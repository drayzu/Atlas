# README opening clip

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
