import { createRoot } from 'react-dom/client';
import type { CSSProperties } from 'react';
import { flushSync } from 'react-dom';
import { motionValue } from 'framer-motion';
import { JourneyOverlay, type JourneyKind } from '../../src/designs/museo-orbital/portalJourneys';
import '../../src/designs/museo-orbital/salaPortal.css';

const chapters: Record<string, { kind: JourneyKind; color: string; range: [number, number] }> = {
  intro: { kind: 'scaffold', color: '#f9d66e', range: [0.075, 0.235] },
  habitats: { kind: 'torus', color: '#20d6c7', range: [0.075, 0.225] },
  industry: { kind: 'blueprint', color: '#9ee66f', range: [0.13, 0.265] },
  planetary: { kind: 'horizon', color: '#f9d66e', range: [0.075, 0.235] },
  energy: { kind: 'dyson', color: '#54a0ff', range: [0.06, 0.22] },
  travel: { kind: 'tunnel', color: '#20d6c7', range: [0.06, 0.225] },
  stellar: { kind: 'starburst', color: '#ff7a59', range: [0.065, 0.205] },
  civilizations: { kind: 'galaxy', color: '#f05cff', range: [0.105, 0.26] },
  search: { kind: 'signal', color: '#f05cff', range: [0.08, 0.255] },
};
const progress = motionValue(0.1);
const root = createRoot(document.getElementById('root')!);

const api = {
  chapters: Object.keys(chapters),
  mount(name: string) {
    const chapter = chapters[name];
    if (!chapter) throw new Error(`Unknown chapter ${name}`);
    progress.jump(chapter.range[0]);
    const style = { '--accent': chapter.color } as CSSProperties;
    flushSync(() => root.render(
      <div key={name} className="chapter-scene" style={style}>
        <JourneyOverlay kind={chapter.kind} progress={progress} label={String(Object.keys(chapters).indexOf(name) + 1)}
          image="/Atlas/illustrations/ai/infrastructure.webp" />
      </div>,
    ));
  },
  frame(name: string, fraction: number) {
    const [start, end] = chapters[name].range;
    const eased = 0.5 - 0.5 * Math.cos(Math.PI * fraction);
    progress.jump(start + (end - start) * eased);
  },
};
Object.assign(window, { chapterCapture: api });
