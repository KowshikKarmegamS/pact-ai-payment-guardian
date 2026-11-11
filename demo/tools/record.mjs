// Records the real PACT app. Usage: node record.mjs <take> [--headed]
//   login   open PayPal Sandbox sign-in in a visible window so a human can log in once (nothing is recorded)
//   check   report whether the PayPal Sandbox buyer session is still signed in
//   app1    Command Center, mandate, the blocked $125 purchase
//   app2    the $89 purchase: policy pass, human approval, PayPal Sandbox checkout, verified capture
//   app3    second approval invalidated by a catalog price change, audit trail, final Command Center
//   app4    Agent Gateway: connected third-party agent, its requests, and one awaiting approval
//   card:<name>  record demo/pact-demo-assets/<name>.html (title cards)
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { HERE, Recorder, launch, pointer, sleep } from './lib.mjs';

const BASE = process.env.PACT_URL ?? 'http://localhost:8002';
const take = process.argv[2];
const headed = process.argv.includes('--headed');
if (!take) throw new Error('usage: node record.mjs <take>');

const PROMPT_BLOCKED = 'Order the NuPhy Halo75 V2 wireless keyboard for my desk.';
const PROMPT_OK = 'I need a wireless mechanical keyboard for coding, under $100.';
const PROMPT_SECOND = 'Order one more Keychron K8 Pro keyboard for my teammate.';

async function ask(page, p, text) {
  await p.click(page.getByRole('link', { name: 'Reference agent' }));
  await page.getByPlaceholder('Describe what you want to buy…').waitFor();
  await sleep(700);
  await p.type(page.getByPlaceholder('Describe what you want to buy…'), text);
  await sleep(500);
  await p.click(page.getByRole('button', { name: 'Recommend' }));
}

/** The narration says Gemini made the recommendation; refuse to continue if this one was a fallback. */
async function requireGemini(page) {
  const provider = await page.evaluate(async () => (await (await fetch('/api/proposals')).json())[0]?.ai_provider);
  if (provider !== 'gemini') throw new Error(`latest recommendation came from "${provider}", not Gemini; retake`);
}

const takes = {
  async login() {
    const { context, page } = await launch({ headless: false, cursor: false });
    await page.goto('https://www.sandbox.paypal.com/signin');
    console.log('Log in with the Sandbox PERSONAL (buyer) account in the Chrome window. Waiting up to 10 minutes…');
    await page.waitForURL(/sandbox\.paypal\.com\/(myaccount|mep|webapps\/hermes|home)/, { timeout: 600000 });
    await sleep(3000);
    console.log('Signed in. Session saved in the recorder profile.');
    await context.close();
  },

  async check() {
    const { context, page } = await launch({ headless: !headed, cursor: false });
    await page.goto('https://www.sandbox.paypal.com/myaccount/summary', { waitUntil: 'domcontentloaded' });
    await sleep(5000);
    const url = page.url();
    console.log(/signin|login/.test(url) ? `NOT signed in (${new URL(url).pathname})` : `signed in (${new URL(url).pathname})`);
    await context.close();
  },

  async app1(page, p, rec) {
    await page.goto(BASE + '/');
    await page.getByText('Authorized spending').waitFor();
    await sleep(1500);
    rec.mark('dash');
    await p.moveTo(700, 420);
    await sleep(2600);
    await p.hover(page.getByText('Remaining budget'));
    await sleep(1200);
    await p.scroll(520, 1500);
    await sleep(2600);
    await p.scroll(-520, 1000);
    await sleep(600);

    await p.click(page.getByRole('link', { name: 'Mandates' }));
    await page.getByRole('heading', { name: 'Home Office Essentials' }).waitFor();
    await sleep(600);
    rec.mark('mandate');
    await p.hover(page.getByRole('heading', { name: 'Home Office Essentials' }));
    await sleep(1800);
    await p.hover(page.getByText('The AI may not').first());
    await sleep(3200);

    rec.mark('blocked_ask');
    await ask(page, p, PROMPT_BLOCKED);
    await page.getByRole('heading', { name: /NuPhy Halo75/ }).waitFor({ timeout: 60000 });
    await requireGemini(page);
    rec.mark('blocked_card');
    await sleep(900);
    await p.hover(page.getByText(/Blocked by the policy engine/).first());
    await sleep(3200);
    await p.click(page.getByRole('button', { name: 'See why it was blocked' }).first());
    await page.getByText(/Blocked by the policy engine: 1 of/).waitFor();
    await sleep(500);
    rec.mark('blocked_auth');
    await p.hover(page.getByText('Unit price within limit'));
    await sleep(3500);
    await p.hover(page.getByText('Approval and payment unavailable'));
    await sleep(3500);
    rec.mark('blocked_end');
  },

  async app2(page, p, rec) {
    await page.goto(BASE + '/assistant');
    await page.getByPlaceholder('Describe what you want to buy…').waitFor();
    await sleep(1200);
    rec.mark('ok_ask');
    await ask(page, p, PROMPT_OK);
    await page.getByRole('button', { name: 'Review & authorize' }).first().waitFor({ timeout: 60000 });
    await requireGemini(page);
    rec.mark('ok_card');
    await sleep(800);
    await p.hover(page.getByText('Why this product').first());
    await sleep(2800);
    await p.hover(page.getByText(/Policy check passed/).first());
    await sleep(2200);
    await p.click(page.getByRole('button', { name: 'Review & authorize' }).first());
    await page.getByText(/Your authorization is required/).waitFor();
    await sleep(500);
    rec.mark('ok_auth');
    await p.hover(page.getByText('Within available budget'));
    await sleep(2400);
    await p.hover(page.getByText('Remaining after'));
    await sleep(2200);
    const approve = page.getByRole('button', { name: /^Approve \$89\.00/ });
    await p.click(approve, { pause: 900 });
    await page.getByRole('button', { name: 'Continue to PayPal Checkout' }).waitFor();
    rec.mark('approved');
    await sleep(2600);

    // ---- PayPal Sandbox checkout. Frames are not saved while a login form could be visible. ----
    await p.hover(page.getByRole('button', { name: 'Continue to PayPal Checkout' }));
    await sleep(500);
    rec.mark('to_paypal');
    await page.mouse.down();
    await sleep(90);
    await page.mouse.up();
    await sleep(350);
    rec.suppress = true;
    await page.waitForURL(/sandbox\.paypal\.com/, { timeout: 60000 });
    const pay = page.getByRole('button', { name: /Complete Purchase|Pay Now|Continue to Review Order/ }).first();
    const email = page.locator('#email, input[name="login_email"]').first();
    await Promise.race([pay.waitFor({ timeout: 90000 }), email.waitFor({ timeout: 90000 })]).catch(() => undefined);
    if (!(await pay.isVisible().catch(() => false))) {
      console.log('PayPal needs a login. Sign in with the Sandbox buyer account in the window (waiting up to 5 minutes)…');
      await pay.waitFor({ timeout: 300000 });
    }
    await sleep(1500);
    rec.suppress = false;
    await page.mouse.move(900, 300);
    rec.mark('paypal_page');
    await p.moveTo(960, 420);
    await sleep(3000);
    await p.click(pay, { pause: 900 });
    rec.mark('paypal_pay');
    await page.waitForURL(new RegExp(BASE.replace(/[.:/]/g, '\\$&') + '/proposals/'), { timeout: 90000 });
    await page.getByRole('button', { name: /^Capture \$89\.00/ }).waitFor({ timeout: 60000 });
    rec.mark('verified');
    await sleep(900);
    await p.hover(page.getByText('Buyer approves in PayPal Checkout'));
    await sleep(3200);
    await p.click(page.getByRole('button', { name: /^Capture \$89\.00/ }), { pause: 900 });
    rec.mark('capture_click');
    await page.getByText('Payment captured and verified with PayPal').waitFor({ timeout: 90000 });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await sleep(700);
    rec.mark('captured');
    await sleep(900);
    await p.hover(page.getByText('PayPal capture ID'));
    await sleep(5500);
    rec.mark('captured_end');
  },

  async app3(page, p, rec) {
    await page.goto(BASE + '/assistant');
    await page.getByPlaceholder('Describe what you want to buy…').waitFor();
    await sleep(1000);
    rec.mark('second_ask');
    await ask(page, p, PROMPT_SECOND);
    await page.getByRole('button', { name: 'Review & authorize' }).first().waitFor({ timeout: 60000 });
    await requireGemini(page);
    await sleep(1500);
    await p.click(page.getByRole('button', { name: 'Review & authorize' }).first());
    await page.getByText(/Your authorization is required/).waitFor();
    await sleep(1200);
    await p.click(page.getByRole('button', { name: /^Approve \$89\.00/ }), { pause: 700 });
    await page.getByRole('button', { name: 'Continue to PayPal Checkout' }).waitFor();
    rec.mark('second_approved');
    const url = page.url();
    await sleep(2800);

    await p.click(page.getByRole('link', { name: 'Catalog' }));
    await page.getByPlaceholder('Search products…').waitFor();
    await sleep(500);
    rec.mark('catalog');
    await p.type(page.getByPlaceholder('Search products…'), 'K8 Pro', 60);
    await sleep(900);
    await p.click(page.getByRole('button', { name: /Change price of Keychron K8 Pro/ }));
    const input = page.getByLabel('New price (USD)');
    await input.waitFor();
    await sleep(600);
    await input.fill('');
    await page.keyboard.type('99.50', { delay: 110 });
    await sleep(900);
    rec.mark('price_dialog');
    await p.click(page.getByRole('button', { name: 'Update price' }), { pause: 700 });
    await page.getByText(/Price changed to \$99\.50/).waitFor();
    rec.mark('price_changed');
    await sleep(3200);

    await page.goto(url);
    await page.getByText(/Approval invalidated/).first().waitFor();
    await sleep(400);
    rec.mark('invalidated');
    await p.hover(page.getByText('What changed'));
    await sleep(6000);
    rec.mark('invalidated_end');

    await p.click(page.getByRole('link', { name: 'Audit Trail' }));
    await page.getByRole('heading', { name: 'Security & audit trail' }).waitFor();
    await sleep(900);
    rec.mark('audit');
    await p.moveTo(900, 520);
    await sleep(2200);
    await p.scroll(900, 4200);
    await sleep(1800);
    rec.mark('audit_end');

    await p.click(page.getByRole('link', { name: 'Control Center' }));
    await page.getByText('Authorized spending').waitFor();
    await sleep(900);
    rec.mark('final_dash');
    await p.hover(page.getByText('Authorized spending'));
    await sleep(4500);
    rec.mark('end');
  },

  async app4(page, p, rec) {
    await page.goto(BASE + '/agents');
    await page.getByRole('heading', { name: 'Connected agents' }).waitFor();
    await page.getByText('Gemini agent via MCP').first().waitFor();
    await sleep(1200);
    rec.mark('agents');
    await p.hover(page.getByText('Awaiting you'));
    await sleep(2200);
    await p.hover(page.getByText('What it can never do'));
    await sleep(2600);
    await p.click(page.getByText('Anker 7-in-1 USB-C Hub Adapter').first(), { pause: 500 });
    await page.getByText(/Requested by/).waitFor();
    await sleep(700);
    rec.mark('agent_request');
    await p.hover(page.getByText(/Requested by/));
    await sleep(3200);
    await p.hover(page.getByRole('button', { name: /Approve/ }));
    await sleep(2200);
    rec.mark('end');
  },
};

async function recordCard(name) {
  const { context, page } = await launch({ headless: true, cursor: false });
  const rec = new Recorder(page, `card-${name}`);
  const file = path.join(HERE, '..', 'pact-demo-assets', `${name}.html`);
  await page.goto('about:blank');
  await rec.start();
  await page.goto(pathToFileURL(file).href);
  rec.mark('start');
  const seconds = Number(await page.evaluate(() => document.body.dataset.seconds ?? '10'));
  await sleep(seconds * 1000);
  rec.mark('end');
  await rec.stop();
  await context.close();
}

if (take.startsWith('card:')) {
  await recordCard(take.slice(5));
} else if (take === 'login' || take === 'check') {
  await takes[take]();
} else {
  if (!takes[take]) throw new Error(`unknown take ${take}`);
  const { context, page } = await launch({ headless: !headed });
  const rec = new Recorder(page, take);
  const p = pointer(page);
  await page.goto(BASE + '/');
  await rec.start();
  try {
    await takes[take](page, p, rec);
  } catch (err) {
    console.error('TAKE FAILED:', err.message);
    await page.screenshot({ path: path.join(HERE, 'frames', `${take}-failure.png`) }).catch(() => undefined);
    process.exitCode = 1;
  } finally {
    await rec.stop();
    await context.close();
  }
}
