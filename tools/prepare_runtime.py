"""Prepare native overlays and remove redundant composer pose packets."""
import hashlib
import json
from pathlib import Path
import struct
from compression import zstd
from compatibility import runtime_inputs_fingerprint
from formats import erpw, pkg, idf, uinode as N, uiops as U
import sys
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_interop import apply, walk, MAIN, TEMPLATE, F1PATH
from halo import layout, sectors, drs_motion, rpm_mask, instruments
from halo.dials import DIALS, F125, F126

ROOT = Path(__file__).resolve().parents[1]
erpw.zstd_d = zstd.decompress
erpw.zstd_c = lambda data: zstd.compress(data, options={
    zstd.CompressionParameter.compression_level: 12,
    zstd.CompressionParameter.window_log: 20,
    zstd.CompressionParameter.content_size_flag: 1,
})


def repair_gauges(archive):
    changes = []
    for resource in archive.res:
        if '/zh_halo_v2_' not in resource.name or not resource.name.endswith('?context=animation'):
            continue
        metadata = pkg.Pkg(archive.frag_data(resource, 0))
        samples = archive.frag_data(resource, 1)
        kept, removed = [], []
        for packet in metadata.root['packets'].items:
            channel = packet['channels'].items[0]
            misc = channel['misc'].value
            target, count = (misc >> 16) & 0xff, misc & 0xffff
            if target == 3:
                if count != 2:
                    raise ValueError('Gauge must have exactly two position keys')
                kept.append(packet)
                continue
            expected = {1: (0., 0., 0., -1.), 2: (1., 1., 1.)}
            if target not in expected or count != 1:
                raise ValueError('Refusing to remove a changing pose channel')
            actual = struct.unpack_from('<' + 'f' * len(expected[target]), samples,
                                        channel['keyptr'].value)
            if actual != expected[target]:
                raise ValueError('Refusing to remove a non-identity pose')
            removed.append(target)
        if len(kept) != 1 or sorted(removed) not in ([], [1, 2]):
            raise ValueError('Unexpected composer gauge structure')
        metadata.root['packets'].items = kept
        archive.set_frag(resource, 0, metadata.to_bytes())
        padding = (-len(samples)) % 16
        archive.set_frag(resource, 1, samples + bytes(padding))
        if archive.frag_data(resource, 1)[:len(samples)] != samples:
            raise ValueError('Gauge samples changed')
        changes.append({'resource': resource.name, 'removed_targets': removed,
                        'remaining_target': 3, 'position_keys': 2,
                        'syst_padding_bytes': padding,
                        'syst_bytes': len(samples) + padding})
    registry = json.loads((ROOT / 'registry/hud.json').read_text())
    def gauges(elements):
        for element in elements:
            if element['kind'] == 'gauge':
                yield element['id']
            yield from gauges(element.get('children', []))
    expected = {ctx.main + '/zh_' + ctx.prefix + '_' + name + '_' + part + '?context=animation'
                for ctx in DIALS for name in gauges(registry['hud.element'][ctx.registry]['elements'])
                for part in ('win', 'ctr')}
    if {item['resource'] for item in changes} != expected:
        raise ValueError('Composer clips differ from the authored gauges')
    return changes


def share_editor_preview(scene_archive, template_archive):
    """Keep one common editor preview and point both hidden setters at it."""
    resource = scene_archive.find(MAIN)
    scene = idf.Idf(scene_archive.frag_data(resource, 0))
    if len(scene.scenes) != 1:
        raise ValueError('Expected one main dial scene for the editor preview')
    entry = scene.scenes[0].entry
    scene_root = entry.get('scene')

    def preview_objects(obj, found=None):
        found = found if found is not None else {}
        name = obj.get('name')
        name = name.value if name is not None else None
        if name in ('halo_v2_pv', 'halo_v2_26_pv'):
            found.setdefault(name, []).append(obj)
        children = obj.get('children')
        if isinstance(children, pkg.Arr):
            for child in children.items:
                if isinstance(child, pkg.Obj):
                    preview_objects(child, found)
        return found

    found = preview_objects(scene_root)
    if any(len(found.get(name, [])) != 1
           for name in ('halo_v2_pv', 'halo_v2_26_pv')):
        raise ValueError('Expected exactly one shared and one 2026 editor preview root')
    shared = idf.Element(found['halo_v2_pv'][0])
    duplicate = idf.Element(found['halo_v2_26_pv'][0])
    if (shared.position, shared.scale, shared.rotation) != (
            duplicate.position, duplicate.scale, duplicate.rotation):
        raise ValueError('Editor preview roots no longer share the same transform')

    # UIPRE entries address widgets by their leaf-name hash, not the IDF's
    # dotted-path elementId. Capture all of those targets before removing the
    # duplicate subtree so its preset setters can be removed with it.
    removed_name_ids = {idf.djb2(element.name) for element, _ in duplicate.walk()}
    uipre_name = 'eaid://ui_package/art/osd/components/dial/dial_complete.uipre'
    preset_resource = scene_archive.find(uipre_name)
    preset = pkg.Pkg(scene_archive.frag_data(preset_resource, 0))
    if int(preset.root['TargetId'].value) != int(scene.scenes[0].name):
        raise ValueError('Dial editor preset no longer targets the main scene')
    preset_elements = preset.root.get('Elements')
    if not isinstance(preset_elements, pkg.Arr):
        raise ValueError('The dial editor preset has no Elements array')

    def preset_ids(elements):
        return {int(element['Id'].value) for element in elements.items}

    def preset_signature(value):
        if isinstance(value, pkg.Val):
            return ('value', value.type, preset_signature(value.value))
        if isinstance(value, pkg.Obj):
            return ('object', tuple((key.value, preset_signature(item))
                                    for key, item in value.items))
        if isinstance(value, pkg.Arr):
            return ('array', tuple(preset_signature(item) for item in value.items))
        if isinstance(value, (list, tuple)):
            return tuple(preset_signature(item) for item in value)
        return value

    scene_name_ids_before = {
        idf.djb2(element.name) for element, _ in scene.scenes[0].root.walk()
    }
    original_preset_ids = preset_ids(preset_elements)
    unresolved_before = original_preset_ids - scene_name_ids_before
    if len(unresolved_before) != 1:
        raise ValueError('Expected exactly one unrelated unresolved baseline preset target')
    removed_preset_ids = removed_name_ids & original_preset_ids
    if not removed_preset_ids:
        raise ValueError('The duplicate preview has no matching editor preset targets')
    preserved_signatures = [preset_signature(element)
                            for element in preset_elements.items
                            if int(element['Id'].value) not in removed_preset_ids]
    preset_elements.items = [
        element for element in preset_elements.items
        if int(element['Id'].value) not in removed_preset_ids
    ]
    if [preset_signature(element) for element in preset_elements.items] != preserved_signatures:
        raise ValueError('Stock or shared editor preset setters changed during cleanup')

    def remove_child(obj, target):
        children = obj.get('children')
        if not isinstance(children, pkg.Arr):
            return False
        before = len(children.items)
        children.items = [child for child in children.items if child is not target]
        if len(children.items) != before:
            return True
        return any(remove_child(child, target) for child in children.items
                   if isinstance(child, pkg.Obj))

    if not remove_child(scene_root, found['halo_v2_26_pv'][0]):
        raise ValueError('Could not remove the duplicate 2026 editor preview root')
    idf.relookup(entry)

    # Only the editor copy receives the static 75% cyan sample textures.
    # The gameplay battery remains on its original materials and clips.
    preview_root = idf.Element(found['halo_v2_pv'][0])
    for part in ('frame', 'fill'):
        element_name = ('halo_v2_pv_battery_frame' if part == 'frame' else
                        'halo_v2_pv_battery_charge_fill')
        element = preview_root.find(element_name)
        if element is None or len(element.geoms) != 1:
            raise ValueError('Editor battery ' + part + ' geometry is missing')
        old_material = element.geoms[0].get('materialid')
        expected_old = (
            'eaid://ui_package/art/osd/components/hud/'
            + 'halo_v2_battery_' + ('frame' if part == 'frame' else 'fill')
            + '.emb?context=default')
        if old_material != expected_old:
            raise ValueError('Unexpected editor battery ' + part + ' material')
        new_material = (
            'eaid://ui_package/art/osd/components/hud/halo_v2_battery_preview_'
            + part + '.emb?context=default')
        geom = element.obj['geoms'].items[0]
        geom['materialid'].value = new_material
        scene_archive.find(new_material)

    scene_archive.set_frag(resource, 0, scene.to_bytes())
    scene_archive.set_frag(preset_resource, 0, preset.to_bytes())

    ui_resource = template_archive.find(TEMPLATE)
    template = pkg.Pkg(template_archive.frag_data(ui_resource, 0))
    f1 = next((node for node in walk(template.root)
               if N.name(node) == F125.template), None)
    if f1 is None:
        raise ValueError('Could not find the shared dial editor controls')
    setters = {
        N.name(node): node for node in walk(f1)
        if N.name(node) in ('v_halo_v2_pv', 'v_halo_v2_26_pv')
    }
    if set(setters) != {'v_halo_v2_pv', 'v_halo_v2_26_pv'}:
        raise ValueError('Expected both editor preview visibility setters')
    for node in setters.values():
        node.items[N.LAYOUT] = U.layout_path('halo_v2_pv')
    template_archive.set_frag(ui_resource, 0, template.to_bytes())
    remaining_name_ids = {
        idf.djb2(element.name) for element, _ in scene.scenes[0].root.walk()
    }
    unresolved_after = preset_ids(preset_elements) - remaining_name_ids
    if unresolved_after != unresolved_before:
        raise ValueError('Removing the duplicate preview introduced unresolved preset targets')
    return {
        'shared_scene_root': 'halo_v2_pv',
        'removed_duplicate_scene_root': 'halo_v2_26_pv',
        'retargeted_setters': sorted(setters),
        'removed_preset_targets': len(removed_preset_ids),
        'unresolved_preset_targets_before': len(unresolved_before),
        'unresolved_preset_targets_after': len(unresolved_after),
        'new_unresolved_preset_targets': 0,
        'preview_battery_materials': {
            'frame': 'halo_v2_battery_preview_frame',
            'fill': 'halo_v2_battery_preview_fill',
        },
        'transform_preserved': True,
    }


def validate_editor_preview(archive, templates):
    """Validate the single editor scene and both hidden UI layout targets."""
    scene = idf.Idf(archive.frag_data(archive.find(MAIN), 0))
    root = scene.scenes[0].root
    names = [element.name for element, _ in root.walk()]
    if names.count('halo_v2_pv') != 1 or 'halo_v2_26_pv' in names:
        raise ValueError('The editor scene must contain only one shared preview root')
    if any(name.startswith('halo_v2_26_pv_') for name in names):
        raise ValueError('2026-only diagnostics remain in the editor preview scene')
    preview = root.find('halo_v2_pv')
    if preview.path != 'boundless_customisation.halo_v2_pv':
        raise ValueError('Shared editor preview must stay under boundless_customisation')
    preview_names = [element.name for element, _ in preview.walk()]
    direct_names = [child.name for child in preview.children]
    if 'halo_v2_pv_base' not in direct_names:
        raise ValueError('Shared editor preview is missing its base artwork')
    for gear in range(1, 9):
        if not any(name.startswith(f'halo_v2_pv_gear_{gear}_')
                   for name in direct_names):
            raise ValueError(f'Shared editor preview is missing gear {gear}')
    if sum(name.startswith('halo_v2_pv_sector_') for name in preview_names) != 162:
        raise ValueError('Shared editor preview sector label set is incomplete')
    if 'halo_v2_pv_battery_charge_win' not in preview_names:
        raise ValueError('Shared editor preview is missing its battery charge mask')
    if any('halo_v2_pv_'+name not in preview_names for name in ('wing_charge','wing_flow',
            'wing_mode','wing_energy_fill_win','mph')):
        raise ValueError('Shared editor preview is missing its battery energy readout')

    if any("wing_deploy" in name or "wing_harvest" in name for name in preview_names):
        raise ValueError("Power columns are exclusive to the 2026 live dial")

    preview_materials = {
        'frame': 'eaid://ui_package/art/osd/components/hud/halo_v2_battery_preview_frame.emb?context=default',
        'fill': 'eaid://ui_package/art/osd/components/hud/halo_v2_battery_preview_fill.emb?context=default',
    }
    original_materials = {
        'frame': 'eaid://ui_package/art/osd/components/hud/halo_v2_battery_frame.emb?context=default',
        'fill': 'eaid://ui_package/art/osd/components/hud/halo_v2_battery_fill.emb?context=default',
    }
    for part, name in (('frame', 'halo_v2_pv_battery_frame'),
                       ('fill', 'halo_v2_pv_battery_charge_fill')):
        element = preview.find(name)
        if element is None or len(element.geoms) != 1:
            raise ValueError('Shared editor battery ' + part + ' geometry is missing')
        if element.geoms[0].get('materialid') != preview_materials[part]:
            raise ValueError('Shared editor battery ' + part + ' is not tinted by its preview asset')
        material = archive.find(preview_materials[part])
        embedded = archive.frag_data(material, 0)
        if b'halo_v2_battery_preview_' + part.encode() + b'.material' not in embedded:
            raise ValueError('Shared editor battery ' + part + ' material does not resolve to its preview tint')
        texture_name = ('eaid://ui_package/art/osd/textures/hud/halo_v2_battery_preview_'
                        + part + '.tif')
        archive.find(texture_name)
        image_resource = archive.find(texture_name + '.image')
        width, height = struct.unpack_from('<II', archive.frag_data(image_resource, 0), 12)
        with Image.open(ROOT / ('art/battery_preview_' + part + '.png')) as image:
            source = image.convert('RGBA')
        if source.size != (width, height):
            raise ValueError('Serialized editor battery ' + part + ' dimensions differ from its cyan sprite')
        decoded = Image.frombytes('RGBA', (width, height),
                                  archive.frag_data(image_resource, 1),
                                  'bcn', 7, 'BC7')
        expected_colour = instruments.battery_colour(.75)
        visible_colours = {pixel[:3] for pixel in source.getdata() if pixel[3]}
        if visible_colours != {expected_colour}:
            raise ValueError('Editor battery ' + part + ' source sprite is not the 75% cyan tint')
        for source_pixel, decoded_pixel in zip(source.getdata(), decoded.getdata()):
            if source_pixel[3] >= 128 and max(abs(source_pixel[i] - decoded_pixel[i])
                                              for i in range(3)) > 1:
                raise ValueError('Editor battery ' + part + ' decoded texture lost its cyan tint')

    live_scene = scene.scenes[0].root
    for part, name in (('frame', 'halo_v2_battery_frame'),
                       ('fill', 'halo_v2_battery_charge_fill')):
        element = live_scene.find(name)
        if element is None or len(element.geoms) != 1 or element.geoms[0].get('materialid') != original_materials[part]:
            raise ValueError('Live battery ' + part + ' material changed with the editor tint')
        expected_clip = MAIN + '/halo_v2_battery_' + (
            'frame' if part == 'frame' else 'charge_fill') + '_colour?context=animation'
        if expected_clip not in {animation.get('asset') for animation in element.anims}:
            raise ValueError('Live battery ' + part + ' lost its native colour animation')
        archive.find(expected_clip)

    preview_fill = preview.find('halo_v2_pv_battery_charge_fill')
    live_fill = live_scene.find('halo_v2_battery_charge_fill')
    preview_window = preview.find('halo_v2_pv_battery_charge_win')
    live_window = live_scene.find('halo_v2_battery_charge_win')
    window_geometry = ('width', 'length', 'minExtents', 'maxExtents',
                       'cornerCurves', 'cornerCurvesRadius')
    if (preview_fill is None or live_fill is None or preview_window is None or
            live_window is None or preview_window.type != 'eWindow' or
            (preview_fill.position, preview_fill.scale) !=
            (live_fill.position, live_fill.scale) or
            (preview_window.position, preview_window.scale) !=
            (live_window.position, live_window.scale) or
            any(preview_window.params.get(key) != live_window.params.get(key)
                for key in window_geometry)):
        raise ValueError('Static 75% editor battery clip geometry changed during tinting')

    registry = json.loads((ROOT / 'registry/hud.json').read_text(encoding='utf-8'))
    records = registry['hud.element']
    expected_sample = {
        'game.ers_stored': .75,
        'game.has_ers': True,
        'view_model_data.hud_halo_v2_charge': '75%',
        'view_model_data.hud_halo_v2_flow': 'DEPLOYING',
        'view_model_data.hud_halo_v2_mph': '155',
    }
    for key in ('glass_dial', 'glass_dial_26'):
        preview_values = records[key].get('editor', {}).get('preview', {})
        if any(preview_values.get(name) != value
               for name, value in expected_sample.items()):
            raise ValueError('Editor battery preview must use the partial-charge sample')

    template = pkg.Pkg(templates.frag_data(templates.find(TEMPLATE), 0))
    f1 = next((node for node in walk(template.root)
               if N.name(node) == F125.template), None)
    if f1 is None:
        raise ValueError('Could not find editor preview visibility controls')
    setters = {
        N.name(node): node for node in walk(f1)
        if N.name(node) in ('v_halo_v2_pv', 'v_halo_v2_26_pv')
    }
    if set(setters) != {'v_halo_v2_pv', 'v_halo_v2_26_pv'}:
        raise ValueError('A shared editor preview visibility setter is missing')
    for name, node in setters.items():
        node_type = struct.pack('<I', node.items[N.PROPS]['type'].value).decode()
        visibility = node.items[N.PROPS].get('visible')
        layout_groups = node.items[N.LAYOUT].items
        links = [item for group in layout_groups for item in group.items]
        if (node_type != 'UIGP' or visibility is None or
                visibility['value'].value is not False):
            raise ValueError('Editor preview visibility setter must remain hidden by default')
        if (len(links) != 1 or links[0]['debugName'].value != 'halo_v2_pv' or
                links[0]['nodeId'].value != N.djb2('halo_v2_pv')):
            raise ValueError('Editor preview setter does not resolve to the shared root')
    scene_name_ids = {idf.djb2(element.name) for element, _ in root.walk()}
    preset_resource = archive.find('eaid://ui_package/art/osd/components/dial/dial_complete.uipre')
    preset = pkg.Pkg(archive.frag_data(preset_resource, 0))
    if int(preset.root['TargetId'].value) != int(scene.scenes[0].name):
        raise ValueError('Shared preview preset target changed from the main scene')
    preset_ids = {int(element['Id'].value) for element in preset.root['Elements'].items}
    unresolved = preset_ids - scene_name_ids
    if len(unresolved) != 1:
        raise ValueError('Shared preview preset cleanup must leave only the one unrelated baseline target')
    return {
        'single_shared_preview': True,
        'preview_under_boundless_customisation': True,
        'preview_tint_assets_resolve': True,
        'live_battery_materials_and_colour_animation_preserved': True,
        'shared_gears_and_sectors': True,
        'partial_battery_sample': True,
        'both_hidden_setters_resolve': True,
        'both_race_hide_targets_hidden_by_default': True,
        'unresolved_preset_targets': 1,
    }


def validate(archive, templates):
    scene = idf.Idf(archive.frag_data(archive.find(MAIN), 0))
    root = scene.scenes[0].root
    for name in ('speed', 'rpm_value', 'rpm_unit', 'brake_label', 'throttle_label', 'special_gear', 'drs_open_label'):
        holder = root.find('halo_v2_' + name + '_n')
        if holder.type != 'eCentre' or not all(
                holder.params.get(key) is True for key in ('centreX', 'centreY')):
            raise ValueError('Readout must use measured native text centering ' + name)
        if root.find('halo_v2_' + name).position != (0., 0., 0.):
            raise ValueError('Readout retained a baseline offset ' + name)
    row = root.find('halo_v2_rpm_row')
    if row.type != 'eStacker' or [child.name for child in row.children] != [
            'halo_v2_rpm_value_n', 'halo_v2_rpm_unit_n']:
        raise ValueError('RPM number and unit must share a native measured row')
    for part, rings, samples in (
            ('value', layout.RPM_NUMBER_GLOW_RINGS, layout.RPM_NUMBER_GLOW_SAMPLES),
            ('unit', layout.RPM_LABEL_GLOW_RINGS, layout.RPM_LABEL_GLOW_SAMPLES)):
        if len([element for element, _ in root.walk()
                if element.name.startswith(f'halo_v2_rpm_{part}_glow_')]) != samples * len(rings):
            raise ValueError('Native-font RPM glow layers are incomplete ' + part)
    rpm_mask = root.find('halo_v2_rpm_win')
    texture = 'eaid://ui_package/art/osd/textures/hud/halo_v2_rpm_fill_mask.tif'
    if rpm_mask.type != 'eMaskTexture' or rpm_mask.params.get('eMaskTexture.maskTextureResource') != texture:
        raise ValueError('RPM fill lost its antialiased moving edge')
    archive.find(texture)
    archive.find(texture + '.image')
    names = [element.name for element, _ in root.walk()]
    prompt_resource = 'eaid://ui_package/art/osd/halo_hud_v2/drs_prompt.idf'
    prompt = idf.Idf(archive.frag_data(archive.find(prompt_resource),0)).scenes[0].root
    prompt_names = {element.name for element,_ in prompt.walk()}
    known_layout_names = set(names) | prompt_names
    if root.find('halo_v2_drs_open_label').type != 'eText':
        raise ValueError('DRS OPEN must use a native text core')
    for element in [root.find('halo_v2_drs_open_label')] + [prompt.find(name) for name in
            ('text','distance_text','halo_drs_prompt_text','halo_pit_prompt_text','drs_activate_tooltip_as_label')]:
        if element.params.get('style') != layout.DRS_TEXT_STYLE:
            raise ValueError('DRS typography differs from the shared HUD font '+element.name)
    for name in names:
        if name.startswith(('halo_v2_', 'zh_halo_v2_', 'halo_drs_')) and names.count(name) != 1:
            raise ValueError('Duplicate scene leaf ' + name)
    for resource in archive.res:
        if resource.name.startswith('eaid://ui_package/art/osd/halo_hud_v2/') and resource.name.endswith('.idf'):
            component = idf.Idf(archive.frag_data(resource, 0))
            for element, _ in component.scenes[0].root.walk():
                texture = element.params.get('eMaskTexture.maskTextureResource', '')
                if texture.startswith('eaid://ui_package/art/osd/textures/hud/halo_v2_pedal_'):
                    archive.find(texture)
                    archive.find(texture + '.image')
                for geometry in element.geoms:
                    if not any(candidate.name.startswith(geometry['resourceid'])
                               for candidate in archive.res) and 'halo_' in geometry['resourceid']:
                        raise ValueError('Missing custom geometry ' + geometry['resourceid'])
                    archive.find(geometry['materialid'])
    if idf.xref_mismatches(scene):
        raise ValueError('Native component XRef mismatch')
    template = pkg.Pkg(templates.frag_data(templates.find(TEMPLATE), 0))
    f1 = next(node for node in walk(template.root) if N.name(node) == 'hud_f1_dial')
    paths = {}
    def visit(node, prefix=''):
        path = prefix + '.' + N.name(node) if prefix else N.name(node)
        if path in paths:
            raise ValueError('Duplicate UI node ' + path)
        paths[path] = node
        for child in N.children(node):
            if N.is_node(child):
                visit(child, path)
    visit(f1)
    for glyph in sectors.glyphs():
        holder = root.find('halo_v2_' + glyph.name + '_n')
        if holder.type != 'eCentre' or len(holder.children) != 1:
            raise ValueError('Sector cell lost independent native text measurement')
        surface = root.find('halo_v2_' + glyph.name + '_surface')
        tangent = root.find('halo_v2_' + glyph.name + '_tangent')
        x,y = layout.hud_point(glyph.anchor.x,glyph.anchor.y)
        if max(abs(a-b) for a,b in zip(surface.position,(x*.018,-y*.018,0.))) > 1e-6:
            raise ValueError('Sector cell lost its projected column position')
        if (surface.params.get('isHidden') is not False or
                tangent.params.get('isHidden') is not False or
                [child.name for child in surface.children] != [tangent.name] or
                [child.name for child in tangent.children][:1] != [holder.name]):
            raise ValueError('Sector projection hierarchy is incomplete or hidden')
        label = paths[F1PATH + '.halo_v2_ctl.t_' + glyph.name]
        props = label.items[N.PROPS]
        expected = '#' + ''.join(f'{channel:02x}' for channel in glyph.colour)
        if props['colourOverride']['value'].value != expected:
            raise ValueError('Sector prefix or time colour is incorrect')
        text = props['text']
        if glyph.binding and text['dbentry'].value != '#' + glyph.binding:
            raise ValueError('Sector time lost its unique value binding')
        if glyph.literal and text['value'].value != glyph.literal:
            raise ValueError('Sector prefix was changed')
        part = 'prefix' if glyph.literal else 'time'
        expected_children = [holder.name]
        for index,effect in enumerate(sectors.effects(part,glyph.colour)):
            name = 'halo_v2_' + glyph.name + f'_light_{index}'
            expected_children.append(name+'_n')
            centre = root.find(name+'_n')
            if centre.type != 'eCentre' or len(centre.children) != 1:
                raise ValueError('Sector effect lost its independent text measurement')
            opacity = paths[F1PATH+'.halo_v2_ctl.'+glyph.name+f'_light_{index}_alpha']
            value = opacity.items[N.PROPS]['Value']['value'].value
            if abs(value-effect.opacity)>1e-6:
                raise ValueError('Sector effect lost its native opacity cap')
            if (opacity.items[N.PROPS]['ParameterName']['value'].value != 'Alpha' or
                    opacity.items[N.LAYOUT].items[0].items[0]['debugName'].value != name+'_n'):
                raise ValueError('Sector effect alpha targets the wrong text instance')
            label = paths[F1PATH+'.halo_v2_ctl.'+glyph.name+f'_light_{index}_text']
            if glyph.binding and label.items[N.PROPS]['text']['dbentry'].value != '#'+glyph.binding:
                raise ValueError('Sector effect has a stale timing binding')
        if [child.name for child in tangent.children] != expected_children:
            raise ValueError('Unexpected sector effect hierarchy')
    validate_battery_binding(paths,F125)
    validate_rpm_tip(archive,F125)
    mask = root.find('halo_v2_battery_charge_win')
    if mask.type != 'eWindow':
        raise ValueError('Battery fill must use the native geometric clip')
    sweep_paths = [F1PATH + f'.halo_v2_ctl.x_drs_sweep_{side}_{part}'
                   for side in ('left', 'right') for part in ('win', 'ctr')]
    drs_path = F1PATH + '.drs_and_pit_distance'
    gate = paths[drs_path + '.halo_drs_sweep_gate']
    timer_path = drs_path + '.halo_drs_sweep_timer'
    timer = paths[timer_path]
    opening_path = drs_path + '.halo_drs_sweep_opening_timer'
    opening = paths[opening_path]
    expired = next(event for event in opening.items[N.EVENTS].items
                   if event['eventName'].value == 'time_out_expired')
    if not any(signal['to_object_name'].value == drs_path + '.halo_drs_sweep_gate' and
               signal['to_pin_name'].value == 'query' for signal in expired['signals'].items):
        raise ValueError('DRS travelling highlight no longer waits for rail extension')
    selector = paths[drs_path + '.ers_state']
    opened = next(event for event in selector.items[N.EVENTS].items
                  if event['eventName'].value == 'drs_live')['signals'].items
    delay = next(signal for signal in opened if signal['to_object_name'].value == opening_path
                 and signal['to_pin_name'].value == 'reset')
    if abs(delay['attributes']['duration']['value'].value - layout.DRS_OPEN_DURATION) > 1e-7:
        raise ValueError('DRS reveal and travelling highlight timing differ')
    enter = paths[F1PATH + '.halo_drs_open.halo_drs_enter']
    if enter.items[N.PROPS]['AnimationCurve']['value'].value != layout.DRS_OPEN_CURVE:
        raise ValueError('DRS text and rails lost their synchronized opening curve')
    for side in ('left', 'right'):
        for part in ('win', 'ctr'):
            target = F1PATH + f'.halo_v2_ctl.x_drs_{side}_{part}'
            signal = next(signal for signal in opened if signal['to_object_name'].value == target
                          and signal['to_pin_name'].value == 'playToFraction')
            if signal['attributes']['curveName']['value'].value != N.djb2(layout.DRS_OPEN_CURVE):
                raise ValueError('DRS rail extension lost its more visible opening curve')
    leave=paths[F1PATH+'.halo_drs_open.halo_drs_leave']
    if leave.items[N.LAYOUT].items[0].items[0]['debugName'].value!='halo_v2_drs_open_label_n':
        raise ValueError('DRS closing fade hides the rail retraction')
    for event in selector.items[N.EVENTS].items:
        state=event['eventName'].value
        if state in ('invalid','drs_live'):
            continue
        for side in ('left','right'):
            for part in ('win','ctr'):
                target=F1PATH+f'.halo_v2_ctl.x_drs_{side}_{part}'
                signal=next(v for v in event['signals'].items if
                    v['to_object_name'].value==target and v['to_pin_name'].value=='playToFraction')
                if (signal['attributes']['value']['value'].value!=0. or
                    signal['attributes']['curveName']['value'].value!=N.djb2(layout.DRS_CLOSE_CURVE)):
                    raise ValueError('DRS closure lost its reverse mask sweep')
    validate_sector_appearance(root,paths,F125)
    for side in ('left', 'right'):
        mask = root.find('halo_v2_drs_sweep_' + side + '_win')
        texture = mask.params.get('eMaskTexture.maskTextureResource', '')
        if mask.type != 'eMaskTexture' or abs(mask.params['width'] -
                drs_motion.WINDOW_WIDTH * layout.HUD_SCALE * .018) > 1e-6:
            raise ValueError('DRS highlight lost its soft, correctly sized native mask')
        archive.find(texture)
        archive.find(texture + '.image')
    for path in sweep_paths:
        if paths[path].items[N.PROPS].get('fraction') is not None:
            raise ValueError('DRS sweep fraction still competes with a data binding')
    for event in gate.items[N.EVENTS].items:
        state = event['eventName'].value
        signals = event['signals'].items
        if state == 'drs_live':
            for path in sweep_paths:
                play = [signal for signal in signals if signal['to_object_name'].value == path
                        and signal['to_pin_name'].value == 'playToFraction']
                if (len(play) != 1 or
                        play[0]['attributes']['curveName']['value'].value != N.djb2(drs_motion.CURVE)):
                    raise ValueError('DRS sweep lost its one-second native animation')
            resets = [signal for signal in signals if signal['to_object_name'].value == timer_path
                      and signal['to_pin_name'].value == 'reset']
            if len(resets) != 1 or resets[0]['attributes']['duration']['value'].value != drs_motion.PERIOD:
                raise ValueError('DRS sweep timer differs from its animation duration')
        elif not any(signal['to_object_name'].value == timer_path and
                     signal['to_pin_name'].value == 'stop' for signal in signals):
            raise ValueError('DRS sweep continues outside the open state')
    expired = next(event for event in timer.items[N.EVENTS].items
                   if event['eventName'].value == 'time_out_expired')
    if not any(signal['to_object_name'].value == drs_path + '.halo_drs_sweep_gate'
               and signal['to_pin_name'].value == 'query' for signal in expired['signals'].items):
        raise ValueError('DRS loop bypasses its current-state guard')
    for command_name in ('hide', 'disable'):
        command = next(command for command in paths[F1PATH].items[N.COMMANDS].items
                       if command['commandName'].value == command_name)
        if not any(signal['to_object_name'].value == timer_path and
                   signal['to_pin_name'].value == 'stop' for signal in command['signals'].items):
            raise ValueError('Hidden HUD does not stop its DRS sweep')
    for part, rings, samples in (
            ('value', layout.RPM_NUMBER_GLOW_RINGS, layout.RPM_NUMBER_GLOW_SAMPLES),
            ('unit', layout.RPM_LABEL_GLOW_RINGS, layout.RPM_LABEL_GLOW_SAMPLES)):
        for index in range(samples * len(rings)):
            prefix = F1PATH + '.halo_v2_ctl.'
            actor_path = prefix + f'rpm_{part}_glow_alpha_{index:02d}'
            actor = paths[actor_path]
            props = actor.items[N.PROPS]
            alpha = rings[index // samples][1] / 255.
            if (props['ParameterName']['value'].value != 'Alpha' or
                    abs(props['Value']['value'].value - alpha) > 1e-6):
                raise ValueError('RPM glow lacks its native alpha cap ' + part)
            label = paths[prefix + f't_rpm_{part}_glow_{index:02d}']
            if not label.items[N.PROPS]['colourOverride']['value'].value.endswith('ff'):
                raise ValueError('RPM glow opacity must use its native Alpha override')
            if part == 'value' and label.items[N.PROPS]['text']['dbentry'].value != '#view_model_data.hud_halo_v2_rpm':
                raise ValueError('RPM digit glow lost its live RPM binding')
            for event in ('command_vmContextValid', 'use_dial', 'show'):
                command = next(c for c in paths[F1PATH].items[N.COMMANDS].items
                               if c['commandName'].value == event)
                if not any(signal['to_object_name'].value == actor_path and
                           signal['to_pin_name'].value == 'activateOverride'
                           for signal in command['signals'].items):
                    raise ValueError('RPM glow alpha lacks an initialization signal ' + part)
    for key, suffix in (('status',''),('distance',''),('prompt','.halo_drs_prompt_caption'),
                        ('pit','.halo_pit_prompt_caption'),('button','.tooltip_drs_button'),
                        ('keyboard','.tooltip_drs_button'),('open',None)):
        context = F1PATH+'.halo_v2_ctl' if suffix is None else F1PATH+'.drs_and_pit_distance'+suffix
        effects = [('outline',layout.DRS_PROMPT_OUTLINE_ALPHA)]
        if key == 'open':
            effects = [('glow',layout.DRS_LABEL_GLOW_ALPHA),('outline',30)]
        for effect,alpha in effects:
            for index in range(4):
                name = f'halo_drs_type_{key}_{effect}_{index}'
                actor = paths[context+'.'+name+'_alpha']
                if abs(actor.items[N.PROPS]['Value']['value'].value-alpha/255.)>1e-6:
                    raise ValueError('DRS text effect lost its opacity cap '+name)
                if name not in known_layout_names:
                    raise ValueError('DRS text effect has no glyph '+name)
    for name,binding in (('distance','distance_formatted'),('bar_status','bar_state_text')):
        label=paths[F1PATH+'.drs_and_pit_distance.'+name]
        if label.items[N.PROPS]['text']['dbentry'].value != binding:
            raise ValueError('DRS caption lost its native live binding '+name)
    tooltip=F1PATH+'.drs_and_pit_distance.tooltip_drs_button.'
    for name,binding in (('icon','icon'),('icon_as_text','action.axis_0.display_text')):
        if paths[tooltip+name].items[N.PROPS]['text']['dbentry'].value != binding:
            raise ValueError('DRS prompt lost its mapped button binding '+name)
    registry=json.loads((ROOT/'registry/hud.json').read_text())['hud.element']['glass_dial']
    battery=next(element for element in registry['elements'] if element['id']=='battery')
    fill=next(element for element in battery['children'] if element['id']=='battery_charge')
    for index,charge in enumerate((0.,1.)):
        actual=(fill['path'][index][0]+fill['window'][0]/2)/layout.HUD_SCALE+layout.CX
        if abs(actual-layout.battery_fill_edge(charge))>1e-4:
            raise ValueError('Battery travel differs from its visible cavity')
    for gear in range(1, 9):
        name = f'halo_v2_gear_{gear}_active'
        gate = root.find(name)
        if gate.geoms or [child.name for child in gate.children] != [name + '_glyph']:
            raise ValueError('Selected-gear visibility must belong to its parent gate')
        if gate.position != (0., 0., 0.) or gate.scale != (1., 1., 1.):
            raise ValueError('Gear fade changed a slot anchor')
        prefix = F1PATH + '.halo_v2_ctl.'
        visible = paths[prefix + f'v_gear_{gear}_active']
        binding = visible.items[N.PROPS]['visible']
        if binding['dbentry'].value != f'#view_model_data.hud_halo_v2_gear{gear}':
            raise ValueError('Gear selection lost its live visibility binding')
        actor_path = prefix + f'gear_{gear}_enter'
        actor = paths[actor_path]
        props = actor.items[N.PROPS]
        if (props['ParameterName']['value'].value != 'Alpha' or
                props['AnimationCurve']['value'].value != 'generic_fade_on' or
                abs(props['StartingValue']['value'].value - .30) > 1e-6 or
                props['Value']['value'].value != 1.):
            raise ValueError('Selected gear lost its original fade')
        for event, pin in (('shown', 'activateOverride'), ('hidden', 'deactivateOverride')):
            signals = next(e for e in visible.items[N.EVENTS].items
                           if e['eventName'].value == event)['signals'].items
            if not any(signal['to_object_name'].value == actor_path and
                       signal['to_pin_name'].value == pin for signal in signals):
                raise ValueError('Gear fade is missing a show/hide transition')
    for path, node in paths.items():
        for section in (N.COMMANDS, N.EVENTS):
            for event in node.items[section].items:
                signals = event.get('signals')
                for signal in signals.items if signals is not None else []:
                    target = signal['to_object_name'].value
                    if target.startswith(F1PATH) and target not in paths:
                        raise ValueError('Missing UI signal target ' + target)
    for path, node in paths.items():
        if '.halo_v2_ctl.' in path or '.halo_drs_open' in path or '.halo_drs_type_' in path:
            for group in node.items[N.LAYOUT].items:
                for binding in group.items:
                    leaf = binding.get('debugName')
                    if leaf is not None and leaf.value not in known_layout_names:
                        raise ValueError('Missing composed scene leaf ' + leaf.value)
    # Recheck clip alignment and crash-sensitive metadata after final serialization.
    for resource in archive.res:
        if resource.name.endswith('?context=animation') and len(archive.frag_data(resource, 1)) % 16:
            raise ValueError('Animation buffer lacks 16-byte padding ' + resource.name)
        if '/zh_halo_v2_' in resource.name and resource.name.endswith('?context=animation'):
            metadata = pkg.Pkg(archive.frag_data(resource, 0))
            packets = metadata.root['packets'].items
            if len(packets) != 1 or ((packets[0]['channels'].items[0]['misc'].value >> 16) & 255) != 3:
                raise ValueError('Unsafe constant pose packet remained')
            if len(archive.frag_data(resource, 1)) % 16:
                raise ValueError('Composer animation buffer lacks 16-byte padding')
    return {'f1_ui_nodes': len(paths), 'unique_native_signal_targets': True,
            'composed_layout_links': True, 'native_xrefs': True,
            'drs_sweep_masks_and_state_guard': True, 'native_battery_direct_binding': True}


def validate_rpm_tip(archive,ctx):
    expected=rpm_mask.path()
    samples={}
    for part in ('win','ctr'):
        name=ctx.main+'/zh_'+ctx.prefix+'_rpm_'+part+'?context=animation'
        resource=archive.find(name)
        metadata=pkg.Pkg(archive.frag_data(resource,0))
        channel=metadata.root['packets'].items[0]['channels'].items[0]
        count=channel['misc'].value&0xffff
        if count!=len(expected):
            raise ValueError('RPM tip lost its sampled curve')
        raw=archive.frag_data(resource,1)
        times=struct.unpack_from('<'+'f'*count,raw,channel['timesptr'].value)
        values=struct.unpack_from('<'+'f'*(3*count),raw,channel['keyptr'].value)
        if max(abs(v-i/(count-1)) for i,v in enumerate(times))>1e-6:
            raise ValueError('RPM motion timing is nonuniform')
        samples[part]=values
        for i,(x,y) in enumerate(expected):
            target=(x*.018,-y*.018,0.) if part=='win' else (-x*.018,y*.018,.12)
            if max(abs(a-b) for a,b in zip(values[i*3:i*3+3],target))>1e-6:
                raise ValueError('RPM cap/counter motion differs from its curved path')
    for i in range(len(expected)):
        if max(abs(samples['win'][i*3+j]+samples['ctr'][i*3+j]) for j in (0,1))>1e-6:
            raise ValueError('RPM counter-motion moved the static artwork')


def validate_sector_appearance(root,paths,ctx):
    prefix=ctx.path+'.'+ctx.prefix+'_ctl.'
    for sector in range(1,4):
        key=f'sector_s{sector}'
        wrapper=root.find(ctx.prefix+'_'+key+'_times')
        if len(wrapper.children)!=24 or wrapper.position!=(0.,0.,0.) or wrapper.scale!=(1.,1.,1.):
            raise ValueError('Sector appearance changed its projected layout')
        if any('_prefix_' in child.name for child in wrapper.children):
            raise ValueError('Sector appearance must retain steady labels')
        actor=paths[prefix+key+'_enter']
        props=actor.items[N.PROPS]
        if (props['AnimationCurve']['value'].value!=layout.SECTOR_FADE_CURVE or
            abs(props['StartingValue']['value'].value-layout.SECTOR_FADE_START)>1e-6):
            raise ValueError('Sector appearance lost its brief subtle fade')
        for suffix in ('ready','pulse'):
            decision=paths[prefix+key+'_'+suffix]
            expected=f'#view_model_data.hud_halo_v2_sector_s{sector}_{suffix}'
            if decision.items[N.PROPS]['dbEntry']['value'].value!=expected:
                raise ValueError('Sector appearance reads an incorrect revision leaf')
        for name in ('hide','disable'):
            command=next(c for c in paths[ctx.path].items[N.COMMANDS].items if c['commandName'].value==name)
            targets={(v['to_object_name'].value,v['to_pin_name'].value) for v in command['signals'].items}
            if (prefix+key+'_pulse','unregister') not in targets:
                raise ValueError('Sector appearance selector survives a hidden dial')


def validate_battery_binding(paths,ctx):
    prefix=ctx.path+'.'+ctx.prefix+'_ctl.'
    for key in ('deploy_kw','harvest_kw','deploy_caption','harvest_caption'):
        if (prefix+'t_wing_'+key in paths) != (ctx == F126):
            raise ValueError('Unexpected season for wing power readout '+key)
    names=['x_battery_charge_win','x_battery_charge_ctr',
           'x_'+ctx.prefix+'_battery_frame_colour',
           'x_'+ctx.prefix+'_battery_charge_fill_colour']
    for name in names:
        fraction=paths[prefix+name].items[N.PROPS]['fraction']
        if fraction['value'].type!='fp32' or fraction['dbentry'].value!='ers_stored':
            raise ValueError('Battery channel lost its direct normalized charge binding '+name)
    if any(prefix+name in paths for name in ('battery_smooth_gate','battery_smooth_timer')):
        raise ValueError('Battery retained the superseded easing timer')


def validate_f126(archive, templates):
    """Check the second dial's native types, lifecycle, namespaces and UI links."""
    from halo.f126 import BOOST_STATES
    from formats import uiops as U
    ctx=F126
    scene=idf.Idf(archive.frag_data(archive.find(ctx.main),0))
    root=scene.scenes[0].root
    template=pkg.Pkg(templates.frag_data(templates.find(TEMPLATE),0))
    f1=next(n for n in walk(template.root) if N.name(n)==ctx.template)
    paths={}
    def visit(node,parent=''):
        path=parent+'.'+N.name(node) if parent else N.name(node)
        if path in paths:
            raise ValueError('Duplicate 2026 UI node '+path)
        paths[path]=node
        for child in N.children(node):
            if N.is_node(child):
                visit(child,path)
    visit(f1)
    prefix=ctx.path+'.'+ctx.prefix+'_ctl.'
    names=[element.name for element,_ in root.walk()]
    custom=[name for name in names if name.startswith(ctx.prefix)]
    if len(custom)!=len(set(custom)) or idf.xref_mismatches(scene):
        raise ValueError('2026 scene contains duplicate names or an XRef mismatch')
    for name in ('speed','rpm_value','rpm_unit','special_gear','drs_open_label'):
        holder=root.find(ctx.prefix+'_'+name+'_n')
        if holder.type!='eCentre' or holder.params.get('centreX') is not True:
            raise ValueError('2026 readout lost native centering '+name)
    for name in ('rpm_win','drs_sweep_left_win','drs_sweep_right_win'):
        mask=root.find(ctx.prefix+'_'+name)
        if mask.type!='eMaskTexture':
            raise ValueError('2026 native mask missing '+name)
        texture=mask.params['eMaskTexture.maskTextureResource']
        archive.find(texture)
        archive.find(texture+'.image')
    def binding(node,prop,path,tag):
        value=node.items[N.PROPS][prop]
        expected='#'+path if path.startswith('view_model_data.') else path
        if value['dbentry'].value!=expected or value['value'].type!=tag:
            raise ValueError('2026 native binding has the wrong path or type '+prop+' '+path)
    for name,prop,path,tag in (
        ('t_sm_distance_value','text','distance_to_xm','stri'),
        ('v_sm_distance','visible','show_xm_distance','bool'),
        ('v_sm_ready','visible','x_mode_show_tooltip','bool'),
        ('v_sm_available','visible','is_xm_available','bool'),
        ('t_sm_button','text','x_mode_overtake_tooltip_icon_path','stri'),
        ('t_sm_keyboard','text','x_mode_overtake_tooltip_text','stri'),
        ('t_sm_keyboard','localise','x_mode_overtake_tooltip_localise','bool'),
        ('v_sm_prompt_closed','visible','is_xm_active','bool'),
        ('t_overtake_on','visible','om_active','bool'),
    ):
        binding(paths[prefix+name],prop,path,tag)
    for gate_name in ('sm_active','sm_sweep_gate','sm_close_gate'):
        gate=paths[prefix+gate_name]
        if gate.items[N.PROPS]['dbEntry']['value'].value!='is_xm_active':
            raise ValueError('Straight Mode effects use an incorrect state')
        if gate.items[N.PROPS]['value']['value'].type!='bool':
            raise ValueError('Straight Mode selector must compare a boolean')
    boost=paths[prefix+'boost_state']
    if (boost.items[N.PROPS]['dbEntry']['value'].value!='ers_overtake_state' or
        {e['eventName'].value for e in boost.items[N.EVENTS].items}!=set(BOOST_STATES)):
        raise ValueError('Boost state no longer matches the stock enum decision')
    if paths[prefix+'t_wing_mode'].items[N.PROPS]['text']['dbentry'].value != '#view_model_data.hud_halo_v2_mode26':
        raise ValueError('2026 wing must use its ordinary season mode')
    for event in boost.items[N.EVENTS].items:
        active = event['eventName'].value == 'eActive'
        pins = {(s['to_object_name'].value,s['to_pin_name'].value) for s in event['signals'].items}
        if ((prefix+'wing_boost','show' if active else 'hide') not in pins or
                (prefix+'wing_mode','hide' if active else 'show') not in pins):
            raise ValueError('2026 wing Boost gate disagrees with '+event['eventName'].value)
    validate_battery_binding(paths,ctx)
    validate_rpm_tip(archive,ctx)
    if root.find(ctx.prefix+'_battery_charge_win').type!='eWindow':
        raise ValueError('2026 battery fill must use the native geometric clip')
    validate_sector_appearance(root,paths,ctx)
    leave=paths[prefix+'sm_leave']
    if leave.items[N.LAYOUT].items[0].items[0]['debugName'].value!=ctx.prefix+'_drs_open_label_n':
        raise ValueError('SM closing fade hides the rail retraction')
    inactive=next(e for e in paths[prefix+'sm_active'].items[N.EVENTS].items if e['eventName'].value=='no')
    for side in ('left','right'):
        for part in ('win','ctr'):
            target=prefix+f'x_drs_{side}_{part}'
            signal=next(v for v in inactive['signals'].items if
                v['to_object_name'].value==target and v['to_pin_name'].value=='playToFraction')
            if (signal['attributes']['value']['value'].value!=0. or
                signal['attributes']['curveName']['value'].value!=N.djb2(layout.DRS_CLOSE_CURVE)):
                raise ValueError('SM closure lost its reverse mask sweep')

    for gear in range(1,9):
        binding(paths[prefix+f'v_gear_{gear}_active'],'visible',
                f'view_model_data.hud_halo_v2_gear{gear}','bool')
        if root.find(ctx.prefix+f'_gear_{gear}_active').children[0].name != ctx.prefix+f'_gear_{gear}_active_glyph':
            raise ValueError('2026 gear animation hierarchy is incomplete')
    for command_name in ('hide','disable'):
        command=next(c for c in paths[ctx.path].items[N.COMMANDS].items
                     if c['commandName'].value==command_name)
        signals={(v['to_object_name'].value,v['to_pin_name'].value) for v in command['signals'].items}
        for name in ('sm_active','boost_state'):
            if (prefix+name,'unregister') not in signals:
                raise ValueError('2026 mode selector remains registered when hidden')
        for name in ('sm_opening_timer','sm_sweep_timer','sm_close_timer'):
            if (prefix+name,'stop') not in signals:
                raise ValueError('2026 hidden HUD timer keeps running '+name)
    for path,node in paths.items():
        for section in (N.COMMANDS,N.EVENTS):
            for event in node.items[section].items:
                signals=event.get('signals')
                for signal in signals.items if signals is not None else []:
                    target=signal['to_object_name'].value
                    if target.startswith(ctx.path) and target not in paths:
                        raise ValueError('Missing 2026 native signal target '+target)
        if path.startswith(prefix):
            for group in node.items[N.LAYOUT].items:
                for item in group.items:
                    name=item.get('debugName')
                    if name is not None and name.value not in names:
                        raise ValueError('Missing 2026 composed layout '+name.value)
    return {'f1_ui_nodes':len(paths),'native_bindings_and_types':True,
            'shared_charge_rpm_gears':True,'separate_mode_states':True,
            'native_xrefs_and_signal_targets':True,'timer_lifecycle':True}


def prepare(expected_inputs=None, settings=None):
    expected_inputs=expected_inputs or runtime_inputs_fingerprint(settings)
    if runtime_inputs_fingerprint(settings)!=expected_inputs:
        raise ValueError('Source inputs changed before composition preparation')
    compiled, output = ROOT / 'build/composed', ROOT / 'runtime'
    output.mkdir(exist_ok=True)
    scene = erpw.Erp(compiled / 'hud_scene.erp')
    templates = erpw.Erp(compiled / 'hud_template.erp')
    before = {resource.name: [scene.frag_data(resource, index)
        for index in range(len(resource.frags))] for resource in scene.res}
    changes = repair_gauges(scene)
    interop = {ctx.dial: apply(scene, templates, ctx=ctx) for ctx in DIALS}
    editor_preview = share_editor_preview(scene, templates)
    native_padding = []
    for resource in scene.res:
        if resource.name.endswith('?context=animation'):
            samples = scene.frag_data(resource, 1)
            padding = (-len(samples)) % 16
            if padding:
                scene.set_frag(resource, 1, samples + bytes(padding))
                native_padding.append({'resource': resource.name, 'padding_bytes': padding})
    scene.to_file(output / 'hud_scene.erp', reframe=False)
    templates.to_file(output / 'hud_template.erp', reframe=False)
    final = erpw.Erp(output / 'hud_scene.erp')
    final_template = erpw.Erp(output / 'hud_template.erp')
    clips = {item['resource'] for item in changes}
    tip_clips={name for info in interop.values() for name in info['rpm_tip']['clips']}
    allowed_changed_resources = {
        'eaid://ui_package/art/osd/components/dial/dial_complete.uipre',
    }
    for name, fragments in before.items():
        resource = final.find(name)
        actual = [final.frag_data(resource, index) for index in range(len(resource.frags))]
        if name in {ctx.main for ctx in DIALS} or name in allowed_changed_resources:
            continue
        if name in tip_clips:
            continue  # Validated against the exact shared sampled path below.
        if name in clips:
            original = pkg.Pkg(fragments[0])
            original.root['packets'].items = [packet for packet in original.root['packets'].items
                if ((packet['channels'].items[0]['misc'].value >> 16) & 255) == 3]
            padded = fragments[1] + bytes((-len(fragments[1])) % 16)
            if actual != [original.to_bytes(), padded, *fragments[2:]]:
                raise ValueError('Position clip metadata or samples changed ' + name)
        elif actual != fragments:
            raise ValueError('Unexpected composer resource change ' + name)
    checks = {
        'editor_preview': validate_editor_preview(final, final_template),
        'f1_25': validate(final, final_template),
        'f1_26': validate_f126(final, final_template),
    }
    scenes = ['flow_race.erp', 'flow_options.erp', 'persistent.erp', 'screens/hud_spectator_2.erp']
    templates_paths = ['flow_race.erp', 'flow_options.erp']
    operations = {'schema_version': 1, 'ops': [
        {'op': 'overlay', 'source': 'runtime/hud_scene.erp',
         'erps': ['2025_asset_groups/ui_package/' + path for path in scenes]},
        {'op': 'overlay', 'source': 'runtime/hud_template.erp',
         'erps': ['2025_asset_groups/ui_package/' + path for path in templates_paths]},
    ]}
    (output / 'overlays.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    if runtime_inputs_fingerprint(settings)!=expected_inputs:
        raise ValueError('Source inputs changed during preparation. Retry the build.')
    record = {'clips': changes, 'native_clip_padding': native_padding,
        'native_interop': interop, 'editor_preview': editor_preview,
        'checks': checks,
        'hud_registry_sha256': hashlib.sha256((ROOT / 'registry/hud.json').read_bytes()).hexdigest(),
        'source_inputs_sha256': expected_inputs,
        'unchanged_sample_values_except_sampled_rpm_tip': True,
        'runtime_archives': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in output.glob('*.erp')}}
    (output / 'validation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'Verified {len(changes)} aligned position-only clips, native controls and UI links.')


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    prepare()
