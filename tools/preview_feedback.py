"""Preview the v0.3.0 feedback fixes, including four- and five-digit RPM rows."""
from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import layout as geo,preview_instruments as hud


def font(size):
    return ImageFont.truetype(str(ROOT/geo.FONT_PATH),size)


def main():
    capture=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGB')
    background=capture.crop((350,180,1550,620)).convert('RGBA')
    state=hud.State(speed=206,rpm=10096,gear=4,throttle=.6,brake=.5,charge=.75,drs='hidden')
    updated=hud.render(state)
    updated.save(ROOT/'design/v030-feedback-transparent.png')
    Image.alpha_composite(background,updated).convert('RGB').save(ROOT/'design/v030-feedback-gameplay.png')
    before=Image.open(ROOT/'design/wing-edge-glow-transparent.png').convert('RGBA')
    sheet=Image.new('RGB',(1248,1018),(21,34,44))
    draw=ImageDraw.Draw(sheet)
    for y,title,artwork in ((58,'Previous layout',before),
                            (548,'Centered speed, taller battery and corrected RPM row',updated)):
        draw.text((24,y-36),title,font=font(23),fill=(236,248,253))
        sheet.paste(Image.alpha_composite(background,artwork).convert('RGB'),(24,y))
    draw.text((24,994),'Simulated preview. Native font rendering still needs an in-game check.',
              font=font(16),fill=(175,201,217))
    sheet.save(ROOT/'design/v030-feedback-preview.png')

    cases=Image.new('RGB',(1248,1020),(21,34,44))
    draw=ImageDraw.Draw(cases)
    for index,rpm in enumerate((9999,10000,11585,12999)):
        left=24+(index%2)*606
        top=54+(index//2)*470
        draw.text((left,top-34),f'{rpm:,} RPM',font=font(23),fill=(236,248,253))
        sample=hud.render(hud.State(speed=280,rpm=rpm,gear=6,throttle=1.,charge=.75,drs='hidden'))
        panel=Image.alpha_composite(background,sample)
        detail=panel.crop((820,160,1010,320)).resize((494,416),Image.Resampling.LANCZOS)
        cases.paste(detail.convert('RGB'),(left,top))
    draw.text((24,994),'The game uses a measured number/unit row. These preview fonts are approximated.',
              font=font(16),fill=(175,201,217))
    cases.save(ROOT/'design/v030-feedback-rpm-cases.png')

    detail=Image.alpha_composite(background,updated).crop((425,0,740,200))
    detail.resize((788,500),Image.Resampling.LANCZOS).convert('RGB').save(
        ROOT/'design/v030-feedback-center-detail.png')
    print('Rendered revised layout, centered instruments and four/five-digit RPM previews.')


if __name__=='__main__':
    main()
