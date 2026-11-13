"""Compare the proposed final-quarter RPM warning using simulated bar values."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import preview_instruments as hud, layout as geo
import preview_restoration

def font(size):
    face = ImageFont.truetype(str(ROOT / geo.FONT_PATH), size)
    face.set_variation_by_axes([550, 100])
    return face

def main():
    sheet = Image.new("RGB", (1040, 1038), (31,47,57))
    draw = ImageDraw.Draw(sheet)
    values = (.70,.82,.92,1.0)
    for index,fraction in enumerate(values):
        column,row = index%2,index//2
        left,top = column*520,row*500
        draw.text((left+20,top+12),f"Bar {fraction:.0%} filled",
                  font=font(24),fill=(225,239,247))
        state = hud.State(speed=280,rpm=round(13000*fraction),gear=6,
                          throttle=1,brake=0,charge=.75,drs="hidden")
        frame = hud.render(state).crop((745,35,1065,325))
        frame = frame.resize((480,435),Image.Resampling.LANCZOS)
        sheet.paste(frame,(left+20,top+44),frame)
    draw.rectangle((0,1000,1040,1038),fill=(31,47,57))
    draw.text((20,1010),
              "Simulated values. Warning follows the game's existing RPM-bar fraction.",
              font=font(17),fill=(169,194,208))
    sheet.save(ROOT/"design/rpm-shift-warning-preview.png")
    # Refresh the existing overview and motion preview with the shared fill art.
    if "--refresh-overview" in sys.argv:
        preview_restoration.main()
    print("Rendered final-quarter RPM shift warning preview.")

if __name__=="__main__":
    main()
