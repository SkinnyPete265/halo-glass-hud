"""Preview a tiny outer-glow lift and the optional centered decimal point."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import (artwork as art, layout as geo, material as mat,
                  preview_instruments as hud, sectors)


def main():
    background=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    previous=Image.open(ROOT/'design/sector-times-before-outer-glow.png').convert('RGBA').crop((20,58,1220,498))
    times=('27.628','18.159','33.366')
    colours=('yellow','green','purple')
    panels=[('v0.4.0',previous)]
    background_extended=Image.new('RGBA',(background.width,
                                          background.height+round(geo.ARTWORK_TOP_PADDING)))
    background_extended.alpha_composite(background,(0,round(geo.ARTWORK_TOP_PADDING)))
    for title,fraction in (('Tiny outer-glow lift',sectors.DECIMAL_BASELINE_FRACTION),
                           ('Centred separator option',0.)):
        image=hud.static_base().copy()
        overlay=art.canvas()
        sectors.draw(overlay,times,colours,decimal_fraction=fraction)
        image.alpha_composite(overlay,(0,round(geo.ARTWORK_TOP_PADDING*art.S)))
        panels.append((title,Image.alpha_composite(background_extended,art.finish(image))))
    sheet=Image.new('RGB',(1450,690),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    for index,(title,image) in enumerate(panels):
        left=20+index*480
        view=image.crop((125,135,315,350)).resize((456,516),Image.Resampling.LANCZOS)
        sheet.paste(view.convert('RGB'),(left,58))
        draw.text((left,20),title,font=mat.typeface(22,550),fill=(236,248,253))
    draw.text((20,603),"The final option places the decimal point on the digits' centreline.",
              font=mat.typeface(21,500),fill=(211,232,243))
    draw.text((20,649),'Simulated preview with approximate native fonts.',
              font=mat.typeface(18,500),fill=(175,201,217))
    sheet.save(ROOT/'design/sector-outer-glow-and-decimal-preview.png')
    print('Rendered the small glow increase and centered-separator comparison.')


if __name__=='__main__':
    main()
