"""Preview sector completion and fixed-column curved layout."""
from dataclasses import replace
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import layout as geo, material as mat, preview_instruments as hud, sectors


def main():
    for part, advances in (('prefix',sectors.PREFIX_ADVANCES),('time',sectors.TIME_ADVANCES)):
        for index in range(len(advances)):
            cells=[sectors.anchor(row,part,index)[0] for row in range(3)]
            step_x,step_y=sectors.row_step()
            assert all(abs(b.x-a.x-step_x)<1e-6 and abs(b.y-a.y-step_y)<1e-6
                       for a,b in zip(cells,cells[1:]))
            assert cells[0].rotation==cells[1].rotation==cells[2].rotation
    starts=[]
    for row in range(3):
        image=hud.art.canvas()
        spec,basis=sectors.anchor(row,'prefix',0)
        sectors.draw_character(image,'S',spec,basis,sectors.COLOURS['white'])
        starts.append(image.getchannel('A').point(lambda alpha:255 if alpha>64 else 0).getbbox()[:2])
    step_x,step_y=sectors.row_step()
    for index,(x,y) in enumerate(starts):
        assert abs(x-starts[0][0]-index*step_x*mat.S)<=1.
        assert abs(y-starts[0][1]-index*step_y*mat.S)<=1.
    fields=list(sectors.glyphs())
    assert len(fields)==81
    assert len({field.name for field in fields})==81
    assert len({field.binding for field in fields if field.binding})==72
    assert all(field.colour==sectors.COLOURS['white'] for field in fields if field.literal)
    background=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    state=hud.State(speed=250,rpm=11585,gear=6,throttle=1.,charge=.75,drs='hidden')
    completed=replace(state,sector_times=('27.628','18.159','33.366'),
                      sector_colours=('yellow','green','purple'))
    sheet=Image.new('RGB',(1240,1020),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    first=None
    for y,title,sample in ((58,'Completed sectors with sample colour states',completed),
                           (548,'Pending sectors',state)):
        frame=hud.render(sample)
        composite=Image.alpha_composite(background,frame)
        if first is None:
            first=composite
        sheet.paste(composite.convert('RGB'),(20,y))
        draw.text((20,y-35),title,font=mat.typeface(23,550),fill=(236,248,253))
    draw.text((20,994),'Simulated inputs and approximate native fonts. Live v2 timing still needs an in-game test.',
              font=mat.typeface(17,500),fill=(175,201,217))
    sheet.save(ROOT/'design/sector-times-preview.png')
    detail=first.crop((125,110,315,350)).resize((570,720),Image.Resampling.LANCZOS)
    detail.convert('RGB').save(ROOT/'design/sector-times-detail.png')
    old=Image.open(ROOT/'design/sector-times-before-lighting.png').convert('RGB')
    new=sheet
    compare=Image.new('RGB',(1110,516),(24,39,49))
    compare_draw=ImageDraw.Draw(compare)
    # Identical screen regions make the outward move and perspective visible.
    region=(125,65,465,350)
    source_region=(region[0]+20,region[1]+58,region[2]+20,region[3]+58)
    for x,title,source in ((20,'Before lighting',old),
                            (575,'Label glow and timing contrast',new)):
        panel=source.crop(source_region).resize((510,428),Image.Resampling.LANCZOS)
        compare.paste(panel,(x,56))
        compare_draw.text((x,18),title,font=mat.typeface(21,550),fill=(236,248,253))
    compare.save(ROOT/'design/sector-times-lighting-comparison.png')
    dark=Image.new('RGBA',background.size,(9,16,24,255))
    dark_frame=Image.alpha_composite(dark,hud.render(completed))
    dark_frame.crop((125,110,315,350)).resize((570,720),Image.Resampling.LANCZOS).convert('RGB').save(
        ROOT/'design/sector-times-dark-detail.png')
    print('Verified label starts, projected spacing and colour bindings. Rendered daylight and dark previews.')


if __name__=='__main__':
    main()
