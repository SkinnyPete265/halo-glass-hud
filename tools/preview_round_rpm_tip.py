"""Inspect the rounded RPM tip at several high-RPM fill levels."""
from pathlib import Path
import sys
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import artwork as art,material as mat,rpm_mask

image=Image.new('RGB',(1000,400),(24,39,49))
draw=ImageDraw.Draw(image)
source=art.rpm_fill()
for index,fraction in enumerate((.82,.90,.96,1.)):
    filled=rpm_mask.clip(source,fraction,art.S)
    x,y=rpm_mask.tip(min(fraction,.975))
    bounds=tuple(round(v*art.S) for v in (x-35,y-24,x+25,y+24))
    part=filled.crop(bounds).resize((240,192),Image.Resampling.LANCZOS)
    image.paste(part,(index*250,45),part)
    draw.text((index*250+15,15),f'{fraction:.0%} RPM fill',font=mat.typeface(18,600),fill=mat.WHITE)
image.save(ROOT/'design/rpm-round-tip-inspection.png')
