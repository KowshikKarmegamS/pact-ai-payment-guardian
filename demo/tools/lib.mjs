// Shared recorder: drives the installed Chrome at 1920x1080 and saves frames straight from the browser
// (CDP screencast), so there is no desktop, no browser chrome and no dev tools in the picture.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A visible cursor for the recording (headless Chrome draws none). Purely cosmetic overlay.
const CURSOR_SCRIPT = `
(() => {
  if (window.__pactCursor) return;
  const install = () => {
    if (window.__pactCursor || !document.body) return;
    const c = document.createElement('div');
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;' +
      'background:rgba(255,255,255,.28);border:2px solid rgba(255,255,255,.9);box-shadow:0 2px 10px rgba(0,0,0,.45);' +
      'z-index:2147483647;pointer-events:none;transition:transform .12s ease,background .12s ease;transform:translate(-100px,-100px)';
    document.body.appendChild(c);
    window.__pactCursor = c;
    let x = -100, y = -100, s = 1;
    const draw = () => { c.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')'; };
    addEventListener('mousemove', (e) => { x = e.clientX; y = e.clientY; draw(); }, true);
    addEventListener('mousedown', () => { s = 0.7; c.style.background = 'rgba(124,140,255,.7)'; draw(); }, true);
    addEventListener('mouseup', () => { s = 1; c.style.background = 'rgba(255,255,255,.28)'; draw(); }, true);
  };
  if (document.body) install(); else addEventListener('DOMContentLoaded', install);
})();`;

export async function launch({ headless = true, cursor = true } = {}) {
  const context = await chromium.launchPersistentContext(path.join(HERE, '.profile'), {
    channel: 'chrome',
    headless,
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    locale: 'en-US',
    args: ['--hide-scrollbars', '--disable-blink-features=AutomationControlled', `--window-size=${WIDTH},${HEIGHT + 90}`],
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  });
  if (cursor) await context.addInitScript(CURSOR_SCRIPT);
  const page = context.pages()[0] ?? (await context.newPage());
  return { context, page };
}

/** Frame recorder. Frames arrive only when the picture changes; timestamps let ffmpeg rebuild real timing. */
export class Recorder {
  constructor(page, take) {
    this.page = page;
    this.dir = path.join(HERE, 'frames', take);
    fs.rmSync(this.dir, { recursive: true, force: true });
    fs.mkdirSync(this.dir, { recursive: true });
    this.frames = [];
    this.markers = [];
    this.suppress = false; // true while anything private (a login form) may be on screen
    this.n = 0;
  }

  async start() {
    this.cdp = await this.page.context().newCDPSession(this.page);
    this.cdp.on('Page.screencastFrame', async (f) => {
      try {
        if (!this.suppress) {
          const file = `${String(++this.n).padStart(6, '0')}.jpg`;
          fs.writeFileSync(path.join(this.dir, file), Buffer.from(f.data, 'base64'));
          this.frames.push({ file, t: f.metadata.timestamp ?? Date.now() / 1000 });
        }
        await this.cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId });
      } catch {
        /* page navigated mid-frame */
      }
    });
    await this.cdp.send('Page.startScreencast', { format: 'jpeg', quality: 93, maxWidth: WIDTH, maxHeight: HEIGHT, everyNthFrame: 1 });
  }

  mark(name) {
    this.markers.push({ name, t: Date.now() / 1000 });
    console.log(`  [mark] ${name}`);
  }

  async stop() {
    try {
      await this.cdp.send('Page.stopScreencast');
    } catch {
      /* already gone */
    }
    const end = Date.now() / 1000;
    fs.writeFileSync(path.join(this.dir, 'frames.json'), JSON.stringify({ frames: this.frames, markers: this.markers, end }, null, 1));
    console.log(`saved ${this.frames.length} frames, ${this.markers.length} markers -> ${this.dir}`);
  }
}

/** Human-looking pointer helpers. */
export function pointer(page) {
  let pos = { x: WIDTH / 2, y: HEIGHT / 2 };
  const moveTo = async (x, y, steps = 28) => {
    const from = { ...pos };
    for (let i = 1; i <= steps; i += 1) {
      const k = i / steps;
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; // ease in-out
      await page.mouse.move(from.x + (x - from.x) * e, from.y + (y - from.y) * e);
      await sleep(12);
    }
    pos = { x, y };
  };
  const center = async (locator) => {
    await locator.scrollIntoViewIfNeeded();
    const b = await locator.boundingBox();
    if (!b) throw new Error('element not visible');
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  };
  return {
    moveTo,
    hover: async (locator) => {
      const c = await center(locator);
      await moveTo(c.x, c.y);
    },
    click: async (locator, { pause = 350 } = {}) => {
      const c = await center(locator);
      await moveTo(c.x, c.y);
      await sleep(pause);
      await page.mouse.down();
      await sleep(90);
      await page.mouse.up();
    },
    type: async (locator, text, delay = 26) => {
      const c = await center(locator);
      await moveTo(c.x, c.y);
      await sleep(200);
      await page.mouse.click(c.x, c.y);
      await page.keyboard.type(text, { delay });
    },
    scroll: async (dy, ms = 1200) => {
      const steps = Math.max(1, Math.round(ms / 16));
      for (let i = 0; i < steps; i += 1) {
        await page.mouse.wheel(0, dy / steps);
        await sleep(16);
      }
    },
  };
}
