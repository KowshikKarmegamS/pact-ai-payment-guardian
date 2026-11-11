// Captures README screenshots from the running app (default: demo server on :8002).
//   node screenshots.mjs <blocked-id> <captured-id> <voided-id> <agent-request-id>
// Writes docs/screenshots/*.jpg. Headless Chrome, no cursor, no browser chrome.
import { chromium } from 'playwright-core';
import path from 'node:path';
import { HERE, sleep } from './lib.mjs';

const BASE = process.env.PACT_URL ?? 'http://localhost:8002';
const OUT = path.join(HERE, '..', '..', 'docs', 'screenshots');
const [blocked, captured, voided, agentReq] = process.argv.slice(2);
if (!agentReq) throw new Error('usage: node screenshots.mjs <blocked> <captured> <voided> <agent-request>');

const shots = [
  ['control-center', '/', 'Authorized spending'],
  ['agents', '/agents', 'Connected agents'],
  ['blocked-125', `/proposals/${blocked}`, 'Blocked by the policy engine'],
  ['captured-89', `/proposals/${captured}`, 'Payment captured and verified with PayPal'],
  ['price-change-voided', `/proposals/${voided}`, 'What changed'],
  ['agent-request', `/proposals/${agentReq}`, 'Requested by'],
  ['audit-trail', '/audit', 'Security & audit trail'],
];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function capture(name, url, text, viewport, scale) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: scale, colorScheme: 'dark' });
  await page.goto(BASE + url, { waitUntil: 'networkidle' });
  await page.getByText(text).first().waitFor({ timeout: 20000 });
  await sleep(1200); // let entrance animations settle
  const file = path.join(OUT, `${name}.jpg`);
  await page.screenshot({ path: file, type: 'jpeg', quality: 86 });
  console.log('saved', path.relative(path.join(HERE, '..', '..'), file));
  await page.close();
}
for (const [name, url, text] of shots) await capture(name, url, text, { width: 1440, height: 900 }, 1);
await capture('mobile-control-center', '/', 'Authorized spending', { width: 390, height: 844 }, 2);
await capture('mobile-captured', `/proposals/${captured}`, 'Payment captured and verified with PayPal', { width: 390, height: 844 }, 2);
await browser.close();
