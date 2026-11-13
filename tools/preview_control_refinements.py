"""Compare the proposed white prompts, rounded battery and GEARS caption."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import layout as geo, material as mat, preview_instruments as hud

BASELINE=ROOT/'build/source-checkpoints/before-white-prompts-battery-direct'


def main():
    states={
        'distance':hud.State(drs='distance',drs_distance=280,charge=.95),
        'ready':hud.State(drs='ready',charge=.125),
        'open':hud.State(drs='open',charge=.30),
    }
    current={name:hud.render(state) for name,state in states.items()}
    previous={name:Image.open(BASELINE/(name+'.png')).convert('RGBA') for name in states}
    board=Image.new('RGB',(1240,940),(23,37,47))
    draw=ImageDraw.Draw(board)
    font=lambda size:mat.typeface(size,600)
    draw.text((30,15),'Installed',font=font(24),fill=mat.WHITE)
    draw.text((650,15),'Proposed',font=font(24),fill=mat.WHITE)
    samples=[
        ('Distance on a bright background','distance',(geo.CX-105,geo.DRS_CENTRE[1]-20,geo.CX+105,geo.DRS_CENTRE[1]+20),2.,(208,222,229)),
        ('Ready prompt','ready',(geo.CX-105,geo.DRS_CENTRE[1]-20,geo.CX+105,geo.DRS_CENTRE[1]+20),2.,(48,65,77)),
        ('Battery at 95%','distance',(geo.CX-37,geo.BATTERY_CENTRE[1]-16,geo.CX+37,geo.BATTERY_CENTRE[1]+16),4.,(34,51,62)),
        ('Battery at 12.5%','ready',(geo.CX-37,geo.BATTERY_CENTRE[1]-16,geo.CX+37,geo.BATTERY_CENTRE[1]+16),4.,(34,51,62)),
        ('GEARS caption','distance',(855,geo.top(902.5)-1,953,geo.top(902.5)+51),3.,(34,51,62)),
    ]
    for index,(title,name,box,scale,background) in enumerate(samples):
        y=(53,185,317,497,677)[index]
        for x,images in ((30,previous),(650,current)):
            draw.text((x,y),title,font=font(17),fill=(186,211,226))
            crop=images[name].crop(tuple(round(v) for v in box))
            crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
            tile=Image.new('RGBA',crop.size,background+(255,))
            tile.alpha_composite(crop)
            board.paste(tile.convert('RGB'),(x,y+29))
    draw.text((30,910),'Enlarged offline comparison. Native font rendering and motion need in-game confirmation.',
              font=mat.typeface(16,500),fill=(166,192,207))
    destination=ROOT/'design/control-refinements-preview.png'
    board.save(destination)
    current['distance'].save(ROOT/'design/control-refinements-hud.png')
    print(destination)

if __name__=='__main__':
    main()
