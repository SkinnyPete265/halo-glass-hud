"""Motion comparison for the proposed travelling DRS highlight."""
from dataclasses import replace
from pathlib import Path
import math
import sys
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from halo import artwork as art,material as mat,preview_instruments as hud,drs_motion as motion,sectors

FPS=24


def ease_out(value):
    value=max(0.,min(1.,value))
    return 1.-(1.-value)**2


def main():
    assert sectors.DECIMAL_BASELINE_FRACTION==.40
    left=motion.mask_texture('left')
    right=motion.mask_texture('right')
    assert list(left.getchannel('A').getdata())==list(right.transpose(Image.Transpose.FLIP_LEFT_RIGHT).getchannel('A').getdata())
    assert right.getpixel((0,0))[3]==right.getpixel((255,0))[3]==0
    left.save(ROOT/'design/drs-sweep-mask-left.png')
    right.save(ROOT/'design/drs-sweep-mask-right.png')
    state=hud.State(speed=279,rpm=11249,gear=7,throttle=1.,brake=0.,charge=.75,drs='hidden',
                    sector_times=('29.531','19.094','--.---'),sector_colours=('yellow','yellow','white'))
    background=Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    base=Image.alpha_composite(background,hud.render(state))
    frames=[]
    snapshots=[]
    for index in range(108):
        time=index/FPS
        active=.45<=time<3.65
        closing=3.65<=time<3.725
        overlay=art.canvas()
        pulse,reveal,phase=1.,1.,0.
        if active or closing:
            age=time-.45
            pulse=.87+.13*math.cos(math.pi*max(0.,age-.15)/.6)
            reveal=ease_out(age/.15)
            if closing:
                reveal=1.-min(1.,(time-3.65)/.075)**2
            phase=(age%motion.PERIOD)/motion.PERIOD
            hud.draw_drs(overlay,replace(state,drs='open'),pulse,reveal)
        else:
            hud.draw_drs(overlay,replace(state,drs='ready'))
        current=Image.alpha_composite(base,art.finish(overlay))
        if active or closing:
            motion.draw(overlay,phase,pulse,reveal)
        candidate=Image.alpha_composite(base,art.finish(overlay))
        panel=Image.new('RGB',(1000,824),(24,39,49))
        draw=ImageDraw.Draw(panel)
        for y,title,image in ((42,'Current DRS',current),(428,'Travelling highlight',candidate)):
            panel.paste(image.resize((960,352),Image.Resampling.LANCZOS).convert('RGB'),(20,y))
            draw.text((20,y-34),title,font=mat.typeface(22,550),fill=(236,248,253))
        draw.text((20,798),'Simulated opening, active flow and closing. Native integration is pending.',
                  font=mat.typeface(17,500),fill=(175,201,217))
        frames.append(panel)
        if index in (17,23,29,35):
            snapshots.append((time,candidate))
    reference=frames[30].resize((500,412)).convert('P',palette=Image.Palette.ADAPTIVE,colors=256)
    palette = reference.getpalette()
    for index, colour in enumerate(sectors.COLOURS.values(), start=252):
        palette[index*3:index*3+3] = colour[:3]
    reference.putpalette(palette)
    palette_frames=[frame.quantize(palette=reference,dither=Image.Dither.NONE) for frame in frames]
    durations=[round((index+1)*1000/FPS/10)*10-round(index*1000/FPS/10)*10 for index in range(len(frames))]
    palette_frames[0].save(ROOT/'design/drs-travelling-highlight-preview.gif',save_all=True,
                           append_images=palette_frames[1:],duration=durations,loop=0,disposal=1,optimize=True)
    sheet=Image.new('RGB',(1200,270),(24,39,49))
    draw=ImageDraw.Draw(sheet)
    for index,(time,frame) in enumerate(snapshots):
        x=index*300
        view=frame.crop((720,155,1050,370)).resize((294,192),Image.Resampling.LANCZOS)
        sheet.paste(view.convert('RGB'),(x+3,45))
        draw.text((x+10,10),f'{time-.45:.2f} s after opening',font=mat.typeface(17,500),fill=(236,248,253))
    sheet.save(ROOT/'design/drs-highlight-motion-stages.png')
    print('Rendered a one-second centre-out highlight with a fading trail, opening and fast closure.')


if __name__=='__main__':
    main()
