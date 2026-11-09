// Finds Latin-script text visible in the ARABIC UI (text nodes + placeholder/aria-label/title/alt/option) on every page, plus error states.
const { chromium } = require('playwright');
const WEB = 'http://localhost:5173', API = 'http://127.0.0.1:8000/api/v1';
const api = async (p, { method = 'GET', token, body } = {}) => { const r = await fetch(API + p, { method, headers: { 'content-type': 'application/json', ...(token && { authorization: 'Bearer ' + token }) }, body: body && JSON.stringify(body) }); const t = await r.text(); if (!r.ok) throw new Error(p + ' ' + r.status + ' ' + t.slice(0, 150)); return t ? JSON.parse(t) : null; };
const login = async (id, pw) => (await api('/auth/login', { method: 'POST', body: { identifier: id, password: pw } })).access_token;
const sfx = Math.random().toString(36).slice(2, 7);
const ALLOW = /^(EG|Civic|Operations|GPS|AI|ID|OSM|OpenStreetMap|Esri|Leaflet|Nominatim|km|m|PDF|MB|KB)$/i;
const scan = () => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { const el = n.parentElement; if (!el || /SCRIPT|STYLE/.test(el.tagName) || !el.offsetParent && getComputedStyle(el).position !== 'fixed') continue; const t = n.textContent.trim(); if (/[A-Za-z]{2,}/.test(t)) out.push('text: ' + t.slice(0, 90)); }
  document.querySelectorAll('[placeholder],[aria-label],[title],img[alt]').forEach((e) => ['placeholder', 'aria-label', 'title', 'alt'].forEach((a) => { const v = e.getAttribute(a); if (v && /[A-Za-z]{2,}/.test(v)) out.push(`${a}: ${v.slice(0, 90)}`); }));
  return out;
};
const keep = (list) => list.filter((s) => { const v = s.replace(/^[a-z-]+: /, ''); const words = v.match(/[A-Za-z][A-Za-z.\-']+/g) || []; return words.some((x) => !ALLOW.test(x)); });
(async () => {
  const admin = await login('e2e.admin@example.com', 'AdminPass123');
  const sup = { email: `l.sup.${sfx}@example.com`, pw: 'SupPass12345' }, tech = { email: `l.tech.${sfx}@example.com`, pw: 'TechPass12345' };
  await api('/admin/staff', { method: 'POST', token: admin, body: { name: 'مشرف اختبار', email: sup.email, password: sup.pw, role: 'supervisor' } });
  await api('/admin/staff', { method: 'POST', token: admin, body: { name: 'فني اختبار', email: tech.email, password: tech.pw, role: 'technician' } });
  const phone = '011' + String(Math.floor(10000000 + Math.random() * 89999999));
  await api('/auth/register', { method: 'POST', body: { name: 'مواطن اختبار', phone, password: 'CitPass12345' } });
  const cit = await login(phone, 'CitPass12345');
  const t = await api('/tickets', { method: 'POST', token: cit, body: { description: 'عمود إنارة مكسور أمام المدرسة', title: 'عمود إنارة مكسور', lat: 30.05, lng: 31.24, address: 'شارع التحرير', governorate: 'القاهرة', city: 'القاهرة' } });
  const browser = await chromium.launch(); const res = {};
  const roles = [
    ['citizen', phone, 'CitPass12345', ['', '/new', '/tickets', `/tickets/${t.id}`, '/notifications', '/profile']],
    ['supervisor', sup.email, sup.pw, ['', '/incidents', `/incidents/${t.id}`, '/notifications']],
    ['technician', tech.email, tech.pw, ['', '/tasks', '/notifications']],
    ['admin', 'e2e.admin@example.com', 'AdminPass123', ['', '/users', '/departments', '/categories', '/teams', '/audit-logs']],
  ];
  const mk = async () => { const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } }); await ctx.addInitScript(() => { try { if (!localStorage.getItem('s')) { localStorage.setItem('s', '1'); localStorage.setItem('egc.lang', 'ar'); } } catch {} }); return ctx; };
  const add = (k, l) => { const f = keep(l); if (f.length) res[k] = [...new Set([...(res[k] || []), ...f])]; };
  // public + error states
  { const ctx = await mk(); const p = await ctx.newPage();
    for (const u of ['/', '/login', '/register']) { await p.goto(WEB + u); await p.waitForTimeout(700); add('public ' + u, await p.evaluate(scan)); }
    await p.goto(WEB + '/login'); await p.locator('input').first().fill('01000000000'); await p.locator('input[type=password]').fill('wrongpass123'); await p.locator('button[type=submit]').click(); await p.waitForTimeout(1200); add('login wrong password', await p.evaluate(scan));
    await p.goto(WEB + '/login'); await p.locator('button[type=submit]').click(); await p.waitForTimeout(500); add('login empty submit', await p.evaluate(scan));
    await p.goto(WEB + '/register'); await p.locator('button[type=submit]').click(); await p.waitForTimeout(500); add('register empty submit', await p.evaluate(scan));
    await p.goto(WEB + '/register'); const ins = p.locator('input'); await ins.nth(0).fill('abc'); await ins.nth(1).fill('123'); await ins.nth(2).fill('123'); await p.locator('button[type=submit]').click(); await p.waitForTimeout(500); add('register invalid values', await p.evaluate(scan));
    await p.goto(WEB + '/register'); await p.locator('input').nth(0).fill('مواطن اختبار ثالث رابع'); await p.locator('input').nth(1).fill(phone); await p.locator('input[type=password]').fill('CitPass12345'); await p.locator('button[type=submit]').click(); await p.waitForTimeout(1500); add('register duplicate phone', await p.evaluate(scan));
    await ctx.close(); }
  for (const [role, id, pw, pages] of roles) {
    const ctx = await mk(); const p = await ctx.newPage();
    await p.goto(WEB + '/login'); await p.locator('input').first().fill(id); await p.locator('input[type=password]').fill(pw); await p.locator('button[type=submit]').click(); await p.waitForURL('**/' + role, { timeout: 10000 }).catch(() => {});
    for (const pg of pages) { await p.goto(`${WEB}/${role}${pg}`); await p.waitForTimeout(1000); add(`${role}${pg.replace(t.id, ':id') || '/'}`, await p.evaluate(scan)); }
    if (role === 'citizen') { await p.goto(WEB + '/citizen/new'); await p.waitForTimeout(800); const sb = p.locator('button[type=submit]'); if (await sb.count()) { await sb.first().click().catch(() => {}); await p.waitForTimeout(600); add('citizen/new empty submit', await p.evaluate(scan)); } }
    if (role === 'supervisor') { await p.goto(`${WEB}/supervisor/incidents/${t.id}`); await p.waitForTimeout(800); for (const b of await p.locator('button:visible').all()) { const tx = (await b.innerText().catch(() => '')).trim(); if (/تحليل|مراجعة|تشغيل/.test(tx)) { await b.click().catch(() => {}); await p.waitForTimeout(1800); add('supervisor trigger AI', await p.evaluate(scan)); break; } } }
    if (role === 'admin') { await p.goto(WEB + '/admin/users'); await p.waitForTimeout(800); for (const b of await p.locator('button:visible').all()) { const tx = (await b.innerText().catch(() => '')).trim(); if (/إضافة|إنشاء|موظف/.test(tx)) { await b.click().catch(() => {}); await p.waitForTimeout(700); add('admin users create modal', await p.evaluate(scan)); break; } } }
    await ctx.close();
  }
  await browser.close();
  const keys = Object.keys(res); console.log(keys.length ? 'LATIN TEXT IN ARABIC UI:' : 'No Latin text found in Arabic UI.');
  for (const k of keys) console.log('\n' + k + '\n  ' + res[k].join('\n  '));
})().catch((e) => { console.error(e); process.exit(1); });
