# README clips

Capture the site's actual opening with hardware WebGL, then encode the dark
and light README variants. Requires the project dependencies, Playwright's
full Chromium browser, Python with NumPy and Pillow, and ffmpeg with SVT-AV1.

```powershell
node tools/readme-clips/capture.mjs tmp/readme-hero
python tools/readme-clips/hero.py tmp/readme-hero --preview tmp/readme-hero/preview.mp4
```

The default capture is 11 seconds at 60 fps. `--probe` saves one screenshot
every half-second instead, for checking the composition before a full capture.
Each capture records errors and title animation samples in `capture.json`.

The recorder advances timers and exactly one RAF callback batch per frame.
Motion uses its JS driver during capture, so opacity, blur and scale share
the WebGL scene's clock. Time-based CSS animations also use that clock;
scroll-based animations retain their scroll timeline. Fonts and shaders load
before recording starts. These changes apply only to the capture browser.
On Windows, full headless Chromium uses Direct3D 11 for the living-star scene.

The encoder streams frames into 1600 px / 60 fps AVIF and 1080 px / 30 fps
WebP files. Both themes use a short fade through black at the loop boundary,
without overlapping the title and the opening nebula. Versioned output names
also prevent readers from receiving the previous clip from an image cache.
WebP uses independent frames to avoid trails from lossy delta-frame blending.

## Chapter cards

The chapter recorder mounts the site's current `JourneyOverlay` components
in an isolated capture page. It records each camera passage at 60 fps without
UI controls, keeping the existing card layout, chapter captions and fonts.

```powershell
node tools/readme-clips/capture-chapters.mjs tmp/readme-chapters
python tools/readme-clips/chapters.py tmp/readme-chapters
```

Use `--probe` on the recorder to inspect five camera positions per chapter.
Chapter names after the output folder select a subset. The encoder accepts
the same names after its source folder, and `--preview-dir <folder>` saves MP4
previews as well. `--avif-only` retunes AVIF files while retaining existing
WebP outputs.

Each five-second passage eases into its turnarounds and plays forward and
back as a continuous ten-second loop. The caption stays still. AVIF cards
are 1280 × 440 at 60 fps; the WebP fallback is 960 × 330 at 30 fps, with
independent frames to prevent trails. This limits the decoding cost while
retaining four times the original AVIF frame rate.

Dark cards retain the older cards' color treatment: normalize the renderer's
blue-black sky, then screen-blend the scene over GitHub Dark's `#0d1117`.
The recovered edge feather uses a sixth-power superellipse with an 80%
opaque center. This treats the scene's empty sky as part of the page, rather
than hiding a darker rectangle with a vignette. Bright highlights stay bright.
Use `--theme dark` to regenerate only these cards; light cards keep their
white page and rounded-window treatment. `--version` controls cache-busting
output names (currently v6).

The former `sharpen.py` pipeline is retained for reproducing the older v4
cards; it starts from their 15 fps sources and cannot restore smooth motion.
