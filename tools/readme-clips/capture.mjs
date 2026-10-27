/* global window, document, Element, Node, localStorage, performance, DocumentTimeline, getComputedStyle */
/** Capture the real opening on one clock, including Motion and CSS animations.
 * Usage: node tools/readme-clips/capture.mjs <output-dir> [--probe]
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import process from 'node:process';
import console from 'node:console';
import { setTimeout as delay } from 'node:timers/promises';
import { Buffer } from 'node:buffer';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { chromium } from '@playwright/test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.resolve(process.argv[2] ?? path.join(root, 'tmp/readme-hero'));
const probe = process.argv.includes('--probe');
await mkdir(output, { recursive: true });
const server = await createServer({ root, server: {
  host: '127.0.0.1', port: 5198, strictPort: true,
  fs: { allow: [root, realpathSync(path.join(root, 'node_modules'))] },
}, logLevel: 'error' });
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ headless: true, channel: 'chromium', args: [
    '--use-angle=d3d11', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
  ] });
  const page = await browser.newPage({ viewport: { width: 1260, height: 540 }, deviceScaleFactor: 1840 / 1260, reducedMotion: 'no-preference' });
  const cdp = await page.context().newCDPSession(page);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.clock.install({ time: new Date('2026-01-01T00:00:00Z') });
  await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
  await page.addInitScript(() => {
    // Motion's native WAAPI timeline uses wall time. Its JS implementation
    // instead shares the controlled RAF/performance clock with the WebGL scene.
    // Keep direct element.animate() calls available, while Motion's feature
    // detection (an own property on Element.prototype) selects its JS driver.
    Object.defineProperty(Node.prototype, 'animate', { value: Element.prototype.animate, configurable: true });
    delete Element.prototype.animate;
    localStorage.setItem('mo-locale', 'es');
    // One RAF per output frame. Playwright's default 16 ms RAF cadence would
    // otherwise occasionally run two scene updates in a 60 fps capture frame.
    let nextId = 0;
    const callbacks = new Map();
    window.requestAnimationFrame = callback => { callbacks.set(++nextId, callback); return nextId; };
    window.cancelAnimationFrame = id => callbacks.delete(id);
    window.__captureTick = () => {
      const pending = [...callbacks.values()];
      callbacks.clear();
      for (const callback of pending) callback(performance.now());
    };
    const cssClocks = new WeakMap();
    window.__syncCaptureCSS = () => {
      const now = performance.now();
      for (const animation of document.getAnimations()) {
        if (animation.timeline && !(animation.timeline instanceof DocumentTimeline)) continue;
        if (!cssClocks.has(animation)) {
          cssClocks.set(animation, now);
          animation.pause();
        }
        const elapsed = now - cssClocks.get(animation);
        const end = animation.effect.getComputedTiming().endTime;
        if (Number.isFinite(end) && elapsed >= end) {
          if (animation.playState !== 'finished') animation.finish();
        } else animation.currentTime = elapsed;
      }
    };
  });
  await page.goto('http://127.0.0.1:5198/Atlas/', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: '.mo-cursor { visibility: hidden !important; }' });
  await page.mouse.move(1250, 530);
  console.log(JSON.stringify(await page.evaluate(() => ({
    living: document.querySelector('.mo-hero')?.classList.contains('is-living'),
    font: getComputedStyle(document.querySelector('h1')).fontFamily,
    canvases: document.querySelectorAll('canvas').length,
  }))));
  if (!(await page.locator('.mo-hero').evaluate(hero => hero.classList.contains('is-living')))) {
    throw new Error('Hardware WebGL is required to record the living star.');
  }
  await page.evaluate(async () => {
    const { livingSignal } = await import('/Atlas/src/designs/museo-orbital/living/livingHero.ts');
    window.__captureLiving = livingSignal;
  });
  // Compile shaders before recording, and begin at the flight's first frame.
  for (let i = 0; i < 120; i++) {
    await page.clock.runFor(16);
    await page.evaluate(() => { window.__captureTick(); window.__syncCaptureCSS(); });
    if (await page.evaluate(() => window.__captureLiving.flight.active)) break;
    await delay(20);
  }
  if (!(await page.evaluate(() => window.__captureLiving.flight.active))) throw new Error('Nebula flight did not start.');
  const telemetry = [];
  const fps = 60;
  const frames = Math.round(11 * fps);
  let advanced = 0;
  for (let i = 0; i < frames; i++) {
    const target = Math.round((i + 1) * 1000 / fps);
    await page.clock.runFor(target - advanced);
    advanced = target;
    await page.evaluate(() => { window.__captureTick(); window.__syncCaptureCSS(); });
    if (!probe || i % 30 === 0) {
      const screenshot = await cdp.send('Page.captureScreenshot', {
        format: 'png', fromSurface: true, captureBeyondViewport: false, optimizeForSpeed: true,
      });
      await writeFile(path.join(output, `${String(i).padStart(4, '0')}.png`), Buffer.from(screenshot.data, 'base64'));
    }
    if (i % 15 === 0) telemetry.push(await page.evaluate(() => {
      const hero = document.querySelector('.mo-hero');
      return {
        time: performance.now(), hero: hero.className, flight: hero.getAttribute('data-flight'),
        letters: [...document.querySelectorAll('.mo-hero-letter')].map(letter => {
          const style = getComputedStyle(letter);
          return { opacity: style.opacity, transform: style.transform, filter: style.filter };
        }),
      };
    }));
    if (i % 60 === 0) console.log(`Captured ${(i / fps).toFixed(0)} / ${frames / fps}s`);
  }
  await writeFile(path.join(output, 'capture.json'), JSON.stringify({ fps, frames, errors, telemetry }, null, 2));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(`Capture complete: ${output}`);
} finally {
  await browser?.close();
  await server.close();
}
