"""The README's opening clip, sharper: the flight through a nebula to the birth of a star and the museum
opening, from the original recording (1260 x 540 at 60 fps, kept in Astroingenieria-readme-archive).

    python tools/readme-clips/hero.py  ->  docs/readme/clips/hero-v6-<theme>.avif / .webp

Drawn at 1840 px wide at 30 fps (AVIF), with a lighter WebP (920 px, 15 fps) for browsers without AVIF.
Dark: blended into GitHub's page; light: a rounded card. It loops forwards with a short crossfade.
"""
import os, subprocess
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = r'E:/Proyectos/ChatGPT/Astroingenieria-readme-archive/docs-readme-intros/intro-principal.mp4'
OUT = os.path.join(ROOT, 'docs', 'readme', 'clips')
SW, SH = 1260, 540
PW = 1840
PH = round(PW * SH / SW)
FPS, XFADE = 30, 15
WEBP_W, WEBP_Q = 920, 60
THEMES = {'dark': (13, 17, 23), 'light': (255, 255, 255)}

def feather(w, h, p=4, inner=0.82):
    u = np.abs(np.linspace(-1, 1, w))[None, :]
    v = np.abs(np.linspace(-1, 1, h))[:, None]
    t = np.clip((((u ** p + v ** p) ** (1 / p)) - inner) / (1 - inner), 0, 1)
    return 1 - t * t * (3 - 2 * t)

def card(w, h, r=40):
    im = Image.new('L', (w * 4, h * 4), 0)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), r * 4, fill=255)
    return np.asarray(im.resize((w, h), Image.LANCZOS), dtype=np.float32) / 255

def frames():
    """The recording at 30 fps, scaled to 1840 px (Lanczos, by ffmpeg)."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-vf', f'fps={FPS},scale={PW}:{PH}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    out = []
    while True:
        b = p.stdout.read(PW * PH * 3)
        if len(b) < PW * PH * 3:
            break
        out.append(np.frombuffer(b, np.uint8).reshape(PH, PW, 3).astype(np.float32) / 255)
    p.wait()
    return out

def main():
    fr = frames()
    n = len(fr)
    seq = [fr[i] for i in range(XFADE, n - XFADE)] + [fr[n - XFADE + k] * (1 - (k + 1) / (XFADE + 1)) + fr[k] * ((k + 1) / (XFADE + 1)) for k in range(XFADE)]
    mask, rounded = feather(PW, PH), card(PW, PH)
    for theme, page in THEMES.items():
        pg = np.array(page, np.float32) / 255
        al = (mask if theme == 'dark' else rounded)[..., None]
        dst = os.path.join(OUT, f'hero-v6-{theme}')
        enc = subprocess.Popen(
            ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{PW}x{PH}', '-r', str(FPS), '-i', '-',
             '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
             '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1', '-colorspace', 'bt709', '-color_range', 'tv',
             '-c:v', 'libsvtav1', '-preset', '5', '-crf', '32', '-g', '600', '-loop', '0', dst + '.avif'], stdin=subprocess.PIPE)
        webp = []
        for k, rgb in enumerate(seq):
            out = rgb * al + pg * (1 - al)
            img = Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8), 'RGB')
            enc.stdin.write(img.tobytes())
            if k % 2 == 0:
                webp.append(img.resize((WEBP_W, round(PH * WEBP_W / PW)), Image.LANCZOS))
        enc.stdin.close()
        enc.wait()
        webp[0].save(dst + '.webp', save_all=True, append_images=webp[1:], duration=2000 // FPS, loop=0, quality=WEBP_Q, method=4)
        print(f'  hero-v6-{theme}: {len(seq)} frames {PW}x{PH}  avif {os.path.getsize(dst + ".avif") / 1e6:.2f} MB'
              f'  webp {os.path.getsize(dst + ".webp") / 1e6:.2f} MB', flush=True)

if __name__ == '__main__':
    main()
