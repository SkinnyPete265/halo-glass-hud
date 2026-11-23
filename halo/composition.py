"""Generate the native dial records and in-game editor assets."""
import json
from pathlib import Path
from PIL import Image, ImageChops
from .asset_cache import AssetCache
from tools.build_inputs import artwork_source_fingerprint
from .tuning import values
from . import artwork as art, layout as geo
from . import energy_panel, feature_assets, instruments, sectors, drs_motion, rpm_mask

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "view_model_data.hud_halo_v2_"
STABLE_BASE_CROP = (27, 0, 3755,
                    2028 + round(geo.ARTWORK_TOP_PADDING * geo.BASE_TEXTURE_RESOLUTION))


def crop_sprite(name, final):
    """Return the source image and crop used for one composed sprite."""
    if name == 'base':
        bounds = final.getchannel('A').getbbox()
        if bounds is None:
            raise ValueError('Empty sprite base')
        left, top, right, bottom = STABLE_BASE_CROP
        if (final.width >= right and final.height >= bottom and
                bounds[0] >= left and bounds[1] >= top and
                bounds[2] <= right and bounds[3] <= bottom):
            return final, STABLE_BASE_CROP

        left, top, bound_right, bound_bottom = bounds
        width = bound_right - left
        height = bound_bottom - top
        right = left + (width + 3) // 4 * 4
        bottom = top + (height + 3) // 4 * 4
        padded_width = max(final.width, right)
        padded_height = max(final.height, bottom)
        if (padded_width, padded_height) != final.size:
            expanded = Image.new('RGBA', (padded_width, padded_height))
            expanded.alpha_composite(final)
            final = expanded
        return final, (left, top, right, bottom)

    bounds = final.getbbox()
    if not bounds:
        raise ValueError('Empty sprite ' + name)
    left, top, right, bottom = bounds
    if name.startswith('lit_') or name in ('white_arc','shoulder_glass'):
        # Leave a transparent BC7 block around the filtered edge.
        left, top, right, bottom = left-4, top-4, right+4, bottom+4
    right += (4 - (right - left) % 4) % 4
    bottom += (4 - (bottom - top) % 4) % 4
    return final, (left, top, right, bottom)

def write():
    sprites = {}
    if geo.STYLE!=values():
        raise RuntimeError('Style changed during startup. Retry the build.')
    cache=AssetCache(ROOT,artwork_source_fingerprint(),geo.STYLE)
    size_ratio = geo.HUD_SCALE / 0.30

    def dependencies(name):
        if name=='base':
            return ('gears_size','gears_weight','gears_colour','gears_x','gears_y',
                    'wing_extension','wing_content_follow','text_size','text_colour','text_glow',
                    'text_glow_strength','text_outline','rpm_width')
        if name.startswith('gear_'):
            return ('wing_extension','wing_content_follow','text_size','text_colour','text_glow','text_glow_strength','text_outline')
        if name.startswith('drs_'):
            return ('wing_extension',)
        if name.startswith('wing_energy'):
            return ('wing_extension','wing_content_follow','hud_size')
        if name.startswith('battery_preview_'):
            return ('battery_width','battery_height','battery_y','battery_blue')
        if name.startswith('battery_'):
            return ('battery_width','battery_height','battery_y')
        if name in ('rpm_fill','rpm_fill_mask'):
            return ('rpm_width','wing_extension','wing_content_follow')
        return ()

    def sprite(name, producer, resolution=2, resample=Image.Resampling.LANCZOS,
               origin=(0.0, 0.0)):
        def create():
            final=art.finish(producer(),resolution,resample)
            final, (left,top,right,bottom) = crop_sprite(name, final)
            final.crop((left,top,right,bottom)).save(ROOT/'art'/(name+'.png'))
            return {'png':'art/'+name+'.png',
                    'bounds':geo.hud_bounds([
                        left / resolution + origin[0],
                        top / resolution + origin[1],
                        right / resolution + origin[0],
                        bottom / resolution + origin[1],
                    ])}
        sprites[name]=cache.get(name,dependencies(name),create)

    def raw_sprite(name,producer,bounds):
        def create():
            producer().save(ROOT/'art'/(name+'.png'))
            return {'png':'art/'+name+'.png','bounds':bounds}
        sprites[name]=cache.get(name,dependencies(name),create)

    sprite('base',art.texture_base,geo.BASE_TEXTURE_RESOLUTION,
           origin=(-geo.WING_TEXTURE_PADDING, -geo.ARTWORK_TOP_PADDING))
    sprite('shoulder_glass',art.shoulder_glass,2,origin=(0.,geo.WHITE_ARC_TOP))
    sprite('white_arc',art.white_arc,art.S,origin=(0.,geo.WHITE_ARC_TOP))
    sprite('rpm_fill',art.rpm_fill)
    # The composer encodes these full-frame textures for the native input masks.
    # Their resources are consumed by native_interop, with no extra scene quads.
    half_span = geo.PEDAL_MASK_SPAN / 2
    for side, name in ((-1, "brake"), (1, "accelerate")):
        mask_name = "pedal_" + name + "_mask"
        raw_sprite(mask_name,lambda:feature_assets.pedal_mask(side),
            geo.hud_bounds([geo.CX-half_span,geo.CY-half_span,geo.CX+half_span,geo.CY+half_span]))


    elements = [{"kind": "sprite", "id": "base", "sprite": "base", "layer": 20}]
    preview = {PREFIX + "kph": "250", PREFIX + "mph": "155", "game.revs": .89, "game.ers_stored": .75,
               "game.has_ers": True, PREFIX + "rpm": "11585",
               PREFIX + "drs_reveal": 0.0, PREFIX + "drs_visible": False}
    elements.append({'kind':'sprite','id':'shoulder_glass','sprite':'shoulder_glass','layer':19})
    elements.append({'kind':'sprite','id':'white_arc','sprite':'white_arc','layer':21})
    pedal_gate = PREFIX+'pedals_stepped'
    preview[pedal_gate] = False
    elements.append({'kind':'group','id':'pedal_gradual',
                     'visible':{'view_model':pedal_gate,'not':True,'default':False},'children':[]})
    banks = []
    for side, name in ((-1,'brake'),(1,'throttle')):
        slats = []
        for index in range(10):
            key = f'lit_{name}_{index+1:02d}'
            sprite(key,lambda side=side,index=index:feature_assets.pedal_slat(side,index))
            slats.append(key)
        banks.append({'kind':'slats','id':name+'_steps','sprites':slats,
                      'show':PREFIX+name+'{nn}','layer':25})
    elements.append({'kind':'group','id':'pedal_stepped','visible':{'view_model':pedal_gate},
                     'children':banks})
    for gear in range(1, 9):
        for selected in (False, True):
            name = f"gear_{gear}_{'active' if selected else 'idle'}"
            sprite(name,lambda:instruments.gear_artwork(gear,selected))
            elements.append({
                "kind": "sprite", "id": name, "sprite": name, "layer": 25,
                "visible": {"view_model": PREFIX + f"gear{gear}",
                            "not": not selected, "default": False}})
        preview[PREFIX + f"gear{gear}"] = gear == 6

    width,height=rpm_mask.window()
    motion=rpm_mask.path()
    elements.append({
        'kind':'gauge','id':'rpm','sprite':'rpm_fill','layer':24,
        'window':[width*geo.HUD_SCALE,height*geo.HUD_SCALE],
        'path':[motion[0],motion[-1]],'value':{'game':'revs'}})
    raw_sprite('rpm_fill_mask',rpm_mask.texture,geo.hud_bounds([0,0,*rpm_mask.TEXTURE_SIZE]))
    number_at,unit_at=instruments.rpm_labels(11585)
    for name, spec, value, box in (
        ("speed", geo.circle_speed(False), {"view_model": PREFIX + "kph"}, 52),
        ("stock_speed", geo.circle_speed(False), {"game": "speed_str"}, 52),
        ("rpm_value", number_at, {"view_model": PREFIX + "rpm"}, 22),
        ("rpm_unit", unit_at, {"literal": "RPM"}, 12),
        ("brake_label", geo.pedal_label(-1), {"literal": "BRAKE"}, 20),
        ("throttle_label", geo.pedal_label(1), {"literal": "THROTTLE"}, 20),
        ("special_gear", geo.SPECIAL_GEAR, {"view_model": PREFIX + "special_gear"}, 12),
    ):
        element={
            "kind":"text","id":name,"style":"OSD_24_bold","align":"centre",
            "box":box*size_ratio,"cap_height":round(spec.size*.672*geo.HUD_SCALE*geo.STYLE['text_size']/100.,6),
            "at":geo.hud_point(spec.x,spec.y),
            "rot":spec.rotation,"layer":26,
        }
        if "literal" in value:
            element["literal"]=value["literal"]
        else:
            element["value"]=value
        if name in ("speed", "stock_speed"):
            element["visible"] = {"view_model": PREFIX+"speed_valid", "not": name=="stock_speed"}
        elements.append(element)

    preview[PREFIX+"speed_valid"] = True
    elements.extend(sectors.elements())
    for glyph in sectors.glyphs():
        if glyph.binding:
            index = int(glyph.name[-1])
            preview[glyph.binding] = '--.---'[index] if '_white_' in glyph.name else ''

    def gauge(name,sprite_name,binding,reverse=False):
        bounds=sprites[sprite_name]["bounds"]
        width=bounds[2]-bounds[0]+2*size_ratio
        height=bounds[3]-bounds[1]+2*size_ratio
        middle=(bounds[1]+bounds[3])/2
        if reverse:
            path=[[bounds[2]+width/2,middle],[bounds[0]+width/2,middle]]
        else:
            path=[[bounds[0]-width/2,middle],[bounds[2]-width/2,middle]]
        return {"kind":"gauge","id":name,"sprite":sprite_name,"layer":26,
                "window":[width,height],"path":path,"value":binding}

    battery=[]
    for part in ('housing','frame','fill','bolt'):
        name="battery_"+part
        if part=="fill":
            # BOX preserves the exact cavity support without resampling rings.
            sprite(name,lambda:feature_assets.battery_layers()[part],geo.BATTERY_TEXTURE_RESOLUTION,resample=Image.Resampling.BOX)
            fill = gauge("battery_charge",name,{"game":"ers_stored"})
            for index, charge in enumerate((0.,1.)):
                edge = geo.hud_point(geo.battery_fill_edge(charge),geo.BATTERY_CENTRE[1])[0]
                fill["path"][index][0] = edge - fill["window"][0] / 2
            battery.append(fill)
        else:
            sprite(name,lambda:feature_assets.battery_layers()[part],geo.BATTERY_TEXTURE_RESOLUTION)
            battery.append({"kind":"sprite","id":name,"sprite":name,
                            "layer":28 if part=="bolt" else 24 if part=="housing" else 27})
    for name, spec, caption in geo.circle_readouts(False):
        readout = energy_panel.text_record(name,spec,72,literal=caption,leaf=name,prefix=PREFIX)
        readout["visible"] = {"view_model": PREFIX+"speed_valid"}
        elements.append(readout)

    sprite('wing_energy_track',energy_panel.track,art.S)
    panel = [{'kind':'sprite','id':'wing_energy_track','sprite':'wing_energy_track','layer':24}]
    left, right = energy_panel.rail_limits()
    window = right - left + 20
    for name, producer, layer in (('wing_energy_glow',energy_panel.rail_glow,25),
                                  ('wing_energy_fill',energy_panel.fill,26)):
        sprite(name,producer,art.S,resample=Image.Resampling.BOX)
        rail = gauge(name,name,{'game':'ers_stored'})
        rail['layer'] = layer
        rail['window'][0] = window * geo.HUD_SCALE
        for end, x in zip(rail['path'],(left,right)):
            end[0] = geo.hud_point(x-window/2,0)[0]
        panel.append(rail)
    raw_sprite('wing_energy_front',lambda:energy_panel.front_mask(window),geo.hud_bounds([0,0,1024,8]))
    panel.extend(energy_panel.readouts(False,PREFIX))
    elements.append({'kind':'group','id':'wing_energy','visible':{'game':'has_ers'},'children':panel})
    preview.update({PREFIX+key:value for key,value in {
        'charge':'75%', 'mode':'HOTLAP', 'flow':'DEPLOYING',
        'deploy_kw':'116','harvest_kw':'22'}.items()})
    # These two standalone assets are redirected only into the editor preview
    # during runtime preparation. Bake its 75% battery tint without changing
    # either game's live material or native colour animation.
    for part in ('frame', 'fill'):
        name = 'battery_preview_' + part
        layer = feature_assets.battery_layers()[part]
        tint = Image.new('RGBA', layer.size, instruments.battery_colour(.75,part) + (255,))
        producer = lambda layer=layer, tint=tint: ImageChops.multiply(layer, tint)
        if part == 'fill':
            sprite(name, producer, geo.BATTERY_TEXTURE_RESOLUTION,
                   resample=Image.Resampling.BOX)
        else:
            sprite(name, producer, geo.BATTERY_TEXTURE_RESOLUTION)
    elements.append({"kind":"group","id":"battery",
                     "visible":{"game":"has_ers"},"children":battery})

    rails=[]
    for side in ("left","right"):
        name="drs_"+side
        sprite(name,lambda:feature_assets.drs_side(side))
        rails.append(gauge(name,name,{"view_model":PREFIX+"drs_reveal"},side=="left"))
    for side, sign in (("left", -1), ("right", 1)):
        name = "drs_sweep_" + side
        sprite(name,lambda:drs_motion.side_surface(side))
        bounds = sprites[name]["bounds"]
        middle_y = (bounds[1] + bounds[3]) / 2
        width = drs_motion.WINDOW_WIDTH * geo.HUD_SCALE
        height = bounds[3] - bounds[1] + 4 * size_ratio
        path = [geo.hud_point(geo.CX + sign * drs_motion.window_centre(phase), 0)[0]
                for phase in (0., 1.)]
        rails.append({
            "kind": "gauge", "id": name, "sprite": name, "layer": 28,
            "window": [width, height],
            "path": [[x, middle_y] for x in path],
            "value": {"view_model": PREFIX + "drs_sweep"},
        })
        mask_name = name + "_mask"
        raw_sprite(mask_name,lambda:drs_motion.mask_texture(side),geo.hud_bounds([0,0,256,8]))
    preview[PREFIX + "drs_sweep"] = 0.0
    rails.append({"kind":"text","id":"drs_open_label","style":geo.DRS_TEXT_STYLE,
                  "align":"centre","box":120*size_ratio,
                  "cap_height":round(geo.DRS_STATUS_TEXT_SIZE*.672*geo.HUD_SCALE*geo.STYLE['text_size']/100.,6),
                  "at":geo.hud_point(*geo.DRS_CENTRE),"literal":"DRS OPEN","layer":27})
    elements.append({
        "kind":"group","id":"drs_open",
        "visible":{"view_model":PREFIX+"drs_visible"},
        "children":[{"kind":"group","id":"drs_pulse",
                     "children":[{"kind":"group","id":"drs_content","children":rails}]}],
    })
    preview[PREFIX + "special_gear"] = ""
    record = {"prefix": "halo_v2", "dial": "f1_25", "stock": "hide", "spectator": False,
              "box": geo.hud_bounds([max(0,2*geo.CX-geo.WING_EFFECT_END-11),
                                     min(-geo.ARTWORK_TOP_PADDING,geo.WHITE_ARC_TOP),
                                     geo.WING_EFFECT_END+11, geo.HUD_BOX_BOTTOM]),
              "sprites": sprites, "elements": elements,
              "editor": {"preview": preview}}
    for row, states in (('boost', ('dim','ready','active')), ('overtake', ('dim','active'))):
        for state in states:
            sprite(f'band_{row}_{state}',lambda row=row,state=state:feature_assets.status_band(row,state))
    from .f126 import record_for_2026
    records = {"glass_dial": record, "glass_dial_26": record_for_2026(record)}
    (ROOT / "registry" / "hud.json").write_text(
        json.dumps({"hud.element": records}, indent=2) + "\n",
        encoding="utf-8")
    cache.save()
    return record
