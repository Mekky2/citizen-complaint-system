// Session isolation: four tabs of ONE browser context (shared storage origin), each signed in as a different role.
const { chromium } = require('playwright');
const WEB = 'http://localhost:5173', API = 'http://127.0.0.1:8000/api/v1';
const sfx = Math.random().toString(36).slice(2, 7);
const api = async (p, { method = 'GET', token, body } = {}) => { const r = await fetch(API + p, { method, headers: { 'content-type': 'application/json', ...(token && { authorization: 'Bearer ' + token }) }, body: body && JSON.stringify(body) }); const t = await r.text(); if (!r.ok) throw new Error(p + ' ' + r.status + t.slice(0, 120)); return t ? JSON.parse(t) : null; };
let fails = 0; const ok = (n, c, x = '') => { console.log(`${c ? 'PASS' : 'FAIL'} ${n} ${x}`); if (!c) fails++; };
(async () => {
  const adm = (await api('/auth/login', { method: 'POST', body: { identifier: 'e2e.admin@example.com', password: 'AdminPass123' } })).access_token;
  const sup = `m.sup.${sfx}@example.com`, tech = `m.tech.${sfx}@example.com`, phone = '011' + String(Math.floor(10000000 + Math.random() * 89999999));
  await api('/admin/staff', { method: 'POST', token: adm, body: { name: 'مشرف', email: sup, password: 'SupPass12345', role: 'supervisor' } });
  await api('/admin/staff', { method: 'POST', token: adm, body: { name: 'فني', email: tech, password: 'TechPass12345', role: 'technician' } });
  await api('/auth/register', { method: 'POST', body: { name: 'مواطن', phone, password: 'CitPass12345' } });
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1100, height: 800 } });
  const who = [['admin', 'e2e.admin@example.com', 'AdminPass123'], ['citizen', phone, 'CitPass12345'], ['technician', tech, 'TechPass12345'], ['supervisor', sup, 'SupPass12345']];
  const pages = {};
  for (const [role, id, pw] of who) {
    const p = await ctx.newPage(); pages[role] = p;
    await p.goto(WEB + '/login'); await p.locator('input').first().fill(id); await p.locator('input[type=password]').fill(pw); await p.locator('button[type=submit]').click();
    await p.waitForURL('**/' + role, { timeout: 10000 }).catch(() => {});
    ok(`tab ${role}: landed on /${role}`, p.url().endsWith('/' + role), p.url());
  }
  for (const [role] of who) { await pages[role].reload(); await pages[role].waitForTimeout(1200); ok(`tab ${role}: still ${role} after reload (other tabs signed in)`, pages[role].url().endsWith('/' + role), pages[role].url()); }
  // logging out in one tab must not log out the others
  await pages.citizen.evaluate(() => sessionStorage.clear()); await pages.citizen.reload(); await pages.citizen.waitForTimeout(1000);
  ok('citizen tab signed out locally', pages.citizen.url().includes('/login') || !pages.citizen.url().endsWith('/citizen'), pages.citizen.url());
  await pages.admin.reload(); await pages.admin.waitForTimeout(1000); ok('admin tab unaffected by citizen sign-out', pages.admin.url().endsWith('/admin'), pages.admin.url());
  const ls = await pages.admin.evaluate(() => Object.keys(localStorage).filter((k) => /egco/.test(k)));
  ok('no auth tokens in localStorage', ls.length === 0, JSON.stringify(ls));
  // role guard: admin tab cannot open a supervisor page
  await pages.admin.goto(WEB + '/supervisor/incidents'); await pages.admin.waitForTimeout(800); ok('admin tab blocked from /supervisor', !pages.admin.url().includes('/supervisor/incidents'), pages.admin.url());
  await b.close(); console.log(fails ? `\n${fails} FAILED` : '\nall passed'); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
