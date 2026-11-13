"""Compare fuller wing-tip backing and coordinated soft edge fades."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import material as mat, layout as geo, preview_instruments as hud


def composite(background, artwork):
    return Image.alpha_composite(background.convert('RGBA'),artwork).convert('RGB')


def main():
    before=Image.open(ROOT/'design/wing-tip-fade-last-proposal.png').convert('RGBA')
    state=hud.State(speed=279,rpm=11249,gear=7,throttle=.7,brake=0.,charge=.75,drs='open',
                    sector_times=('29.531','19.094','--.---'),
                    sector_colours=('yellow','yellow','white'))
    after=hud.render(state)
    assert before.size==after.size
    assert before.crop((240,0,924,440)).tobytes()==after.crop((240,0,924,440)).tobytes()
    assert abs((geo.WING_FACE_END-geo.WING_FACE_START)/(1038.-geo.WING_FACE_START)-1.10)<.003
    assert mat.WING_TIP_FADE_WIDTH==32.
    assert mat.FACET_ALPHA==120.
    fade=lambda x: mat._smooth((geo.WING_FACE_END-x)/mat.WING_TIP_FADE_WIDTH)
    assert fade(geo.WING_FACE_END)==0.
    assert fade(geo.WING_FACE_END-mat.WING_TIP_FADE_WIDTH)==1.
    values=[fade(geo.WING_FACE_END-mat.WING_TIP_FADE_WIDTH+index/10.)
            for index in range(round(mat.WING_TIP_FADE_WIDTH*10)+1)]
    import hashlib,json
    from halo import feature_assets,drs_motion
    baseline=json.loads((ROOT/'build/wing-coverage-baseline.json').read_text())
    assert hashlib.sha256(feature_assets.drs_rails().tobytes()).hexdigest()==baseline['rails']
    assert hashlib.sha256(drs_motion.surface().tobytes()).hexdigest()==baseline['highlight']
    assert all(first>=second for first,second in zip(values,values[1:]))
    after.save(ROOT/'design/wing-tip-fade-transparent.png')
    capture=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGB')
    scenery=capture.crop((350,180,1550,620))
    full=composite(scenery,after)
    full.save(ROOT/'design/wing-tip-fade-gameplay.png')
    sheet=Image.new('RGB',(1240,1010),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    for top,title,artwork in ((52,'Previous proposal',before),
                              (542,'10% more backing · original fade',after)):
        draw.text((20,top-34),title,font=mat.typeface(23,550),fill=(236,248,253))
        sheet.paste(composite(scenery,artwork),(20,top))
    draw.text((20,986),'Offline material comparison.',font=mat.typeface(16,500),fill=(175,201,217))
    sheet.save(ROOT/'design/wing-tip-fade-comparison.png')
    backgrounds=(
        ('Bright sky',ImageOps.fit(capture.crop((550,0,1410,170)),(1200,440))),
        ('Pale surface',Image.new('RGB',(1200,440),(235,238,233))),
        ('Dark scenery',Image.new('RGB',(1200,440),(28,42,51))),
    )
    details=Image.new('RGB',(1120,800),(24,39,49))
    draw=ImageDraw.Draw(details)
    for index,(title,background) in enumerate(backgrounds):
        left=12+index*370
        draw.text((left,12),title,font=mat.typeface(20,550),fill=(236,248,253))
        for top,label,artwork in ((64,'Previous',before),(424,'+10% backing',after)):
            view=composite(background,artwork).crop((945,120,1105,420))
            view.thumbnail((346,312),Image.Resampling.LANCZOS)
            details.paste(view,(left+84,top))
            draw.text((left,top+124),label,font=mat.typeface(17,500),fill=(188,213,228))
    draw.text((12,778),'Wing-tip details on bright and dark backgrounds.',font=mat.typeface(16,500),fill=(175,201,217))
    details.save(ROOT/'design/wing-tip-fade-backgrounds.png')
    print('Verified fade endpoints, monotonic feathering and identical central-region pixels.')
    print('Saved full comparison, gameplay preview and three-background tip details.')


if __name__=='__main__':
    main()
