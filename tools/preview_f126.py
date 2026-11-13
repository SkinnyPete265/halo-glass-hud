"""Render the 2026 base-port states with the shared instrument artwork."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import artwork as art, layout as geo, material as mat, feature_assets, drs_motion
from halo import preview_instruments as render
from halo.f126 import BOOST_STATES


def frame(state,sm,overtake,boost):
    image=render.static_base().copy()
    render.sectors.draw(image,state.sector_times,state.sector_colours)
    render.draw_pedals(image,state)
    render.draw_pedal_labels(image)
    render.draw_battery(image,state.charge)
    render.draw_gears(image,state)
    art.label(image,geo.SPEED,str(state.speed),weight=650)
    render.draw_rpm(image,state)
    if sm=='open':
        image.alpha_composite(feature_assets.drs_rails())
        drs_motion.draw(image,.60)
        feature_assets.drs_text(image,geo.DRS_CENTRE,'SM OPEN',colour=geo.DRS_TEXT_COLOUR,outline=True)
    elif sm=='distance':
        feature_assets.drs_text(image,geo.DRS_CENTRE,'SM 300M')
    else:
        feature_assets.drs_text(image,(geo.CX+10,geo.DRS_CENTRE[1]),'SM')
        draw=ImageDraw.Draw(image)
        x,y=geo.CX-23,geo.DRS_CENTRE[1]
        draw.line([((x-5)*art.S,(y+4)*art.S),(x*art.S,(y-5)*art.S),
                   ((x+5)*art.S,(y+4)*art.S),((x-5)*art.S,(y+4)*art.S)],
                  fill=(235,247,255),width=max(1,round(art.S)))
    x=335.
    for offset,text in ((50.,'OVERTAKE ON' if overtake else 'OVERTAKE OFF'),
                        (76.,BOOST_STATES[boost])):
        art.label(image,geo.Text(x,geo.top(x)+offset,13.,-16.),text,color=mat.UNIT_TEXT)
    return art.finish(image)


def main():
    cases=[
        ('Straight Mode approach',render.State(speed=180,rpm=9800,gear=4,charge=.75), 'distance',False,'eAvailable'),
        ('Straight Mode available',render.State(speed=220,rpm=10900,gear=5,charge=.30),'ready',True,'eAvailable'),
        ('Straight Mode open, Boost active',render.State(speed=310,rpm=12500,gear=8,charge=.125),'open',True,'eActive'),
    ]
    board=Image.new('RGB',(1200,1470),(27,41,51))
    draw=ImageDraw.Draw(board)
    for index,(caption,state,sm,om,boost) in enumerate(cases):
        y=index*480
        draw.text((25,y+12),caption,font=mat.typeface(21,600),fill=(235,247,255))
        picture=frame(state,sm,om,boost)
        board.paste(picture,(0,y+35),picture)
    draw.text((25,1450),'Offline simulation. Native glyphs, mapped buttons and live states need in-game confirmation.',
              font=mat.typeface(15,500),fill=(166,194,207))
    destination=ROOT/'design/f126-base-preview.png'
    board.save(destination)
    print(destination)

if __name__=='__main__':
    main()
