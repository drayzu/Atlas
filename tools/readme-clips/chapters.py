"""Compose freshly captured chapter portals with the existing README captions.

    node tools/readme-clips/capture-chapters.mjs tmp/readme-chapters
    python tools/readme-clips/chapters.py tmp/readme-chapters

Each 60 fps, five-second camera passage plays forward and back, with smooth
turnarounds and a continuous ten-second loop. AVIF keeps 60 fps (600 frames);
the WebP fallback samples every second frame for 30 fps.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = Path(__file__).resolve().parent / 'fonts'
W, H, Z = 1280, 440, 1280 / 960
SW, SH, FRAMES, FPS = 800, 320, 600, 60
SCENE_BLACK = (4, 6, 11)
THEMES = {
    'light': ((255, 255, 255), (126, 106, 68), (36, 31, 22), (88, 85, 79)),
    'dark': ((13, 17, 23), (198, 187, 163), (232, 223, 205), (189, 189, 185)),
}
DARK_LUT = [round(base + max(0, value - black) * (255 - base) / (255 - black))
            for base, black in zip(THEMES['dark'][0], SCENE_BLACK) for value in range(256)]
CLIPS = [
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
    return ImageFont.truetype(str(FONTS / name), size * Z)


KICK = font('montserrat-latin-500-normal.woff2', 13)
TITLE = font('cormorant-garamond-latin-500-normal.woff2', 50)
LINE = font('cormorant-garamond-latin-400-italic.woff2', 27)


def base_image(number, right, titles, lines, theme):
    page, kicker, title, line = THEMES[theme]
    image = Image.new('RGB', (W, H), page)
    draw = ImageDraw.Draw(image)
    tx = 633.5 if right else 25.5
    baseline = 113.5 - (52 * (len(titles) - 1) + 31 * (len(lines) - 1)) / 2
    x = tx * Z
    for char in f'CHAPTER {number}':
        draw.text((x, baseline * Z), char, font=KICK, fill=kicker, anchor='ls')
        x += KICK.getlength(char) + 5 * Z
    y = baseline + 68
    for text in titles:
        draw.text((tx * Z, y * Z), text, font=TITLE, fill=title, anchor='ls')
        y += 52
    y -= 10
    for text in lines:
        draw.text((tx * Z, y * Z), text, font=LINE, fill=line, anchor='ls')
        y += 31
    return image


def scene_mask(theme):
    if theme == 'light':
        image = Image.new('L', (SW * 4, SH * 4), 0)
        ImageDraw.Draw(image).rounded_rectangle((0, 0, SW * 4 - 1, SH * 4 - 1), round(20 * Z * 4), fill=255)
        return image.resize((SW, SH), Image.Resampling.LANCZOS)
    u = np.abs(np.linspace(-1, 1, SW))[None, :]
    v = np.abs(np.linspace(-1, 1, SH))[:, None]
    # Recover the prior cards' edge profile, fitted against their light/dark pairs.
    t = np.clip(((u ** 6 + v ** 6) ** (1 / 6) - 0.80) / 0.20, 0, 1)
    return Image.fromarray(np.round(255 * (1 - t * t * (3 - 2 * t))).astype(np.uint8))


def scene_palette(image, theme):
    if theme != 'dark':
        return image
    # The earlier dark cards screen-blended their scenes over GitHub's page.
    # Normalize the live renderer's blue-black first, so its empty sky maps
    # to the page rather than leaving a darker (or lifted blue) rectangle.
    return image.point(DARK_LUT)


def decoder(source):
    graph = ('[0:v]split=2[f][r];[f]trim=end_frame=300,setpts=PTS-STARTPTS[f0];'
             '[r]reverse,trim=end_frame=300,setpts=PTS-STARTPTS[r0];'
             '[f0][r0]concat=n=2:v=1:a=0,scale=800:320:flags=lanczos,format=rgb24[out]')
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(source), '-filter_complex', graph,
                             '-map', '[out]', '-frames:v', str(FRAMES), '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)


def encoder(destination, log, preview=False, crf=36):
    command = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-an']
    if preview:
        command += ['-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'fast',
                    '-crf', '19', '-movflags', '+faststart']
    else:
        command += ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                    '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1',
                    '-colorspace', 'bt709', '-color_range', 'tv', '-c:v', 'libsvtav1',
                    '-preset', '7', '-crf', str(crf), '-svtav1-params', 'lp=2', '-g', '600', '-loop', '0']
    return subprocess.Popen(command + [str(destination)], stdin=subprocess.PIPE, stderr=log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('names', nargs='*')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/readme/clips')
    parser.add_argument('--preview-dir', type=Path)
    parser.add_argument('--avif-only', action='store_true')
    parser.add_argument('--version', default='v6')
    parser.add_argument('--theme', choices=['dark', 'light', 'both'], default='both')
    args = parser.parse_args()
    capture = json.loads((args.source / 'capture.json').read_text(encoding='utf-8'))
    assert capture['fps'] == FPS and capture['frames'] == 301 and not capture['errors']
    args.output.mkdir(parents=True, exist_ok=True)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    for number, (name, right, titles, lines) in enumerate(CLIPS, 1):
        if args.names and name not in args.names:
            continue
        assert name in capture['names']
        for theme in ('dark', 'light'):
            if args.theme != 'both' and theme != args.theme:
                continue
            base = base_image(number, right, titles, lines, theme)
            mask = scene_mask(theme)
            box = (0 if right else W - SW, (H - SH) // 2)
            stem = args.output / f'{name}-{args.version}-{theme}'
            with (args.source / f'{name}-{theme}-encode.log').open('wb') as log:
                source = decoder(args.source / f'{name}.mp4')
                crf = 38 if name == 'planetary' else 36
                avif = encoder(stem.with_suffix('.avif'), log, crf=crf)
                preview = encoder(args.preview_dir / f'{name}.mp4', log, True) if args.preview_dir and theme == 'dark' and not args.avif_only else None
                processes = [avif] + ([preview] if preview else [])
                webp = []
                try:
                    for index in range(FRAMES):
                        data = source.stdout.read(SW * SH * 3)
                        if len(data) != SW * SH * 3:
                            raise RuntimeError(f'{name}: incomplete source at frame {index}')
                        frame = base.copy()
                        panel = scene_palette(Image.frombytes('RGB', (SW, SH), data), theme)
                        frame.paste(panel, box, mask)
                        raw = frame.tobytes()
                        for process in processes:
                            process.stdin.write(raw)
                        if index % 2 == 0 and not args.avif_only:
                            webp.append(frame.resize((960, 330), Image.Resampling.LANCZOS))
                        if index == 150:
                            frame.save(args.source / f'{name}-{theme}-composed.png')
                    for process in processes:
                        process.stdin.close()
                    assert source.wait() == 0
                    for process in processes:
                        if process.wait() != 0:
                            raise RuntimeError(f'{name}: encoder failed; see {name}-{theme}-encode.log')
                finally:
                    for process in [source] + processes:
                        if process.poll() is None:
                            process.terminate()
                            process.wait()
            if not args.avif_only:
                durations = [round((i + 1) * 1000 / 30) - round(i * 1000 / 30) for i in range(300)]
                webp[0].save(stem.with_suffix('.webp'), save_all=True, append_images=webp[1:],
                             duration=durations, loop=0, quality=67, method=3, kmin=1, kmax=1)
            entry = {'name': name, 'theme': theme, 'avif_bytes': stem.with_suffix('.avif').stat().st_size,
                     'webp_bytes': stem.with_suffix('.webp').stat().st_size, 'avif_crf': crf}
            print(json.dumps(entry), flush=True)
            (args.source / f'{name}-{theme}-encoding.json').write_text(json.dumps(entry, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
