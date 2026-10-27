"""Encode a synchronized opening capture for the README.

    node tools/readme-clips/capture.mjs tmp/readme-hero
    python tools/readme-clips/hero.py tmp/readme-hero --preview <optional.mp4>

AVIF: 1600 px, 60 fps. WebP fallback: 1080 px, 30 fps. AVIF is streamed;
only the smaller WebP frames are held in RAM. The loop fades through black,
so the title never overlaps the opening nebula at the loop boundary.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
PW, PH = 1600, 686
THEMES = {'dark': (13, 17, 23), 'light': (255, 255, 255)}


def feather(w, h, p=4, inner=0.82):
    u = np.abs(np.linspace(-1, 1, w, dtype=np.float32))[None, :]
    v = np.abs(np.linspace(-1, 1, h, dtype=np.float32))[:, None]
    t = np.clip((((u ** p + v ** p) ** (1 / p)) - inner) / (1 - inner), 0, 1)
    return 1 - t * t * (3 - 2 * t)


def card(w, h, radius=36):
    image = Image.new('L', (w * 4, h * 4), 0)
    ImageDraw.Draw(image).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius * 4, fill=255)
    return np.asarray(image.resize((w, h), Image.Resampling.LANCZOS), dtype=np.float32) / 255


def encoder(destination, fps, codec):
    command = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{PW}x{PH}', '-r', str(fps), '-i', '-', '-an']
    if codec == 'avif':
        command += ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                    '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1',
                    '-colorspace', 'bt709', '-color_range', 'tv', '-c:v', 'libsvtav1',
                    '-preset', '6', '-crf', '30', '-svtav1-params', 'lp=4', '-g', '660', '-loop', '0']
    else:
        command += ['-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-movflags', '+faststart']
    return subprocess.Popen(command + [str(destination)], stdin=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/readme/clips')
    parser.add_argument('--version', default='v8')
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--webp-only', action='store_true')
    args = parser.parse_args()
    capture = json.loads((args.source / 'capture.json').read_text(encoding='utf-8'))
    fps, count = capture['fps'], capture['frames']
    assert not capture['errors'], capture['errors']
    paths = [args.source / f'{index:04d}.png' for index in range(count)]
    assert all(path.is_file() for path in paths), 'Capture is incomplete'
    args.output.mkdir(parents=True, exist_ok=True)
    duration = (count - 1) / fps
    for theme, background in THEMES.items():
        page = np.array(background, dtype=np.float32)
        alpha = (feather(PW, PH) if theme == 'dark' else card(PW, PH))[..., None]
        base = args.output / f'hero-{args.version}-{theme}'
        destinations = [] if args.webp_only else [(base.with_suffix('.avif'), 'avif')]
        if args.preview and theme == 'dark' and not args.webp_only:
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            destinations.append((args.preview, 'mp4'))
        processes = [encoder(destination, fps, codec) for destination, codec in destinations]
        webp_frames = []
        try:
            for index, path in enumerate(paths):
                if args.webp_only and index % 2:
                    continue
                with Image.open(path) as source:
                    image = source.convert('RGB').resize((PW, PH), Image.Resampling.LANCZOS)
                    rgb = np.asarray(image, dtype=np.float32)
                time = index / fps
                fade = min(1, time / 0.25, (duration - time) / 0.65)
                if index >= count - 2:
                    fade = 0
                fade = fade * fade * (3 - 2 * fade)
                composed = rgb * max(0, fade) * alpha + page * (1 - alpha)
                pixels = np.clip(composed + 0.5, 0, 255).astype(np.uint8)
                payload = pixels.tobytes()
                for process in processes:
                    process.stdin.write(payload)
                if index % 2 == 0:
                    webp_frames.append(Image.fromarray(pixels).resize((1080, 464), Image.Resampling.LANCZOS))
            for process in processes:
                process.stdin.close()
            for process in processes:
                if process.wait() != 0:
                    raise RuntimeError('Encoding failed')
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
        webp_frames[-1] = webp_frames[0].copy()
        durations = [round((i + 1) * 2000 / fps) - round(i * 2000 / fps) for i in range(len(webp_frames))]
        webp_path = base.with_suffix('.webp')
        # Independent frames prevent lossy delta-frame trails, especially in
        # the dark gradients and the closing fade. They also decode predictably.
        webp_frames[0].save(webp_path, save_all=True, append_images=webp_frames[1:],
                            duration=durations, loop=0, quality=68, method=4, kmin=1, kmax=1)
        destinations.append((webp_path, 'webp'))
        for destination, codec in destinations:
            print(f'{destination.name}: {destination.stat().st_size / 1e6:.2f} MB ({codec})', flush=True)


if __name__ == '__main__':
    main()
