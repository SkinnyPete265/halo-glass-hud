"""Preview longer DRS rails and the projected sector block farther outward."""
from pathlib import Path
import math
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import artwork as art, layout as geo, material as mat, sectors, drs_motion
from halo import preview_instruments as hud


def main():
    before=Image.open(ROOT/'design/rails-sector-position-before.png').convert('RGBA')
    previous_length=geo.arc_length(1010.)-geo.arc_length(geo.DRS_RAIL_START)
    current_length=geo.arc_length(geo.DRS_RAIL_END)-geo.arc_length(geo.DRS_RAIL_START)
    assert current_length>previous_length
    assert geo.DRS_RAIL_END==geo.WING_FACE_END
    assert drs_motion.rail_limits()[1]==geo.DRS_RAIL_END==geo.WING_FACE_END
    assert abs(math.hypot(*sectors.row_step())-27.)<1e-6
    assert sectors.FONT_SIZE==21.*.95
    assert sectors.PREFIX_ADVANCES==(11.3,10.8,5.0)
    assert sectors.TIME_ADVANCES==(11.7,11.7,5.1,11.7,11.7,11.7)
    assert sectors.DECIMAL_BASELINE_FRACTION==.40
    for part,advances in (('prefix',sectors.PREFIX_ADVANCES),('time',sectors.TIME_ADVANCES)):
        for index in range(len(advances)):
            cells=[sectors.anchor(row,part,index)[0] for row in range(3)]
            step_x,step_y=sectors.row_step()
            for first,second in zip(cells,cells[1:]):
                assert abs(second.x-first.x-step_x)<1e-6
                assert abs(second.y-first.y-step_y)<1e-6
    times=('29.531','19.094','33.366')
    colours=('yellow','yellow','purple')
    core=art.canvas()
    sectors.draw(core,times,colours,lighting=False)
    alpha=core.getchannel('A')
    box=alpha.getbbox()
    pixels=alpha.crop(box)
    for y in range(pixels.height):
        for x in range(pixels.width):
            if pixels.getpixel((x,y))<128:
                continue
            world_x=(box[0]+x)/mat.S
            world_y=(box[1]+y)/mat.S
            upper,lower=geo.wing_face_bounds(2*geo.CX-world_x)
            assert upper+2<world_y<lower-2
    state=hud.State(speed=279,rpm=11249,gear=7,throttle=.7,brake=0.,charge=.75,drs='open',
                    sector_times=times,sector_colours=colours)
    after=hud.render(state)
    after.save(ROOT/'design/rails-sector-position-transparent.png')
    capture=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    sheet=Image.new('RGB',(1240,1010),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    frames=[]
    for top,title,artwork in ((52,'Before',before),(542,'Longer DRS rails · sectors farther toward the tip',after)):
        image=Image.alpha_composite(capture,artwork).convert('RGB')
        frames.append(image)
        sheet.paste(image,(20,top))
        draw.text((20,top-34),title,font=mat.typeface(23,550),fill=(236,248,253))
    draw.text((20,986),'Offline layout preview with simulated sector times.',font=mat.typeface(16,500),fill=(175,201,217))
    sheet.save(ROOT/'design/rails-sector-position-preview.png')
    frames[1].save(ROOT/'design/rails-sector-position-gameplay.png')
    detail=Image.new('RGB',(960,660),(24,39,49))
    draw=ImageDraw.Draw(detail)
    for left,title,image in ((12,'Before',frames[0]),(492,'Reprojected outward',frames[1])):
        panel=image.crop((100,145,320,430)).resize((440,570),Image.Resampling.LANCZOS)
        detail.paste(panel,(left,48))
        draw.text((left,14),title,font=mat.typeface(22,550),fill=(236,248,253))
    draw.text((12,634),'The row pitch and glyph advances use the established projected layout.',font=mat.typeface(16,500),fill=(175,201,217))
    detail.save(ROOT/'design/sector-outward-position-detail.png')
    print('Rail arc-length increase',round((current_length/previous_length-1)*100,2),'percent')
    print('Verified sector row/column alignment, spacing and core glyph clearance within the wing.')


if __name__=='__main__':
    main()
