"""Connect composed artwork to the game's native inputs for each supported dial generation."""
import copy
import math
import struct
import uuid
from pathlib import Path
from formats import erpw, idf, pkg, uinode as N, uiops as U
from halo import layout, energy_panel, instruments, material, sectors, drs_motion, rpm_mask
from halo.tuning import rgb
from halo.dials import F125, F126
from halo.f126 import BOOST_STATES

ROOT = Path(__file__).resolve().parents[1]
DIAL = 'eaid://ui_package/art/osd/components/dial/'
MAIN = DIAL + 'dial_complete.idf'
OWN = 'eaid://ui_package/art/osd/halo_hud_v2/'
TEMPLATE = 'eaid://ui_package/templates/hud_dynamic_templates.ui'
F1PATH = 'hud_f1_dial.osd_visibility_option.f1_dial_child'
DRSPATH = F1PATH + '.drs_and_pit_distance'


def walk(node):
    if N.is_node(node):
        yield node
    if isinstance(node, pkg.Obj):
        for _, child in node.items:
            yield from walk(child)
    elif isinstance(node, pkg.Arr):
        for child in node.items:
            yield from walk(child)


def each_string(node):
    if isinstance(node, pkg.Val) and node.type == 'stri':
        yield node
    elif isinstance(node, pkg.Obj):
        for _, child in node.items:
            yield from each_string(child)
    elif isinstance(node, pkg.Arr):
        for child in node.items:
            yield from each_string(child)


def replace_prefix(document, old, new):
    for value in each_string(document):
        if value.value.startswith(old):
            value.value = new + value.value[len(old):]


def clone_resource(archive, reference, source, destination):
    if any(r.name == destination for r in archive.res):
        raise ValueError('Duplicate resource ' + destination)
    resource = copy.deepcopy(reference.find(source))
    resource.name = destination
    archive.res.append(resource)
    return resource


def detach_scene(root, name):
    for element, _ in root.walk():
        children = element.obj.get('children')
        if not isinstance(children, pkg.Arr):
            continue
        for index, child in enumerate(children.items):
            if child['name'].value == name:
                return children.items.pop(index)
    raise KeyError(name)


def refresh_scene(scene):
    root = scene.scenes[0].root.obj
    for child in root['children'].items:
        idf.recompute_ids(child, child['name'].value, [])
    idf.relookup(scene.scenes[0].entry)


def component(archive, reference, source, destination, material_source):
    resource = clone_resource(archive, reference, source, destination)
    scene = idf.Idf(archive.frag_data(resource, 0))
    scene.scenes[0].entry['name'].value = idf.component_id(destination)
    material = idf.material_binding(destination)
    clone_resource(archive, reference, material_source, material)
    # The geometry material reference must follow the namespaced component.
    replace_prefix(scene.pkg.root, material_source, material)
    return resource, scene


def attach_native(scene, slot, destination, ctx=F125, parent=None):
    element = detach_scene(scene.scenes[0].root, slot)
    idf.retarget(element, destination)
    scale = layout.HUD_SCALE * .018 / .0065
    element.set('position', pkg.Val('vec3', [.117 * scale, -1.1875 * scale, 0., 0.]))
    element.set('scale', pkg.Val('vec3', [scale, scale, 1., 0.]))
    scene.scenes[0].root.find(parent or ctx.prefix).obj['children'].items.append(element)


def pedals(archive, reference, scene, ctx=F125):
    source = DIAL + 'engine_meters.idf'
    destination = ctx.own + 'pedals.idf'
    resource, native = component(archive, reference, source, destination,
                                 DIAL + 'engine_meters.emb?context=default')
    for suffix in ('?context=animstringtable&file=0',
                   '/brake_slider_null?context=animation',
                   '/accelerate_slider_null?context=animation'):
        clip = clone_resource(archive, reference, source + suffix, destination + suffix)
        if 'context=animation' in suffix:
            metadata = pkg.Pkg(archive.frag_data(clip, 0))
            replace_prefix(metadata.root, source, destination)
            side = 'brake' if 'brake_slider_null' in suffix else 'accelerate'
            sign = -1 if side == 'brake' else 1
            points = [point for index in range(10) for point in layout.slat_points(sign, index)]
            top = min(y for x, y in points)
            bottom = max(y for x, y in points)
            start = -.46 - (bottom - layout.CY + 3.5) * .0065 / layout.PEDAL_MASK_SCALE
            end = -.46 + (layout.CY - top + 3.5) * .0065 / layout.PEDAL_MASK_SCALE
            channel = metadata.root['packets'].items[0]['channels'].items[0]
            if channel['name'].value != side + '_slider_null' or channel['misc'].value & 0xffff != 2:
                raise ValueError('Unexpected native pedal position keys')
            samples = bytearray(archive.frag_data(clip, 1))
            struct.pack_into('<6f', samples, channel['keyptr'].value,
                             0., start, .00015, 0., end, .00015)
            archive.set_frag(clip, 1, bytes(samples))
            native.scenes[0].root.find(side + '_slider_null').obj.set(
                'position', pkg.Val('vec3', [0., start, .00015, 0.]))
            mask = native.scenes[0].root.find(side + '_mask')
            if any(not math.isclose(scale, layout.PEDAL_MASK_SCALE)
                   for scale in mask.scale[:2]):
                raise ValueError('Native pedal mask scale changed')
            texture = ('eaid://ui_package/art/osd/textures/hud/' + ctx.prefix + '_pedal_') + side + '_mask.tif'
            archive.find(texture)
            archive.find(texture + '.image')
            idf.set_param(mask.obj, 'eMaskTexture.maskTextureResource', texture)
            archive.set_frag(clip, 0, metadata.to_bytes())
    for element, _ in native.scenes[0].root.walk():
        animations = element.obj.get('anims')
        if animations is not None:
            replace_prefix(animations, source, destination)
    refresh_scene(native)
    archive.set_frag(resource, 0, native.to_bytes())
    attach_native(scene, 'engine_meters', destination, ctx=ctx, parent=ctx.prefix+'_pedal_gradual')


def soft_mask(archive, reference, scene, name, texture):
    prototype = idf.Idf(reference.frag_data(reference.find(DIAL + 'engine_meters.idf'), 0))
    mask_type = prototype.scenes[0].root.find('brake_mask').obj['typeName']
    mask = scene.scenes[0].root.find(name)
    width, height = mask.params['width'], mask.params['length']
    mask.obj.set('typeName', copy.deepcopy(mask_type))
    mask.obj['params'].items = [parameter for parameter in mask.obj['params'].items
        if parameter['name'].value not in ('length', 'cornerCurves', 'cornerCurvesRadius')]
    for key, value, kind in (
            ('className', 'eMaskTexture', 'stri'),
            ('enabled', True, 'bool'), ('width', width, 'fp32'), ('height', height, 'fp32'),
            ('eMaskTexture.maskHalfVec', [width/2, height/2, 0., 0.], 'vec3')):
        idf.set_param(mask.obj, key, value, kind)
    archive.find(texture)
    archive.find(texture + '.image')
    idf.set_param(mask.obj, 'eMaskTexture.maskTextureResource', texture)


def battery_binding(controls, ctx=F125):
    """Track the native normalized charge directly on every animation channel."""
    names = ['x_battery_charge_win', 'x_battery_charge_ctr',
             'x_' + ctx.prefix + '_battery_frame_colour',
             'x_' + ctx.prefix + '_battery_charge_fill_colour']
    for name in names:
        N.child(controls, name).items[N.PROPS].set('fraction', U.prop('fp32',0.,'ers_stored'))
    return {'method':'direct native fraction', 'value':'ers_stored',
            'value_tag':'fp32', 'channels':names,
            'fill_feather_art_pixels':layout.BATTERY_FILL_FEATHER}


def battery_colours(archive, reference, scene, controls, dial_child, ctx=F125):
    source = DIAL + 'dial_complete.idf/speedo_number?context=animation'
    prototype = scene.scenes[0].root.find('speedo_number').obj['anims'].items[0]
    for leaf in ((ctx.prefix + '_battery_frame'), (ctx.prefix + '_battery_charge_fill')):
        keys = instruments.battery_keys('frame' if leaf.endswith('_frame') else 'fill')
        times = [time for time, colour in keys]
        colours = [tuple(channel / 255. for channel in colour) + (1.,)
                   for time, colour in keys]
        raw = bytearray(struct.pack('<' + 'f' * len(times), *times))
        key_start = (len(raw) + 15) & ~15
        raw.extend(bytes(key_start - len(raw)))
        for index, (time, colour) in enumerate(zip(times, colours)):
            before, after = max(0, index - 1), min(len(times) - 1, index + 1)
            left = time - (time - times[before]) / 3
            right = time + (times[after] - time) / 3
            for component_index, value in enumerate(colour):
                incoming = value - (value - colours[before][component_index]) / 3
                outgoing = value + (colours[after][component_index] - value) / 3
                raw.extend(struct.pack('<5f', value, incoming, left, outgoing, right))
        clip_path = ctx.main + '/' + leaf + '_colour?context=animation'
        clip = clone_resource(archive, reference, source, clip_path)
        metadata = pkg.Pkg(archive.frag_data(clip, 0))
        packet = metadata.root['packets'].items[0]
        if packet['interpolator'].value != 4:
            raise ValueError('Unexpected native colour interpolator')
        channel = packet['channels'].items[0]
        if channel['name'].value != 'DiffuseColour':
            raise ValueError('Unexpected native colour channel')
        channel['timesptr'].value = 0
        channel['keyptr'].value = key_start
        channel['misc'].value = (channel['misc'].value & ~0xffff) | len(times)
        archive.set_frag(clip, 0, metadata.to_bytes())
        archive.set_frag(clip, 1, bytes(raw))
        animation = copy.deepcopy(prototype)
        animation['asset'].value = clip_path
        scene.scenes[0].root.find(leaf).obj['anims'].items.append(animation)
        controller = copy.deepcopy(N.child(controls, 'x_battery_charge_win'))
        controller.items[N.PROPS]['name'].value = 'x_' + leaf + '_colour'
        controller.items[N.LAYOUT] = U.layout_path(leaf)
        controls.items[N.CHILDREN].items.append(controller)
    binding = battery_binding(controls, ctx=ctx)
    return {'colour_keys': [[time, list(colour)] for time, colour in keys],
            'raw_bytes': len(raw), 'key_offset': key_start, 'binding': binding}


def rpm_tip_motion(archive,reference,scene,ctx):
    """Retain position-only clips while sampling the cap along the actual arc."""
    soft_mask(archive,reference,scene,ctx.prefix+'_rpm_win',
        'eaid://ui_package/art/osd/textures/hud/'+ctx.prefix+'_rpm_fill_mask.tif')
    points=rpm_mask.path()
    clips=[]
    for part in ('win','ctr'):
        name='zh_'+ctx.prefix+'_rpm_'+part
        resource=archive.find(ctx.main+'/'+name+'?context=animation')
        metadata=pkg.Pkg(archive.frag_data(resource,0))
        packets=metadata.root['packets'].items
        if len(packets)!=1 or packets[0]['interpolator'].value!=5:
            raise ValueError('RPM cap expects the verified linear position interpolator')
        channel=packets[0]['channels'].items[0]
        if ((channel['misc'].value>>16)&255)!=3:
            raise ValueError('RPM cap must retain a position-only channel')
        values=[[x*.018,-y*.018,0.] for x,y in points]
        if part=='ctr':
            values=[[-x,-y,.12] for x,y,_ in values]
        raw=bytearray(struct.pack('<'+'f'*len(points),
                                  *(i/(len(points)-1) for i in range(len(points)))))
        key_start=(len(raw)+15)&~15
        raw.extend(bytes(key_start-len(raw)))
        raw.extend(struct.pack('<'+'f'*(len(values)*3),*(n for point in values for n in point)))
        raw.extend(bytes((-len(raw))%16))
        channel['timesptr'].value=0
        channel['keyptr'].value=key_start
        channel['misc'].value=(channel['misc'].value&~0xffff)|len(points)
        archive.set_frag(resource,0,metadata.to_bytes())
        archive.set_frag(resource,1,bytes(raw))
        scene.scenes[0].root.find(name).obj.set('position',pkg.Val('vec3',values[0]+[0.]))
        clips.append(resource.name)
    return {'clips':clips,'position_keys':len(points),
            'profile':'round cap following sampled wing curvature',
            'mask_size':list(rpm_mask.TEXTURE_SIZE)}


def remove_signals(root, prefixes):
    for node in walk(root):
        for section in (N.COMMANDS, N.EVENTS):
            for event in node.items[section].items:
                signals = event.get('signals')
                if signals is not None:
                    signals.items = [s for s in signals.items
                        if not any(s['to_object_name'].value == prefix or
                                   s['to_object_name'].value.startswith(prefix + '.')
                                   for prefix in prefixes)]


def drs_sweep(archive, reference, scene, native, selector, dial_child, controls):
    """Move mirrored soft masks along the rails using the game's UI clock."""
    channels = [N.child(controls, f'x_drs_sweep_{side}_{part}')
                for side in ('left', 'right') for part in ('win', 'ctr')]
    for side in ('left', 'right'):
        soft_mask(archive, reference, scene, 'halo_v2_drs_sweep_' + side + '_win',
                  'eaid://ui_package/art/osd/textures/hud/halo_v2_drs_sweep_' + side + '_mask.tif')

    for channel in channels:
        N.drop_key(channel.items[N.PROPS], 'fraction')
    timer_name, gate_name = 'halo_drs_sweep_timer', 'halo_drs_sweep_gate'
    timer_path, gate_path = DRSPATH + '.' + timer_name, DRSPATH + '.' + gate_name
    opening_name = 'halo_drs_sweep_opening_timer'
    opening_path = DRSPATH + '.' + opening_name

    def stop_signals(event):
        return [U.sig(timer_path, 'stop', event), U.sig(opening_path, 'stop', event)] + [
            U.sig(F1PATH + '.halo_v2_ctl.' + N.name(channel),
                  'goToFraction', event, {'value': 0.}) for channel in channels]

    start = []
    for channel in channels:
        path = F1PATH + '.halo_v2_ctl.' + N.name(channel)
        start.extend([
            U.sig(path, 'goToFraction', 'drs_live', {'value': 0.}),
            U.sig(path, 'playToFraction', 'drs_live',
                  {'curveName': N.djb2(drs_motion.CURVE), 'value': 1.}),
        ])
    start.append(U.sig(timer_path, 'reset', 'drs_live', {'duration': drs_motion.PERIOD}))
    gate = N.clone_node(selector, DRSPATH, gate_name)
    gate.items[N.COMMANDS].items = []
    gate.items[N.CHILDREN].items = []
    gate.items[N.EVENTS].items = [
        U.event(event['eventName'].value,
                start if event['eventName'].value == 'drs_live'
                else stop_signals(event['eventName'].value))
        for event in selector.items[N.EVENTS].items]
    timer = N.clone_node(N.child(native, 'halo_drs_close_timer'), DRSPATH, timer_name)
    timer.items[N.EVENTS].items = [U.event('time_out_expired', [
        U.sig(gate_path, 'query', 'time_out_expired')])]
    opening = N.clone_node(N.child(native, 'halo_drs_close_timer'), DRSPATH, opening_name)
    opening.items[N.EVENTS].items = [U.event('time_out_expired', [
        U.sig(gate_path, 'query', 'time_out_expired')])]
    native.items[N.CHILDREN].items.extend([gate, timer, opening])

    def open_signals(event):
        return stop_signals(event) + [U.sig(opening_path, 'reset', event,
                                           {'duration': layout.DRS_OPEN_DURATION})]

    for event in selector.items[N.EVENTS].items:
        state = event['eventName'].value
        event['signals'].items.extend(
            open_signals(state) if state == 'drs_live' else stop_signals(state))
    for command in native.items[N.COMMANDS].items:
        event = command['commandName'].value
        if event in ('trigger', 'untrigger'):
            command['signals'].items[:0] = stop_signals(event)
    for command in dial_child.items[N.COMMANDS].items:
        event = command['commandName'].value
        if event in ('hide', 'disable'):
            command['signals'].items.extend(stop_signals(event))
        elif event in ('show', 'use_dial', 'command_vmContextValid'):
            command['signals'].items.extend(open_signals(event))
    return {'opening_delay_seconds': layout.DRS_OPEN_DURATION,
            'period_seconds': drs_motion.PERIOD, 'curve': drs_motion.CURVE,
            'channels': len(channels), 'mask_width_art_pixels': drs_motion.WINDOW_WIDTH,
            'direction': 'centre-out', 'loop_guard': 'native drs_pit_state query'}



def drs_typography(scene, prompt_scene, native, controls, dial_child):
    """Style native DRS text with crisp cores and explicitly capped edge effects."""
    main_root = scene.scenes[0].root
    prompt_root = prompt_scene.scenes[0].root
    open_holder = main_root.find('halo_v2_drs_open_label_n')
    world_per_pixel = layout.HUD_SCALE * .018
    native_scale = world_per_pixel / .0065
    legacy_text_scale = open_holder.scale[0] / native_scale * layout.STYLE['text_size'] / 100.
    all_text_colour = (rgb(layout.STYLE['text_colour'])
                       if layout.STYLE['text_colour'] != '#ffffff' else None)
    prompt_parents = {child.name: parent.obj for parent, _ in prompt_root.walk()
                      for child in parent.children}
    records = []

    def decorate(parent, glyph, controller, owner, context, pixel_unit, key, colour,
                 outline=False):
        controller.items[N.PROPS].set('colourOverride', U.prop('rgba',
            '#' + ''.join(f'{value:02x}' for value in colour)))
        idf.set_param(glyph, 'eLayer.layer', 40, 'si32')
        idf.set_param(glyph, 'eLayer.layerIsOffset', False, 'bool')
        rings = [('outline',layout.DRS_PROMPT_OUTLINE_RADIUS,
                  layout.DRS_PROMPT_OUTLINE_ALPHA,(0,0,0))]
        if key == 'open':
            rings = [('glow',layout.DRS_LABEL_GLOW_RADIUS,layout.DRS_LABEL_GLOW_ALPHA,colour[:3])]
        if outline:
            rings.insert(0, ('outline', .28 * layout.STYLE['text_outline'],
                             30, (0, 0, 0)))
        count = 0
        for effect, radius, alpha, tint in rings:
            for index in range(4):
                name = f'halo_drs_type_{key}_{effect}_{index}'
                angle = index * math.tau / 4
                copy_glyph = copy.deepcopy(glyph)
                copy_glyph['name'].value = name
                position = list(glyph['position'].value)
                position[0] += radius * pixel_unit * math.cos(angle)
                position[1] += radius * pixel_unit * math.sin(angle)
                copy_glyph.set('position', pkg.Val('vec3', position))
                idf.set_param(copy_glyph, 'guid', str(uuid.uuid5(uuid.NAMESPACE_URL, 'halo-v2/'+name)))
                idf.set_param(copy_glyph, 'eLayer.layer', 38 if effect == 'outline' else 39, 'si32')
                parent['children'].items.insert(0, copy_glyph)
                label = copy.deepcopy(controller)
                label.items[N.PROPS]['name'].value = name
                label.items[N.EVENTS].items = []
                label.items[N.COMMANDS].items = []
                label.items[N.LAYOUT] = U.layout_path(name)
                label.items[N.PROPS].set('colourOverride', U.prop('rgba',
                    '#' + ''.join(f'{value:02x}' for value in tint + (255,))))
                owner.items[N.CHILDREN].items.append(label)
                text_opacity(owner, dial_child, label, name+'_alpha', name, alpha/255.,
                             controller_root=context)
                count += 1
        records.append({'key':key, 'glyph':glyph['name'].value, 'effect_layers':count,
                        'colour':list(colour), 'native_font':layout.DRS_TEXT_STYLE})

    decorate(open_holder.obj, main_root.find('halo_v2_drs_open_label').obj,
             N.child(controls, 't_drs_open_label'), controls, F1PATH+'.halo_v2_ctl',
             world_per_pixel/open_holder.scale[0], 'open',
             all_text_colour or layout.DRS_TEXT_COLOUR,
             outline=True)
    captions = [
        ('text', native, 'bar_status', DRSPATH, 'status'),
        ('distance_text', native, 'distance', DRSPATH, 'distance'),
        ('halo_drs_prompt_text', N.child(native,'halo_drs_prompt_caption'),
         'halo_drs_prompt_text', DRSPATH+'.halo_drs_prompt_caption', 'prompt'),
        ('halo_pit_prompt_text', N.child(native,'halo_pit_prompt_caption'),
         'halo_pit_prompt_text', DRSPATH+'.halo_pit_prompt_caption', 'pit'),
    ]
    for name, owner, label_name, context, key in captions:
        glyph = prompt_root.find(name).obj
        idf.set_param(glyph, 'style', layout.DRS_TEXT_STYLE)
        idf.set_param(glyph, 'textcase', 'upper')
        glyph.set('scale', pkg.Val('vec3', [legacy_text_scale,legacy_text_scale,1.,0.]))
        decorate(prompt_parents[name], glyph, N.child(owner,label_name), owner,
                 context, .0065, key, all_text_colour or layout.DRS_PROMPT_COLOUR)
    tooltip = N.child(native,'tooltip_drs_button')
    for name in ('icon','icon_as_text'):
        N.child(tooltip,name).items[N.PROPS].set('colourOverride', U.prop('rgba',
            '#' + ''.join(f'{value:02x}' for value in layout.DRS_PROMPT_COLOUR)))
    keyboard = prompt_root.find('drs_activate_tooltip_as_label').obj
    idf.set_param(keyboard,'style',layout.DRS_TEXT_STYLE)
    keyboard.set('scale',pkg.Val('vec3',[legacy_text_scale,legacy_text_scale,1.,0.]))
    for glyph_name,binding_name,key in (
            ('drs_activate_button','icon','button'),
            ('drs_activate_tooltip_as_label','icon_as_text','keyboard')):
        decorate(prompt_parents[glyph_name],prompt_root.find(glyph_name).obj,
                 N.child(tooltip,binding_name),tooltip,DRSPATH+'.tooltip_drs_button',
                 .0065,key,all_text_colour or layout.DRS_PROMPT_COLOUR)

    idf.set_param(prompt_root.find('halo_drs_distance_row').obj,'gap',layout.DRS_DISTANCE_GAP*.0065,'fp32')
    idf.set_param(prompt_root.find('halo_drs_prompt_row').obj,'gap',layout.DRS_PROMPT_GAP*.0065,'fp32')
    return {'method':'native eText with crisp core', 'labels':records,
            'mapped_button_binding':True, 'glow_opacity':layout.DRS_LABEL_GLOW_ALPHA/255.}


def drs(archive, reference, scene, f1, dial_child, controls):
    destination = OWN + 'drs_prompt.idf'
    resource, prompt_scene = component(
        archive, reference, 'eaid://ui_package/art/osd/local_halo/status.idf',
        destination, DIAL + 'dial_pit_lane_slider.emb?context=default')
    for name in ('halo_drs_prompt_centre', 'centre_status'):
        point = prompt_scene.scenes[0].root.find(name)
        point.obj.set('position', pkg.Val('vec3',
            [(layout.DRS_CENTRE[0] - 600.) * .0065,
             (170. - layout.DRS_CENTRE[1]) * .0065 + .7, 0., 0.]))
    attach_native(scene, 'dial_pit_lane_slider', destination)

    original = N.child(dial_child, 'drs_and_pit_distance')
    native = pkg.Pkg((ROOT / 'native/reference/drs-template.bin').read_bytes()).root
    children = dial_child.items[N.CHILDREN].items
    children[children.index(original)] = native
    opened = N.child(native, 'halo_drs_open')
    N.set_prop_value(N.child(opened, 'halo_drs_enter'), 'AnimationCurve', layout.DRS_OPEN_CURVE)
    # Keep the rails visible throughout their return sweep. Fade the caption.
    leave=N.child(opened,'halo_drs_leave')
    leave.items[N.LAYOUT]=U.layout_path('halo_v2_drs_open_label_n')
    N.set_prop_value(leave,'AnimationCurve',layout.DRS_CLOSE_CURVE)

    native.items[N.CHILDREN].items.remove(opened)
    opened.items[N.CHILDREN].items = [child for child in N.children(opened)
        if N.name(child) != 'halo_drs_open_text']
    dial_child.items[N.CHILDREN].items.append(opened)
    N.rename_refs(f1, DRSPATH + '.halo_drs_open', F1PATH + '.halo_drs_open')

    removed = [DRSPATH + '.' + N.name(child) for child in N.children(native)
               if N.name(child).startswith('halo_reveal_')]
    removed.append(F1PATH + '.halo_v2_ctl.v_drs_open')
    native.items[N.CHILDREN].items = [child for child in N.children(native)
        if not N.name(child).startswith('halo_reveal_')]
    controls.items[N.CHILDREN].items = [child for child in N.children(controls)
        if N.name(child) != 'v_drs_open']
    remove_signals(f1, removed)

    for old, new in (('halo_v2_drs_open', 'halo_drs_open'),
                     ('halo_v2_drs_pulse', 'halo_drs_open_pulse'),
                     ('halo_v2_drs_content', 'halo_drs_open_content')):
        scene.scenes[0].root.find(old).obj['name'].value = new

    reveal = [node for node in N.children(controls)
              if N.name(node) in {f'x_drs_{side}_{part}'
                                 for side in ('left', 'right') for part in ('win', 'ctr')}]
    if len(reveal) != 4:
        raise ValueError('Expected paired DRS window/counter channels')
    for node in reveal:
        # Native reveal XAs are signal-driven, as in the tested DRS component.
        N.drop_key(node.items[N.PROPS], 'fraction')
    selector = N.child(native, 'ers_state')
    for event in selector.items[N.EVENTS].items:
        state = event['eventName'].value
        for node in reveal:
            path = F1PATH + '.halo_v2_ctl.' + N.name(node)
            if state == 'drs_live':
                event['signals'].items.extend([
                    U.sig(path, 'goToFraction', state, {'value': 0.}),
                    U.sig(path, 'playToFraction', state,
                          {'curveName': N.djb2(layout.DRS_OPEN_CURVE), 'value': 1.})])
            elif state == 'invalid':
                event['signals'].items.append(U.sig(
                    path, 'goToFraction', state, {'value': 0.}))
            else:
                event['signals'].items.append(U.sig(
                    path, 'playToFraction', state,
                    {'curveName': N.djb2(layout.DRS_CLOSE_CURVE), 'value': 0.}))
    sweep = drs_sweep(archive, reference, scene, native, selector, dial_child, controls)
    typography = drs_typography(scene, prompt_scene, native, controls, dial_child)
    refresh_scene(prompt_scene)
    archive.set_frag(resource, 0, prompt_scene.to_bytes())
    return {'selector': 'drs_pit_state', 'reveal_channels': 4, 'typography':typography,
            'close_retraction_seconds':layout.DRS_CLOSE_DURATION,'close_fade_target':'caption',
            'prompt_art_centre': list(layout.DRS_CENTRE), 'travelling_highlight': sweep}


def centre_text_readouts(scene, reference, controls=None, ctx=F125):
    """Place live text using measured glyph bounds at the shared art anchors."""
    status = reference.find('eaid://ui_package/art/osd/local_halo/status.idf')
    prototype = idf.Idf(reference.frag_data(status, 0))
    centre = prototype.scenes[0].root.find('halo_drs_prompt_centre').obj
    number, unit = instruments.rpm_labels(11585)
    records = {}
    if controls is not None and layout.STYLE['text_colour'] != '#ffffff':
        colour = '#' + layout.STYLE['text_colour'][1:] + 'ff'
        for name in ('speed', 'stock_speed', 'rpm_value', 'rpm_unit', 'brake_label',
                     'throttle_label', 'special_gear'):
            N.child(controls, 't_' + name).items[N.PROPS].set(
                'colourOverride', U.prop('rgba', colour))
    readouts = [
            ('speed', layout.circle_speed(ctx != F125)), ('rpm_value', number), ('rpm_unit', unit),
            ('brake_label', layout.pedal_label(-1)),
            ('throttle_label', layout.pedal_label(1)), ('special_gear', layout.SPECIAL_GEAR),
            ('drs_open_label', layout.Text(*layout.DRS_CENTRE,layout.DRS_STATUS_TEXT_SIZE))]
    readouts.append(('stock_speed',layout.circle_speed(ctx != F125)))
    readouts.extend((name,spec) for name,spec,_ in layout.circle_readouts(ctx != F125))
    readouts.extend(('wing_'+name,energy_panel.text_anchor(name,ctx != F125)) for name in energy_panel.rows(ctx != F125))
    if ctx != F125:
        readouts.append(('wing_boost',energy_panel.text_anchor('mode')))
        readouts.extend(('boost_text_'+state.lower(),layout.BOOST_STATUS) for state in BOOST_STATES)
        readouts.extend(('overtake_'+state,layout.OVERTAKE_STATUS) for state in ('on','off'))
    readouts.extend((glyph.name, glyph.anchor) for glyph in sectors.glyphs())
    for name, spec in readouts:
        holder = scene.scenes[0].root.find((ctx.prefix + '_') + name + '_n').obj
        glyph = scene.scenes[0].root.find((ctx.prefix + '_') + name).obj
        holder.set('typeName', copy.deepcopy(centre['typeName']))
        for parameter in centre['params'].items:
            key = parameter['name'].value
            if key in ('className', 'centreX', 'centreY', 'centreZ', 'mode'):
                value = parameter['value']
                idf.set_param(holder, key, value.value, value.type)
        x, y = layout.hud_point(spec.x, spec.y)
        holder.set('position', pkg.Val('vec3', [x * .018, -y * .018, 0., 0.]))
        glyph.set('position', pkg.Val('vec3', [0., 0., 0., 0.]))
        records[name] = {'anchor': [spec.x, spec.y],
                         'centre_x': True, 'centre_y': True, 'method': 'native eCentre'}
    return records





def text_opacity(controls, dial_child, controller, name, target, opacity,
                 controller_root=None, ctx=F125):
    """Use native material alpha for text effects, including late attachments."""
    controller_root = controller_root or ctx.path + '.' + ctx.prefix + '_ctl'
    actor = U.node(name, 'UIMO', props=[
        ('ParameterName', U.prop('stri', 'Alpha')),
        ('Value', U.prop('fp32', opacity)),
        ('Cascade', U.prop('bool', True)),
        ('BlendType', U.prop('stri', 'Multiplicative')),
    ], layout=(target,), behav=('NBEL','NBMG','NBOS','NBXA'))
    controls.items[N.CHILDREN].items.append(actor)
    path = controller_root + '.' + name
    for command in dial_child.items[N.COMMANDS].items:
        event = command['commandName'].value
        if event in ('command_vmContextValid','use_dial','show'):
            command['signals'].items.append(U.sig(path,'activateOverride',event))
        elif event in ('hide','disable'):
            command['signals'].items.append(U.sig(path,'deactivateOverride',event))
    U.add_events(controller,U.event('shown',[U.sig(path,'activateOverride','shown')]))


def sector_typography(scene, controls, dial_child, ctx=F125):
    root = scene.scenes[0].root
    prototype = copy.deepcopy(root.find(ctx.prefix).obj)
    prototype.set('children', pkg.Arr([]))
    prototype.set('geoms', pkg.Arr([]))
    prototype.set('anims', pkg.Arr([]))
    prototype.set('position', pkg.Val('vec3', [0.,0.,0.,0.]))
    prototype.set('scale', pkg.Val('vec3', [1.,1.,1.,0.]))
    prototype.set('rotation', pkg.Val('quat', [0.,0.,0.,1.]))
    idf.set_param(prototype, 'isHidden', False, 'bool')

    def transform(name, angle):
        node = copy.deepcopy(prototype)
        node['name'].value = name
        half = -math.radians(angle)/2
        node.set('rotation', pkg.Val('quat', [0.,0.,math.sin(half),math.cos(half)]))
        idf.set_param(node, 'guid', str(uuid.uuid5(uuid.NAMESPACE_URL, 'halo-v2/'+name)))
        return node

    for glyph in sectors.glyphs():
        name = (ctx.prefix + '_') + glyph.name
        measured = detach_scene(root, name + '_n')
        outer_angle, scale_x, scale_y, inner_angle = sectors.decompose(glyph.basis)
        surface = transform(name + '_surface', outer_angle)
        surface.set('position', copy.deepcopy(measured['position']))
        surface.set('scale', pkg.Val('vec3', [scale_x,scale_y,1.,0.]))
        tangent = transform(name + '_tangent', inner_angle)
        measured.set('position', pkg.Val('vec3', [0.,0.,0.,0.]))
        measured.set('rotation', pkg.Val('quat', [0.,0.,0.,1.]))
        tangent['children'].items = [measured]
        surface['children'].items = [tangent]
        root.find(ctx.prefix).obj['children'].items.append(surface)
        controller = N.child(controls, 't_' + glyph.name)
        glyph_colour = (rgb(layout.STYLE['text_colour']) + (255,)
                        if layout.STYLE['text_colour'] != '#ffffff' else glyph.colour)
        colour = '#' + ''.join(f'{channel:02x}' for channel in glyph_colour)
        controller.items[N.PROPS].set('colourOverride', U.prop('rgba', colour))
        part = 'prefix' if glyph.literal else 'time'
        world_per_pixel = layout.HUD_SCALE*.018
        for index,effect in enumerate(sectors.effects(part,glyph_colour)):
            effect_name = name + f'_light_{index}'
            centre = copy.deepcopy(measured)
            centre['name'].value = effect_name + '_n'
            centre.set('position',pkg.Val('vec3',[effect.x*world_per_pixel,-effect.y*world_per_pixel,0.,0.]))
            scale = measured['scale'].value.copy()
            scale[0] *= effect.scale
            scale[1] *= effect.scale
            centre.set('scale',pkg.Val('vec3',scale))
            idf.set_param(centre,'guid',str(uuid.uuid5(uuid.NAMESPACE_URL,'halo-v2/'+effect_name+'_n')))
            text = centre['children'].items[0]
            text['name'].value = effect_name
            idf.set_param(text,'guid',str(uuid.uuid5(uuid.NAMESPACE_URL,'halo-v2/'+effect_name)))
            layer = idf.Element(measured['children'].items[0]).params.get('eLayer.layer',40)
            idf.set_param(text,'eLayer.layer',layer+effect.layer_offset,'si32')
            tangent['children'].items.append(centre)
            label = copy.deepcopy(controller)
            label.items[N.PROPS]['name'].value = glyph.name + f'_light_{index}_text'
            label.items[N.LAYOUT] = U.layout_path(effect_name)
            tint = '#' + ''.join(f'{channel:02x}' for channel in effect.colour) + 'ff'
            label.items[N.PROPS].set('colourOverride',U.prop('rgba',tint))
            controls.items[N.CHILDREN].items.append(label)
            text_opacity(controls,dial_child,label,glyph.name+f'_light_{index}_alpha',
                         effect_name+'_n',effect.opacity, ctx=ctx)
    sector_appearance(scene,controls,dial_child,prototype,ctx)
    return {'glyphs': 81, 'permanent_white_prefixes': True,
            'separate_colour_targets': True, 'fixed_columns': True,
            'surface': 'projected cylindrical tangents', 'lighting': 'native alpha-capped glow and contrast edge'}


def sector_appearance(scene,controls,dial_child,prototype,ctx):
    """Fade the complete projected time row once per new split publication."""
    parent=scene.scenes[0].root.find(ctx.prefix).obj
    path=ctx.path+'.'+ctx.prefix+'_ctl.'
    for sector in range(1,4):
        key=f'sector_s{sector}'
        name=ctx.prefix+'_'+key+'_times'
        wrapper=copy.deepcopy(prototype)
        wrapper['name'].value=name
        idf.set_param(wrapper,'guid',str(uuid.uuid5(uuid.NAMESPACE_URL,'halo-v2/'+name)))
        row_prefix=ctx.prefix+'_'+key+'_'
        children=parent['children'].items
        moved=[child for child in children if child['name'].value.startswith(row_prefix)
               and '_prefix_' not in child['name'].value]
        if len(moved)!=24:
            raise ValueError('Sector animation requires all four six-cell time layers')
        wrapper['children'].items=moved
        parent['children'].items=[child for child in children if child not in moved]+[wrapper]
        fade=key+'_enter'
        ready=key+'_ready'
        pulse=key+'_pulse'
        def restart(event):
            return [U.sig(path+fade,'deactivateOverride',event),
                    U.sig(path+fade,'activateOverride',event)]
        actor=U.node(fade,'UIMO',props=[
            ('ParameterName',U.prop('stri','Alpha')),
            ('Value',U.prop('fp32',1.)),('StartingValue',U.prop('fp32',layout.SECTOR_FADE_START)),
            ('Cascade',U.prop('bool',True)),('BlendType',U.prop('stri','Multiplicative')),
            ('AnimationCurve',U.prop('stri',layout.SECTOR_FADE_CURVE)),
            ('AnimateToValue',U.prop('bool',True)),
        ],layout=(name,),behav=('NBEL','NBMG','NBOS','NBXA'),events=[
            U.event('overrideComplete',[U.sig(path+fade,'deactivateOverride','overrideComplete')])])
        phase=U.node(pulse,'SVCD',props=[('value',U.prop('bool',True)),
            ('dbEntry',U.prop('stri',f'#view_model_data.hud_halo_v2_sector_s{sector}_pulse'))],
            events=[U.event('yes',restart('yes')),U.event('no',restart('no'))])
        gate=U.node(ready,'SVCD',props=[('value',U.prop('bool',True)),
            ('dbEntry',U.prop('stri',f'#view_model_data.hud_halo_v2_sector_s{sector}_ready'))],events=[
            U.event('yes',[U.sig(path+pulse,'register','yes'),U.sig(path+pulse,'query','yes')]),
            U.event('no',[U.sig(path+pulse,'unregister','no'),U.sig(path+fade,'deactivateOverride','no')])])
        controls.items[N.CHILDREN].items.extend([actor,phase,gate])
        for command in dial_child.items[N.COMMANDS].items:
            event=command['commandName'].value
            if event in ('command_vmContextValid','use_dial','show'):
                command['signals'].items.extend([U.sig(path+ready,'register',event),U.sig(path+ready,'query',event)])
            elif event in ('hide','disable'):
                command['signals'].items.extend([U.sig(path+ready,'unregister',event),
                    U.sig(path+pulse,'unregister',event),U.sig(path+fade,'deactivateOverride',event)])


def gear_transitions(scene, controls, ctx=F125):
    """Restore the legacy selected-digit fade beneath each visibility gate."""
    root = scene.scenes[0].root
    prototype = root.find(ctx.prefix).obj
    path = ctx.path + ('.' + ctx.prefix + '_ctl.')
    for gear in range(1, 9):
        name = f'{ctx.prefix}_gear_{gear}_active'
        glyph = detach_scene(root, name)
        glyph['name'].value = name + '_glyph'
        gate = copy.deepcopy(prototype)
        gate['name'].value = name
        gate.set('children', pkg.Arr([glyph]))
        gate.set('geoms', pkg.Arr([]))
        gate.set('anims', pkg.Arr([]))
        gate.set('position', pkg.Val('vec3', [0., 0., 0., 0.]))
        gate.set('scale', pkg.Val('vec3', [1., 1., 1., 0.]))
        gate.set('rotation', pkg.Val('quat', [0., 0., 0., 1.]))
        idf.set_param(gate, 'guid', str(uuid.uuid5(uuid.NAMESPACE_URL, 'halo-v2/' + name)))
        root.find(ctx.prefix).obj['children'].items.append(gate)

        fade = f'gear_{gear}_enter'
        actor = U.node(fade, 'UIMO', props=[
            ('ParameterName', U.prop('stri', 'Alpha')),
            ('Value', U.prop('fp32', 1.)),
            ('StartingValue', U.prop('fp32', layout.GEAR_FADE_START)),
            ('Cascade', U.prop('bool', True)),
            ('BlendType', U.prop('stri', 'Multiplicative')),
            ('AnimationCurve', U.prop('stri', 'generic_fade_on')),
            ('AnimateToValue', U.prop('bool', True)),
        ], layout=(name + '_glyph',), behav=('NBEL', 'NBMG', 'NBOS', 'NBXA'))
        controls.items[N.CHILDREN].items.append(actor)
        visible = N.child(controls, f'v_gear_{gear}_active')
        U.add_events(visible,
            U.event('shown', [U.sig(path + fade, 'activateOverride', 'shown')]),
            U.event('hidden', [U.sig(path + fade, 'deactivateOverride', 'hidden')]))
    return {'selected_digits': 8, 'curve': 'generic_fade_on',
            'duration_seconds': layout.GEAR_FADE_DURATION,
            'starting_alpha': layout.GEAR_FADE_START,
            'visibility_owner': 'parent gate', 'animated_target': 'glyph child'}


def rpm_readout(scene, reference, controls, dial_child, ctx=F125):
    """Measure the live number and native-font unit together, including bloom."""
    prototype = idf.Idf(reference.frag_data(reference.find(
        'eaid://ui_package/art/osd/local_halo/status.idf'), 0))
    centre = prototype.scenes[0].root.find('centre_status').obj
    stack = prototype.scenes[0].root.find('halo_drs_distance_row').obj
    root = scene.scenes[0].root
    number = detach_scene(root, (ctx.prefix + '_rpm_value_n'))
    unit = detach_scene(root, (ctx.prefix + '_rpm_unit_n'))
    world_per_pixel = layout.HUD_SCALE * .018

    def group(source, name):
        result = copy.deepcopy(source)
        result['name'].value = name
        result.set('children', pkg.Arr([]))
        result.set('geoms', pkg.Arr([]))
        result.set('anims', pkg.Arr([]))
        result.set('position', pkg.Val('vec3', [0., 0., 0., 0.]))
        result.set('scale', pkg.Val('vec3', [1., 1., 1., 0.]))
        result.set('rotation', pkg.Val('quat', [0., 0., 0., 1.]))
        idf.set_param(result, 'guid', str(uuid.uuid5(uuid.NAMESPACE_URL, 'halo-v2/' + name)))
        return result

    holder = group(centre, (ctx.prefix + '_rpm_readout'))
    idf.set_param(holder, 'centreY', False, 'bool')
    at = layout.rpm_position()
    holder.set('position', pkg.Val('vec3',
        [(at.x - layout.CX) * world_per_pixel,
         -(at.y - layout.CY) * world_per_pixel, 0., 0.]))
    rotation = -math.radians(layout.angle(at.x)) / 2
    holder.set('rotation', pkg.Val('quat', [0., 0., math.sin(rotation), math.cos(rotation)]))
    row = group(stack, (ctx.prefix + '_rpm_row'))
    idf.set_param(row, 'gap', layout.RPM_UNIT_GAP * world_per_pixel, 'fp32')
    idf.set_param(row, 'stackerType', 'l')
    idf.set_param(row, 'useStaticGap', False, 'bool')
    number.set('position', pkg.Val('vec3', [0., 0., 0., 0.]))
    number.set('rotation', pkg.Val('quat', [0., 0., 0., 1.]))
    baseline = (layout.RPM_NUMBER_SIZE - layout.UNIT_LABEL_SIZE) * .336 * world_per_pixel
    unit.set('position', pkg.Val('vec3', [0., -baseline, 0., 0.]))
    unit.set('rotation', pkg.Val('quat', [0., 0., 0., 1.]))

    unit_label = N.child(controls, 't_rpm_unit')
    unit_label.items[N.PROPS].set('colourOverride', U.prop('rgba',
        '#' + ''.join(f'{channel:02x}' for channel in material.UNIT_TEXT)))
    counts = {}
    for part, measured, rings, samples, colour in (
            ('value', number, layout.RPM_NUMBER_GLOW_RINGS,
             layout.RPM_NUMBER_GLOW_SAMPLES, material.RPM_NUMBER_GLOW),
            ('unit', unit, layout.RPM_LABEL_GLOW_RINGS,
             layout.RPM_LABEL_GLOW_SAMPLES, material.UNIT_GLOW)):
        glyph = measured['children'].items[0]
        label = N.child(controls, 't_rpm_' + part)
        count = 0
        for radius, alpha in rings:
            local_radius = radius * world_per_pixel / measured['scale'].value[0]
            for index in range(samples):
                name = f'{ctx.prefix}_rpm_{part}_glow_{count:02d}'
                copy_glyph = copy.deepcopy(glyph)
                copy_glyph['name'].value = name
                angle = index * math.tau / samples
                copy_glyph.set('position', pkg.Val('vec3',
                    [local_radius * math.cos(angle), local_radius * math.sin(angle), 0., 0.]))
                idf.set_param(copy_glyph, 'guid', str(uuid.uuid5(uuid.NAMESPACE_URL, 'halo-v2/' + name)))
                idf.set_param(copy_glyph, 'eLayer.layer', 39, 'si32')
                measured['children'].items.insert(0, copy_glyph)
                controller = copy.deepcopy(label)
                controller.items[N.PROPS]['name'].value = f't_rpm_{part}_glow_{count:02d}'
                controller.items[N.LAYOUT] = U.layout_path(name)
                controller.items[N.PROPS].set('colourOverride', U.prop('rgba',
                    '#' + ''.join(f'{channel:02x}' for channel in colour + (255,))))
                controls.items[N.CHILDREN].items.append(controller)
                fade_name = f'rpm_{part}_glow_alpha_{count:02d}'
                text_opacity(controls,dial_child,controller,fade_name,name,alpha/255., ctx=ctx)
                count += 1
        counts[part] = count
    row['children'].items = [number, unit]
    holder['children'].items = [row]
    root.find(ctx.prefix).obj['children'].items.append(holder)
    return {'method': 'native measured horizontal row',
            'gap_art_pixels': layout.RPM_UNIT_GAP,
            'glow_glyphs': counts['unit'], 'number_glow_glyphs': counts['value'],
            'style': 'OSD_24_bold',
            'glow_opacity': 'native Alpha material override'}


def apply(scene_archive, template_archive, ctx=F125):
    reference = erpw.Erp(ROOT / 'native/reference/native-controls.erpk')
    scene_resource = scene_archive.find(ctx.main)
    scene = idf.Idf(scene_archive.frag_data(scene_resource, 0))
    template_resource = template_archive.find(TEMPLATE)
    template = pkg.Pkg(template_archive.frag_data(template_resource, 0))
    f1 = next(node for node in walk(template.root) if N.name(node) == ctx.template)
    dial_child = N.child(N.child(f1, 'osd_visibility_option'), ctx.child)
    controls = N.child(dial_child, (ctx.prefix + '_ctl'))

    # Custom geometry/material/texture dependencies retain their original names.
    # Base game resources are cloned only into this addon's component namespace.
    copied = []
    for resource in reference.res:
        if resource.name.startswith(('eaid://ui_package/art/osd/local_halo/',
                                     'eaid://ui_package/art/osd/local_halo_')) or any(
                    marker in resource.name for marker in ('/halo_accel_fill?', '/halo_br_fi?')):
            if resource.name.endswith('/status.idf') or '_mask.tif' in resource.name:
                continue
            if not any(r.name == resource.name for r in scene_archive.res):
                scene_archive.res.append(copy.deepcopy(resource))
                copied.append(resource.name)
    readouts = centre_text_readouts(scene, reference, controls, ctx=ctx)
    sector_layout = sector_typography(scene, controls, dial_child, ctx=ctx)
    rpm = rpm_readout(scene, reference, controls, dial_child, ctx=ctx)
    tip=rpm_tip_motion(scene_archive,reference,scene,ctx)
    gears = gear_transitions(scene, controls, ctx=ctx)
    pedals(scene_archive, reference, scene, ctx=ctx)
    front = 'eaid://ui_package/art/osd/textures/hud/'+ctx.prefix+'_wing_energy_front.tif'
    for name in ('wing_energy_fill','wing_energy_glow'):
        soft_mask(scene_archive, reference, scene, ctx.prefix+'_'+name+'_win', front)
        for part in ('win','ctr'):
            N.child(controls,'x_'+name+'_'+part).items[N.PROPS].set('fraction',U.prop('fp32',0.,'ers_stored'))
    for name in energy_panel.rows(ctx != F125):
        if name == 'charge':
            continue
        colour = energy_panel.GREEN if name.startswith('harvest') else energy_panel.ICE
        N.child(controls,'t_wing_'+name).items[N.PROPS].set('colourOverride',
            U.prop('rgba','#%02x%02x%02xff' % colour))
    battery = battery_colours(scene_archive, reference, scene, controls, dial_child, ctx=ctx)
    if ctx == F125:
        status = drs(scene_archive, reference, scene, f1, dial_child, controls)
    else:
        from f126_interop import straight_mode
        status = straight_mode(scene_archive, reference, scene, dial_child, controls, ctx)
    refresh_scene(scene)
    N.fix_ids(f1)
    scene_archive.set_frag(scene_resource, 0, scene.to_bytes())
    template_archive.set_frag(template_resource, 0, template.to_bytes())
    return {'custom_dependencies': copied, 'battery': battery, 'drs': status,
            'readouts': readouts, 'rpm_readout': rpm, 'rpm_tip':tip, 'gear_transitions': gears,
            'sectors': sector_layout,
            'legacy_to_composed_scale': layout.HUD_SCALE * .018 / .0065}
