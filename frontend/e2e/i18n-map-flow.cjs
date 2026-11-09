// EN + light-theme smoke test and map-logic test against the live stack.
// Needs backend (8000), `npm run dev` (5173) and an e2e.admin@example.com / AdminPass123 account.
const { chromium } = require('playwright');
const fs = require('fs');
const WEB = 'http://localhost:5173', API = 'http://127.0.0.1:8000/api/v1';
const OUT = process.env.SHOTS || '/tmp/claude-0/shots9'; fs.mkdirSync(OUT, { recursive: true });
const results = []; const errors = [];
const step = async (n, fn) => { try { await fn(); results.push(['PASS', n]); console.log('PASS', n); } catch (e) { results.push(['FAIL', n, e.message.split('\n')[0]]); console.log('FAIL', n, '-', e.message.split('\n')[0]); } };
const sfx = Math.random().toString(36).slice(2, 7);
const phone = '010' + String(Math.floor(10000000 + Math.random() * 89999999));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, geolocation: { latitude: 30.0444, longitude: 31.2357, accuracy: 9 }, permissions: ['geolocation'], deviceScaleFactor: 1 });
  await ctx.addInitScript(() => { if (!localStorage.getItem('egc.seeded')) { localStorage.setItem('egc.seeded', '1'); localStorage.setItem('egc.lang', 'en'); localStorage.setItem('egc.theme', 'light'); } });
  // Nominatim is not reachable from the sandbox: answer with realistic payloads so the UI logic is exercised.
  await ctx.route('**/nominatim.openstreetmap.org/search**', (r) => r.fulfill({ json: [{ place_id: 1, display_name: 'Tahrir Square, Cairo, Egypt', lat: '30.0444', lon: '31.2357' }, { place_id: 2, display_name: 'Tahrir Street, Giza, Egypt', lat: '30.0600', lon: '31.2100' }] }));
  await ctx.route('**/nominatim.openstreetmap.org/reverse**', (r) => r.fulfill({ json: { display_name: 'Tahrir Square, Cairo', address: { road: 'Tahrir Square', state: 'Cairo Governorate', city: 'Cairo' } } }));
  const p = await ctx.newPage();
  p.on('console', (m) => { if (['error', 'warning'].includes(m.type()) && !/tile|ERR_|Failed to load resource|fonts\.g/i.test(m.text())) errors.push(m.text().slice(0, 200)); });
  p.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  const missing = async () => p.evaluate(() => [...(window.__missingI18n || [])]);

  await step('EN: login page is LTR + English + light', async () => {
    await p.goto(WEB + '/login');
    await p.getByRole('heading', { name: 'Sign in' }).waitFor({ timeout: 8000 });
    const d = await p.evaluate(() => [document.documentElement.dir, document.documentElement.lang, document.documentElement.dataset.theme]);
    if (d.join() !== 'ltr,en,light') throw new Error('got ' + d.join());
    await p.screenshot({ path: `${OUT}/en-light-login.png` });
  });
  await step('EN: register citizen with valid national ID shows age/gov', async () => {
    await p.goto(WEB + '/register');
    await p.getByLabel('Full name', { exact: false }).first().fill('مواطن اختبار رباعي كامل');
    await p.getByLabel('Mobile number').first().fill(phone);
    await p.getByLabel('National ID').fill('2900101' + '01' + String(Math.floor(1000 + Math.random() * 8999)) + '7');
    await p.getByText('Verified — born 01/01/1990').waitFor({ timeout: 4000 });
    await p.getByLabel('Password').fill('CitizenPass123');
    await p.getByRole('button', { name: 'Create account' }).click();
    await p.waitForURL('**/citizen', { timeout: 10000 });
    await p.waitForTimeout(600);
    await p.screenshot({ path: `${OUT}/en-light-citizen-dashboard.png` });
  });

  await step('map: GPS best-fix shows accuracy chip, pin placed, coords filled', async () => {
    await p.goto(WEB + '/citizen/new');
    await p.getByText('GPS accuracy ±9 m').waitFor({ timeout: 8000 });
    await p.getByText('Excellent', { exact: false }).first().waitFor();
    const coords = await p.locator('#coords').inputValue();
    if (!coords.startsWith('30.0444')) throw new Error('coords ' + coords);
    await p.screenshot({ path: `${OUT}/en-light-report-form.png`, fullPage: true });
  });
  await step('map: address search -> pick result -> pin + address autofill', async () => {
    await p.getByLabel('Search for an address').fill('Tahrir');
    await p.getByRole('button', { name: 'Search', exact: true }).click();
    await p.getByRole('button', { name: /Tahrir Street, Giza/ }).click();
    await p.waitForTimeout(1200);
    const coords = await p.locator('#coords').inputValue();
    if (!coords.startsWith('30.060000, 31.210000')) throw new Error('coords ' + coords);
    if (await p.getByText('GPS accuracy').count()) throw new Error('accuracy chip should clear after manual pick');
    const street = await p.getByLabel('Street / address').inputValue();
    if (street !== 'Tahrir Square') throw new Error('street ' + street);
  });
  await step('map: typed coordinates move the pin; invalid text is rejected', async () => {
    await p.locator('#coords').fill('abc'); await p.locator('#coords').press('Enter');
    await p.getByText('Enter coordinates like this').waitFor({ timeout: 3000 });
    await p.locator('#coords').fill('31.2001, 29.9187'); await p.locator('#coords').press('Enter');
    await p.waitForTimeout(300);
    if (!(await p.locator('#coords').inputValue()).startsWith('31.2001')) throw new Error('not applied');
  });
  await step('map: outside-Egypt warning appears', async () => {
    await p.locator('#coords').fill('48.8566, 2.3522'); await p.locator('#coords').press('Enter');
    await p.getByText('This location is outside Egypt').waitFor({ timeout: 3000 });
    await p.locator('#coords').fill('30.0444, 31.2357'); await p.locator('#coords').press('Enter');
  });
  await step('map: satellite layer is selectable', async () => {
    await p.locator('.leaflet-control-layers').hover();
    await p.getByText('Satellite', { exact: true }).click();
    await p.locator('img.leaflet-tile[src*="World_Imagery"]').first().waitFor({ state: 'attached', timeout: 5000 });
  });
  await step('EN: submit report (search Enter does not submit the form)', async () => {
    await p.getByLabel('Search for an address').fill('Tahrir'); await p.getByLabel('Search for an address').press('Enter');
    await p.waitForTimeout(500);
    if (await p.getByText('We received your report').count()) throw new Error('search Enter submitted the report');
    await p.getByLabel('Problem description').fill('A large deep pothole in the middle of the street blocks traffic.');
    await p.getByRole('button', { name: 'Submit report' }).click();
    await p.getByText('We received your report').waitFor({ timeout: 12000 });
    await p.screenshot({ path: `${OUT}/en-light-report-success.png` });
    await p.getByRole('link', { name: 'Track ticket' }).click();
    await p.waitForURL(/\/citizen\/tickets\/[0-9a-f-]{36}/);
    await p.getByText('Submitted', { exact: true }).first().waitFor();
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${OUT}/en-light-ticket-details.png`, fullPage: true });
  });
  await step('EN: theme toggle switches to dark and persists', async () => {
    await p.getByRole('button', { name: 'Dark mode' }).click();
    if ((await p.evaluate(() => document.documentElement.dataset.theme)) !== 'dark') throw new Error('not dark');
    await p.reload(); await p.waitForTimeout(400);
    if ((await p.evaluate(() => document.documentElement.dataset.theme)) !== 'dark') throw new Error('not persisted');
    await p.screenshot({ path: `${OUT}/en-dark-ticket-details.png` });
  });
  await step('EN: language toggle flips back to Arabic RTL and persists', async () => {
    await p.getByRole('button', { name: 'Switch to Arabic' }).click();
    await p.waitForLoadState('load'); await p.waitForTimeout(500);
    const d = await p.evaluate(() => [document.documentElement.dir, document.documentElement.lang]);
    if (d.join() !== 'rtl,ar') throw new Error('got ' + d.join());
    await p.getByText('بلاغاتي').first().waitFor();
    await p.evaluate(() => localStorage.setItem('egc.lang', 'en'));
  });

  // Staff pages in English: any key missing from the dictionary shows up in window.__missingI18n
  const adminLogin = async (pg, id, pw) => { await pg.goto(WEB + '/login'); await pg.evaluate(() => { for (const k of Object.keys(localStorage)) if (!k.startsWith('egc.')) localStorage.removeItem(k); }); await pg.goto(WEB + '/login'); await pg.getByLabel('Mobile number or email').fill(id); await pg.getByLabel('Password').fill(pw); await pg.getByRole('button', { name: 'Sign in', exact: true }).click(); };
  await step('EN: admin pages render without missing translations', async () => {
    const ap = await ctx.newPage();
    ap.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
    await adminLogin(ap, 'e2e.admin@example.com', 'AdminPass123');
    await ap.waitForURL('**/admin', { timeout: 10000 });
    for (const path of ['', '/users', '/departments', '/categories', '/teams', '/audit-logs']) { await ap.goto(WEB + '/admin' + path); await ap.waitForTimeout(700); }
    await ap.goto(WEB + '/admin/users'); await ap.waitForTimeout(500);
    await ap.screenshot({ path: `${OUT}/en-dark-admin-users.png` });
    const m = await ap.evaluate(() => [...(window.__missingI18n || [])]);
    if (m.length) throw new Error('missing: ' + JSON.stringify(m));
    await ap.close();
  });
  await step('EN: no untranslated Arabic keys on citizen pages', async () => {
    const m = await missing();
    if (m.length) throw new Error('missing: ' + JSON.stringify(m));
  });

  await browser.close();
  const fails = results.filter((r) => r[0] === 'FAIL');
  console.log(`\n${results.length - fails.length}/${results.length} passed`);
  console.log('console errors:', errors.length ? JSON.stringify([...new Set(errors)].slice(0, 8), null, 1) : 'none');
})();
