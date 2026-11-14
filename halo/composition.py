"""Generate the native composition and preview from shared sprite positions."""
import json
from pathlib import Path
from PIL import Image
from .asset_cache import AssetCache
from tools.build_inputs import artwork_source_fingerprint
from .tuning import values
from . import artwork as art, layout as geo
from . import feature_assets, instruments, sectors, drs_motion, rpm_mask

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "view_model_data.hud_halo_v2_"

def write():
    sprites = {}
    if geo.STYLE!=values():
        raise RuntimeError('Style changed during startup. Retry the build.')
    cache=AssetCache(ROOT,artwork_source_fingerprint(),geo.STYLE)
    size_ratio = geo.HUD_SCALE / 0.30

    def dependencies(name):
        if name=='base':
            return ('gears_size','gears_weight','gears_colour','rpm_width')
        if name.startswith('battery_'):
            return ('battery_width','battery_height','battery_y')
        if name in ('rpm_fill','rpm_fill_mask'):
            return ('rpm_width',)
        return ()

    def sprite(name, producer, resolution=1, resample=Image.Resampling.LANCZOS):
        def create():
            final=art.finish(producer(),resolution,resample)
            box=final.getbbox()
            if not box:
                raise ValueError('Empty sprite '+name)
            left,top,right,bottom=box
            right+=(4-(right-left)%4)%4
            bottom+=(4-(bottom-top)%4)%4
            final.crop((left,top,right,bottom)).save(ROOT/'art'/(name+'.png'))
            return {'png':'art/'+name+'.png',
                    'bounds':geo.hud_bounds([v/resolution for v in (left,top,right,bottom)])}
        sprites[name]=cache.get(name,dependencies(name),create)

    def raw_sprite(name,producer,bounds):
        def create():
            producer().save(ROOT/'art'/(name+'.png'))
            return {'png':'art/'+name+'.png','bounds':bounds}
        sprites[name]=cache.get(name,dependencies(name),create)

    sprite('base',art.base,geo.BASE_TEXTURE_RESOLUTION)
    sprite('rpm_fill',art.rpm_fill)
    # The composer encodes these full-frame textures for the native input masks.
    # Their resources are consumed by native_interop, with no extra scene quads.
    half_span = geo.PEDAL_MASK_SPAN / 2
    for side, name in ((-1, "brake"), (1, "accelerate")):
        mask_name = "pedal_" + name + "_mask"
        raw_sprite(mask_name,lambda:feature_assets.pedal_mask(side),
            geo.hud_bounds([geo.CX-half_span,geo.CY-half_span,geo.CX+half_span,geo.CY+half_span]))


    elements = [{"kind": "sprite", "id": "base", "sprite": "base", "layer": 20}]
    preview = {"game.speed_str": "250", "game.revs": .89, "game.ers_stored": .75,
               "game.has_ers": True, PREFIX + "rpm": "11585",
               PREFIX + "drs_reveal": 0.0, PREFIX + "drs_visible": False}
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
        ("speed", geo.SPEED, {"game": "speed_str"}, 52),
        ("rpm_value", number_at, {"view_model": PREFIX + "rpm"}, 22),
        ("rpm_unit", unit_at, {"literal": "RPM"}, 12),
        ("brake_label", geo.pedal_label(-1), {"literal": "BRAKE"}, 20),
        ("throttle_label", geo.pedal_label(1), {"literal": "THROTTLE"}, 20),
        ("special_gear", geo.SPECIAL_GEAR, {"view_model": PREFIX + "special_gear"}, 12),
    ):
        element={
            "kind":"text","id":name,"style":"OSD_24_bold","align":"centre",
            "box":box*size_ratio,"cap_height":round(spec.size*.672*geo.HUD_SCALE,6),
            "at":geo.hud_point(spec.x,spec.y),
            "rot":spec.rotation,"layer":26,
        }
        if "literal" in value:
            element["literal"]=value["literal"]
        else:
            element["value"]=value
        elements.append(element)

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
                            "layer":27 if part=="bolt" else 24 if part=="housing" else 25})
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
                  "cap_height":round(geo.DRS_STATUS_TEXT_SIZE*.672*geo.HUD_SCALE,6),
                  "at":geo.hud_point(*geo.DRS_CENTRE),"literal":"DRS OPEN","layer":27})
    elements.append({
        "kind":"group","id":"drs_open",
        "visible":{"view_model":PREFIX+"drs_visible"},
        "children":[{"kind":"group","id":"drs_pulse",
                     "children":[{"kind":"group","id":"drs_content","children":rails}]}],
    })
    preview[PREFIX + "special_gear"] = ""
    record = {"prefix": "halo_v2", "dial": "f1_25", "stock": "hide", "spectator": False,
              "box": geo.hud_bounds([65, 0, 1100, geo.HUD_BOX_BOTTOM]),
              "sprites": sprites, "elements": elements,
              "editor": {"preview": preview}}
    from .f126 import record_for_2026
    records = {"glass_dial": record, "glass_dial_26": record_for_2026(record)}
    (ROOT / "registry" / "hud.json").write_text(
        json.dumps({"hud.element": records}, indent=2) + "\n",
        encoding="utf-8")
    cache.save()
    return record

def preview(record):
    """Render shared artwork with sample inputs for offline inspection."""
    from . import preview_instruments
    image = preview_instruments.render(preview_instruments.State(
        speed=250, rpm=11585, gear=6, throttle=1., brake=0.,
        charge=.75, drs="distance", drs_distance=100))
    image.save(ROOT / "design/core-preview-transparent.png")
    background = Image.new("RGBA", image.size, (31, 47, 57, 255))
    background.alpha_composite(image)
    background.convert("RGB").save(ROOT / "design/core-preview.png")
