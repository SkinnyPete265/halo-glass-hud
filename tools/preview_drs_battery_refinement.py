"""Preview native DRS text and compare the old/new battery clip mapping."""
from pathlib import Path
import json
import sys
from PIL import Image, ImageChops, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import artwork as art, layout as geo, material as mat, feature_assets
from halo import preview_instruments as hud


def battery(charge,previous=False):
    base=ROOT/'build/source-checkpoints/before-drs-battery-refinement' if previous else ROOT
    record=json.loads((base/'registry/hud.json').read_text())['hud.element']['glass_dial']
    group=next(item for item in record['elements'] if item['id']=='battery')
    fill=next(item for item in group['children'] if item['id']=='battery_charge')
    sprite=record['sprites']['battery_fill']
    bounds=[value/geo.HUD_SCALE+origin for value,origin in zip(sprite['bounds'],(geo.CX,geo.CY,geo.CX,geo.CY))]
    raw=Image.open(base/sprite['png']).convert('RGBA')
    layer=art.canvas()
    texture=raw.resize((round((bounds[2]-bounds[0])*mat.S),round((bounds[3]-bounds[1])*mat.S)),Image.Resampling.BILINEAR)
    layer.alpha_composite(texture,(round(bounds[0]*mat.S),round(bounds[1]*mat.S)))
    full=layer.getchannel('A')
    position=fill['path'][0][0]+charge*(fill['path'][1][0]-fill['path'][0][0])
    edge=(position+fill['window'][0]/2)/geo.HUD_SCALE+geo.CX
    row=Image.new('L',(layer.width,1))
    values=[float((x+.5)/mat.S < edge) for x in range(row.width)]
    row.putdata([round(255*value*value*(3.-2.*value)) for value in values])
    alpha=ImageChops.multiply(full,row.resize(layer.size))
    layer.putalpha(alpha)
    y=round(geo.BATTERY_CENTRE[1]*mat.S)
    denominator=sum(full.crop((0,y,full.width,y+1)).getdata())
    fraction=sum(alpha.crop((0,y,alpha.width,y+1)).getdata())/denominator
    colour=Image.new('RGBA',layer.size,hud.battery_colour(charge)+(255,))
    layer=ImageChops.multiply(layer,colour)
    layers=feature_assets.battery_layers()
    image=layers['housing'].copy()
    image.alpha_composite(ImageChops.multiply(layers['frame'],colour))
    image.alpha_composite(layer)
    image.alpha_composite(layers['bolt'])
    crop=tuple(round(value*mat.S) for value in (geo.CX-36,geo.BATTERY_CENTRE[1]-16,geo.CX+36,geo.BATTERY_CENTRE[1]+16))
    return image.crop(crop).resize((360,160),Image.Resampling.LANCZOS),fraction


def main():
    sheet=Image.new('RGB',(1000,805),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    for x,title in ((126,'Previous in-game mapping'),(570,'Cavity-based mapping')):
        draw.text((x,14),title,font=mat.typeface(23,600),fill=mat.WHITE)
    ratios={}
    for index,charge in enumerate((1.,.97,.95,.90)):
        y=58+index*173
        draw.text((15,y+57),f'{charge:.0%}',font=mat.typeface(23,600),fill=mat.WHITE)
        for x,old in ((126,True),(570,False)):
            icon,fraction=battery(charge,old)
            sheet.paste(icon,(x,y),icon.getchannel('A'))
            ratios.setdefault(str(charge),{})['previous' if old else 'corrected']=fraction
    draw.text((16,768),'Steady-charge clip simulation. The smooth retarget animation uses the same charge mapping.',
              font=mat.typeface(17,500),fill=(175,201,217))
    sheet.save(ROOT/'design/battery-fill-range-preview.png')
    assert ratios['0.95']['previous']>.995
    assert .93<ratios['0.95']['corrected']<.97

    capture=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    state=hud.State(speed=279,rpm=11249,gear=7,throttle=.7,charge=.95,drs='open',
                    sector_times=('29.531','19.094','33.366'),sector_colours=('yellow','yellow','purple'))
    Image.alpha_composite(capture,hud.render(state)).convert('RGB').save(ROOT/'design/drs-battery-refinement-gameplay.png')
    panel=Image.new('RGB',(1000,434),(24,39,49))
    draw=ImageDraw.Draw(panel)
    for index,(title,drs) in enumerate((('Distance','distance'),('Available','ready'),('Open','open'))):
        y=15+index*125
        image=art.canvas()
        hud.draw_drs(image,hud.State(drs=drs,drs_distance=280))
        crop=image.crop(tuple(round(value*mat.S) for value in (geo.CX-94,geo.DRS_CENTRE[1]-18,geo.CX+94,geo.DRS_CENTRE[1]+18)))
        draw.text((20,y+26),title,font=mat.typeface(23,600),fill=mat.WHITE)
        panel.paste(crop,(280,y),crop.getchannel('A'))
    draw.text((20,403),'Native font is OSD_24_bold. This offline preview uses the bundled Saira approximation.',
              font=mat.typeface(17,500),fill=(175,201,217))
    panel.save(ROOT/'design/drs-native-text-preview.png')
    (ROOT/'build/drs-battery-refinement-preview.json').write_text(json.dumps(ratios,indent=2)+'\n')
    print(json.dumps(ratios,indent=2))


if __name__=='__main__':
    main()
