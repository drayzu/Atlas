"""Sharper README chapter clips: the same animation, its caption redrawn at 1840 px.

    python tools/readme-clips/sharpen.py [intro energy ...]  ->  docs/readme/clips/<name>-v4-<theme>.avif / .webp

The original captures are gone, so the animation is the v3 clip (960 px, 15 fps, kept in
tools/readme-clips/src, not in git) scaled up; the caption column is cleared and its text drawn
again at full resolution with the same fonts, sizes and colours (fitted against the v3 frames).
AVIF for the page, a WebP of the same frames at 960 px for browsers without AVIF.
"""
import os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(HERE, 'src')
OUT = os.path.join(ROOT, 'docs', 'readme', 'clips')
FONTS = os.path.join(HERE, 'fonts')

W, H = 960, 330                # layout units (the v3 clips)
Z = 1840 / W
PW, PH = round(W * Z), round(H * Z)

THEMES = {  # page, kicker, title, line
    'light': ((255, 255, 255), (126, 106, 68), (36, 31, 22), (88, 85, 79)),
    'dark': ((13, 17, 23), (198, 187, 163), (232, 223, 205), (189, 189, 185)),
}

CLIPS = [  # name, text on the right?, title lines, line lines
    ('intro', True, ['Introduction'], ['Engineering, seen as a', 'landscape.']),
    ('habitats', False, ['Space habitats'], ['Homes that spin to make', 'their own gravity.']),
    ('industry', True, ['Space industry'], ['Ports, mines and shipyards', 'in orbit.']),
    ('planetary', False, ['Planetary', 'engineering'], ['A magnetic field to shield', 'a whole world.']),
    ('energy', True, ['Stellar energy'], ['Harvesting the light of a', 'sun.']),
    ('travel', False, ['Interstellar', 'travel'], ['The long way out, between', 'the stars.']),
    ('stellar', True, ['Stellar', 'engineering'], ['Steering stars and taming', 'black holes.']),
    ('civilizations', False, ['Cosmic', 'civilizations'], ['From single planets to', 'whole galaxies.']),
    ('search', True, ['Extraterrestrial', 'intelligence'], ['Listening to the silence.']),
]

def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size * Z)

KICK = font('montserrat-latin-500-normal.woff2', 13)
TITLE = font('cormorant-garamond-latin-500-normal.woff2', 50)
LINE = font('cormorant-garamond-latin-400-italic.woff2', 27)

def durations(path):
    import struct
    b = open(path, 'rb').read()
    i, out = 12, []
    while i < len(b):
        tag, n = b[i:i + 4], struct.unpack('<I', b[i + 4:i + 8])[0]
        if tag == b'ANMF':
            out.append(int.from_bytes(b[i + 8 + 12:i + 8 + 15], 'little'))
        i += 8 + n + (n & 1)
    return out

def caption(k, right, titles, lines, th):
    """The caption column at full resolution: (x0 px, RGB image of the column)."""
    page, kc, tc, lc = th
    x0 = 605 if right else 0
    col = Image.new('RGB', (PW - round(x0 * Z) if right else round(355 * Z), PH), page)
    d = ImageDraw.Draw(col)
    tx = (633.5 if right else 25.5) - x0
    kb = 113.5 - (52 * (len(titles) - 1) + 31 * (len(lines) - 1)) / 2  # the block is centred
    x = tx * Z
    for c in f'CHAPTER {k + 1}':
        d.text((x, kb * Z), c, font=KICK, fill=kc, anchor='ls')
        x += KICK.getlength(c) + 5 * Z
    y = kb + 68
    for t in titles:
        d.text((tx * Z, y * Z), t, font=TITLE, fill=tc, anchor='ls')
        y += 52
    y += 42 - 52
    for t in lines:
        d.text((tx * Z, y * Z), t, font=LINE, fill=lc, anchor='ls')
        y += 31
    return round(x0 * Z), col

def encode_avif(dst, fps):
    return subprocess.Popen(
        ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{PW}x{PH}', '-r', str(fps), '-i', '-',
         '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
         '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1', '-colorspace', 'bt709', '-color_range', 'tv',
         '-c:v', 'libsvtav1', '-preset', '5', '-crf', '34', '-g', '600', '-loop', '0', dst],
        stdin=subprocess.PIPE)

def clip(k, name, right, titles, lines):
    for theme, th in THEMES.items():
        src_path = os.path.join(SRC, f'{name}-v3-{theme}.webp')
        src = Image.open(src_path)
        durs = durations(src_path)
        fps = round(1000 / (sum(durs) / len(durs)))
        cx, col = caption(k, right, titles, lines, th)
        dst = os.path.join(OUT, f'{name}-v4-{theme}')
        enc = encode_avif(dst + '.avif', fps)
        webp = []
        for i in range(src.n_frames):
            src.seek(i)
            fr = src.convert('RGB').resize((PW, PH), Image.LANCZOS)
            fr.paste(col, (cx, 0))
            enc.stdin.write(fr.tobytes())
            webp.append(fr.resize((W, H), Image.LANCZOS))
        enc.stdin.close()
        enc.wait()
        webp[0].save(dst + '.webp', save_all=True, append_images=webp[1:], duration=durs, loop=0, quality=72, method=4)
        print(f'  {name}-{theme}: {src.n_frames} frames at {fps} fps  avif {os.path.getsize(dst + ".avif") / 1e6:.2f} MB'
              f'  webp {os.path.getsize(dst + ".webp") / 1e6:.2f} MB', flush=True)

if __name__ == '__main__':
    which = sys.argv[1:]
    for k, c in enumerate(CLIPS):
        if not which or c[0] in which:
            clip(k, *c)
