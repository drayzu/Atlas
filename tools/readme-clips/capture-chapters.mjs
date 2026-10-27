/* global window, document, Element, Node, performance, DocumentTimeline */
import { mkdir, writeFile } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import process from 'node:process';
import console from 'node:console';
import { Buffer } from 'node:buffer';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { chromium } from '@playwright/test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.resolve(process.argv[2] ?? path.join(root, 'tmp/readme-chapters'));
const probe = process.argv.includes('--probe');
const requested = process.argv.slice(3).filter(arg => arg !== '--probe');
await mkdir(output, { recursive: true });
const server = await createServer({ root, server: { host: '127.0.0.1', port: 5198, strictPort: true,
  fs: { allow: [root, realpathSync(path.join(root, 'node_modules'))] } }, logLevel: 'error' });
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ headless: true, channel: 'chromium', args: process.platform === 'win32' ? ['--use-angle=d3d11'] : [] });
  const page = await browser.newPage({ viewport: { width: 600, height: 240 }, deviceScaleFactor: 4 / 3 });
  const cdp = await page.context().newCDPSession(page);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.clock.install({ time: new Date('2026-01-01T00:00:00Z') });
  await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
  await page.addInitScript(() => {
    Object.defineProperty(Node.prototype, 'animate', { value: Element.prototype.animate, configurable: true });
    delete Element.prototype.animate;
    let nextId = 0;
    const callbacks = new Map();
    window.requestAnimationFrame = callback => { callbacks.set(++nextId, callback); return nextId; };
    window.cancelAnimationFrame = id => callbacks.delete(id);
    const cssClocks = new WeakMap();
    window.__chapterTick = () => {
      const pending = [...callbacks.values()];
      callbacks.clear();
      for (const callback of pending) callback(performance.now());
      for (const animation of document.getAnimations()) {
        if (animation.timeline && !(animation.timeline instanceof DocumentTimeline)) continue;
        if (!cssClocks.has(animation)) { cssClocks.set(animation, performance.now()); animation.pause(); }
        const elapsed = performance.now() - cssClocks.get(animation);
        const end = animation.effect.getComputedTiming().endTime;
        if (Number.isFinite(end) && elapsed >= end) {
          if (animation.playState !== 'finished') animation.finish();
        } else animation.currentTime = elapsed;
      }
    };
  });
  await page.goto('http://127.0.0.1:5198/Atlas/tools/readme-clips/chapters.html', { waitUntil: 'networkidle' });
  const names = requested.length ? requested : await page.evaluate(() => window.chapterCapture.chapters);
  let width;
  let height;
  for (const name of names) {
    await page.evaluate(name => window.chapterCapture.mount(name), name);
    // Warm the assets and shaders before opening the recording pipe.
    for (let i = 0; i < 90; i++) {
      await page.clock.runFor(17);
      await page.evaluate(() => window.__chapterTick());
    }
    let encoder;
    let closed;
    if (!probe) {
      encoder = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '60', '-i', '-',
        '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '12', '-pix_fmt', 'yuv420p', path.join(output, `${name}.mp4`)], { stdio: ['pipe', 'ignore', 'inherit'] });
      closed = once(encoder, 'close');
    }
    const indices = probe ? [0, 75, 150, 225, 300] : Array.from({ length: 301 }, (_, i) => i);
    let elapsed = 0;
    for (const index of indices) {
      await page.evaluate(({ name, index }) => window.chapterCapture.frame(name, index / 300), { name, index });
      const target = Math.round(index * 1000 / 60);
      await page.clock.runFor(Math.max(1, target - elapsed));
      elapsed = target;
      await page.evaluate(() => window.__chapterTick());
      const screenshot = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, optimizeForSpeed: true, captureBeyondViewport: false });
      const bytes = Buffer.from(screenshot.data, 'base64');
      width = bytes.readUInt32BE(16);
      height = bytes.readUInt32BE(20);
      if (probe || index === 150) await writeFile(path.join(output, `${name}-${index}.png`), bytes);
      if (encoder && !encoder.stdin.write(bytes)) await once(encoder.stdin, 'drain');
    }
    if (encoder) {
      encoder.stdin.end();
      const [code] = await closed;
      if (code !== 0) throw new Error(`${name}: ffmpeg exited ${code}`);
    }
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(`${name}: ${probe ? 'composition checked' : '301 original frames at 60 fps captured'}`);
  }
  await writeFile(path.join(output, probe ? 'probe.json' : 'capture.json'), JSON.stringify({ fps: 60, frames: 301, width, height, names, errors }, null, 2));
} finally {
  await browser?.close();
  await server.close();
}
