"""Render source-only restoration previews with simulated input values."""
from dataclasses import replace
from pathlib import Path
import math
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import preview_instruments as hud

STATES = [
    ("Acceleration, battery 75%, DRS countdown",
     hud.State(speed=250, rpm=11585, gear=6, throttle=1, brake=0,
               charge=.75, drs="distance", drs_distance=100)),
    ("Braking, battery 12.5%, DRS available",
     hud.State(speed=140, rpm=8900, gear=3, throttle=.25, brake=.75,
               charge=.125, drs="ready")),
    ("Battery 8%, DRS open",
     hud.State(speed=300, rpm=11900, gear=8, throttle=1, brake=0,
               charge=.08, drs="open")),
]

def background(image):
    result = Image.new("RGBA", image.size, (31,47,57,255))
    result.alpha_composite(image)
    return result.convert("RGB")

def font(size):
    return ImageFont.truetype(str(ROOT/"assets/fonts/Saira/Saira.ttf"),size)

def main():
    sheet = Image.new("RGB",(1200,1404),(31,47,57))
    draw = ImageDraw.Draw(sheet)
    for index,(title,state) in enumerate(STATES):
        draw.text((24,index*454+12),title,font=font(23),fill=(221,239,248))
        frame = hud.render(state)
        frame.save(ROOT/"design"/f"restoration-state-{index+1}.png")
        source = frame.crop((60,0,1104,416))
        display_scale = .54 * (.53625 / .30)
        frame = source.resize(
            (round(source.width*display_scale),round(source.height*display_scale)),
            Image.Resampling.LANCZOS)
        sheet.paste(background(frame),((sheet.width-frame.width)//2,index*454+42))
    draw.text((24,1377),
              "Simulated inputs. Native speed/RPM fonts and the mapped DRS button are approximated.",
              font=font(16),fill=(169,194,208))
    sheet.save(ROOT/"design/restoration-states-preview.png")

    # A short motion sample covers progressive pedal fill and DRS reveal/pulse/close.
    frames=[]
    for index in range(54):
        t=index/18
        throttle=.5+.5*math.sin(t*math.pi-.5*math.pi)
        brake=.8*max(0,math.sin(t*math.pi-1.2*math.pi))
        if index<12:
            state=replace(STATES[0][1],throttle=throttle,
                          drs_distance=max(1,120-index*10))
            reveal=1
        elif index<18:
            state=replace(STATES[0][1],throttle=throttle,drs="ready")
            reveal=1
        elif index<20:
            state=replace(STATES[0][1],throttle=throttle,drs="open")
            reveal=(index-17)/2
        elif index<42:
            state=replace(STATES[0][1],throttle=throttle,drs="open")
            reveal=1
        elif index==42:
            state=replace(STATES[0][1],throttle=throttle,drs="open")
            reveal=.2
        else:
            state=replace(STATES[1][1],throttle=.1,brake=brake,drs="hidden")
            reveal=0
        pulse=.74+.26*(.5+.5*math.cos(2*math.pi*t))
        frame=background(hud.render(state,pulse,reveal))
        frame=frame.crop((60,0,1104,416)).resize((940,375),Image.Resampling.LANCZOS)
        frames.append(frame)
    frames[0].save(ROOT/"design/restoration-motion-preview.gif",save_all=True,
                   append_images=frames[1:],duration=56,loop=0,
                   disposal=2,optimize=False)
    print("Rendered three state previews and a simulated motion preview.")

if __name__=="__main__":
    main()
