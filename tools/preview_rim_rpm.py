"""Compare the circle texture and preview the opacity-capped RPM halo."""
from io import BytesIO
from pathlib import Path
import json
import sys
import zipfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import layout as geo, material as mat, preview_instruments as hud


def reconstruct(image, bounds, resolution):
    canvas = Image.new('RGBA', (geo.WIDTH * resolution, geo.HEIGHT * resolution))
    left = round((bounds[0] / geo.HUD_SCALE + geo.CX) * resolution)
    top = round((bounds[1] / geo.HUD_SCALE + geo.CY) * resolution)
    canvas.alpha_composite(image, (left, top))
    return canvas


def main():
    previous = ROOT / 'build/rollback-v0.3.1/local.halo-hud-v2.swoftyaddon'
    with zipfile.ZipFile(previous) as archive:
        record = json.loads(archive.read('source/registry/hud.json'))['hud.element']['glass_dial']
        before = reconstruct(Image.open(BytesIO(archive.read('source/art/base.png'))).convert('RGBA'),
                             record['sprites']['base']['bounds'], 1)
    record = json.loads((ROOT / 'registry/hud.json').read_text())['hud.element']['glass_dial']
    texture = Image.open(ROOT / 'art/base.png').convert('RGBA')
    assert texture.width % 4 == texture.height % 4 == 0
    assert max(texture.size) <= 2048
    bounds = record['sprites']['base']['bounds']
    after = reconstruct(texture, bounds, geo.BASE_TEXTURE_RESOLUTION)
    # Texture density changes retain the same art-to-HUD coordinate conversion.
    left = bounds[0] / geo.HUD_SCALE + geo.CX
    top = bounds[1] / geo.HUD_SCALE + geo.CY
    for x, y in ((geo.CX, geo.CY), (geo.CX-89, geo.CY), (geo.CX+89, geo.CY)):
        u = (x-left) * geo.BASE_TEXTURE_RESOLUTION / texture.width
        v = (y-top) * geo.BASE_TEXTURE_RESOLUTION / texture.height
        mapped = (bounds[0]+u*(bounds[2]-bounds[0]), bounds[1]+v*(bounds[3]-bounds[1]))
        assert all(abs(a-b)<1e-6 for a,b in zip(mapped,geo.hud_point(x,y)))

    capture = Image.open(ROOT / 'design/reference/visibility-gameplay.png').convert('RGB')
    background = capture.crop((350,180,1550,620)).convert('RGBA')
    state = hud.State(speed=279,rpm=11249,gear=7,throttle=.85,brake=0.,charge=.75,drs='hidden')
    preview = Image.alpha_composite(background,hud.render(state))
    preview.convert('RGB').save(ROOT / 'design/rim-rpm-preview.png')

    sheet = Image.new('RGB',(1180,478),(24,39,49))
    draw = ImageDraw.Draw(sheet)
    font = mat.typeface(22,550)
    circle = (484,0,680,196)
    backdrop = background.crop(circle).resize((360,360),Image.Resampling.LANCZOS)
    for x,title,source,resolution in ((18,'v0.3.1 circle',before,1),
                                      (404,'Smoothed circle',after,2)):
        region = tuple(value*resolution for value in circle)
        interpolation = Image.Resampling.BILINEAR if resolution==1 else Image.Resampling.LANCZOS
        face = source.crop(region).resize((360,360),interpolation)
        view = Image.alpha_composite(backdrop,face)
        sheet.paste(view.convert('RGB'),(x,62))
        draw.text((x,22),title,font=font,fill=(236,248,253))
    detail = preview.crop((840,145,1010,325)).resize((340,360),Image.Resampling.LANCZOS)
    sheet.paste(detail.convert('RGB'),(790,62))
    draw.text((790,22),'Reduced RPM halo',font=font,fill=(236,248,253))
    draw.text((18,445),'Artwork preview. Native text and final game rendering still need confirmation.',
              font=mat.typeface(18,500),fill=(175,201,217))
    sheet.save(ROOT / 'design/rim-rpm-detail-preview.png')
    print('Verified 2x texture alignment and rendered circle/RPM previews.')


if __name__=='__main__':
    main()
