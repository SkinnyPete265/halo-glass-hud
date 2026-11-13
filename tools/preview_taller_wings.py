"""Preview the taller mirrored wings and expanded instrument spacing."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import preview_instruments as hud, layout


def composite(background,foreground):
    result=background.convert('RGBA').copy()
    result.alpha_composite(foreground)
    return result.convert('RGB')


def main():
    capture=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGB')
    scenery=capture.crop((350,180,1550,620))
    state=hud.State(speed=206,rpm=10096,gear=4,throttle=.6,brake=.5,
                    charge=.75,drs='hidden')
    revised=hud.render(state)
    revised.save(ROOT/'design/taller-wings-transparent.png')
    composite(scenery,revised).save(ROOT/'design/taller-wings-gameplay.png')

    before=Image.open(ROOT/'design/wing-height-before.png').convert('RGBA')
    # Use the same selected gear for the full-width comparison.
    matched=hud.render(hud.State(speed=206,rpm=10096,gear=5,throttle=.6,brake=.5,
                                charge=.75,drs='hidden'))
    sheet=Image.new('RGB',(1248,1018),(21,34,44))
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype(str(ROOT/layout.FONT_PATH),23)
    for y,title,artwork in ((58,'Previous wing height',before),
                            (548,'Both wings 15% taller, with expanded row spacing',matched)):
        draw.text((24,y-36),title,font=font,fill=(236,248,253))
        sheet.paste(composite(scenery,artwork),(24,y))
    draw.text((24,994),'Offline comparison with simulated values. Native text rendering needs an in-game check.',
              font=ImageFont.truetype(str(ROOT/layout.FONT_PATH),16),fill=(175,201,217))
    sheet.save(ROOT/'design/taller-wings-comparison.png')

    detail=composite(scenery,revised).crop((735,45,1065,350))
    detail.resize((660,610),Image.Resampling.LANCZOS).save(
        ROOT/'design/taller-wings-detail.png')
    # Verify that the DRS glow remains attached to the lower wing edges.
    opened=hud.render(hud.State(speed=206,rpm=10096,gear=4,throttle=.6,brake=.5,
                                charge=.75,drs='open'))
    composite(scenery,opened).save(ROOT/'design/taller-wings-drs.png')
    print('Rendered taller-wing comparison, close-up, full HUD and DRS alignment preview.')


if __name__=='__main__':
    main()
