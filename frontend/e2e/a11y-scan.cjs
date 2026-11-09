// Flags interactive elements without an accessible name, images without alt, and duplicate ids — on every page of every role (Arabic).
const { chromium } = require('playwright');
const WEB = 'http://localhost:5173', API = 'http://127.0.0.1:8000/api/v1';
const api = async (p, { method = 'GET', token, body } = {}) => { const r = await fetch(API + p, { method, headers: { 'content-type': 'application/json', ...(token && { authorization: 'Bearer ' + token }) }, body: body && JSON.stringify(body) }); const t = await r.text(); if (!r.ok) throw new Error(p + ' ' + r.status); return t ? JSON.parse(t) : null; };
const sfx = Math.random().toString(36).slice(2, 7);
const check = () => {
  const name = (e) => {
    const al = e.getAttribute('aria-label'); if (al && al.trim()) return al;
    const lb = e.getAttribute('aria-labelledby'); if (lb && lb.split(' ').some((i) => document.getElementById(i)?.innerText.trim())) return 'x';
    if (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) return 'x';
    if (e.closest('label')) return 'x';
    if ((e.getAttribute('alt') || '').trim()) return e.getAttribute('alt');
    if ((e.innerText || '').trim()) return e.innerText;
    if (e.getAttribute('title')) return e.getAttribute('title');
    if (e.querySelector('img[alt]:not([alt=""])')) return 'x';
    return '';
  };
  const bad = [];
  document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[role=button]').forEach((e) => { if (!e.offsetParent && getComputedStyle(e).position !== 'fixed') return; if (!name(e)) bad.push(`${e.tagName.toLowerCase()}${e.type ? '[' + e.type + ']' : ''} .${(e.className || '').toString().split(' ').slice(0, 3).join('.')} ${(e.outerHTML || '').slice(0, 90)}`); });
  document.querySelectorAll('img:not([alt])').forEach((e) => bad.push('img without alt ' + (e.src || '').slice(-40)));
  const ids = {}; document.querySelectorAll('[id]').forEach((e) => { ids[e.id] = (ids[e.id] || 0) + 1; }); Object.entries(ids).filter(([, n]) => n > 1).forEach(([i]) => bad.push('duplicate id ' + i));
  return bad;
};
(async () => {
  const adm = (await api('/auth/login', { method: 'POST', body: { identifier: 'e2e.admin@example.com', password: 'AdminPass123' } })).access_token;
  const sup = `a11y.sup.${sfx}@example.com`, tech = `a11y.tech.${sfx}@example.com`, phone = '011' + String(Math.floor(10000000 + Math.random() * 89999999));
  await api('/admin/staff', { method: 'POST', token: adm, body: { name: 'مشرف', email: sup, password: 'SupPass12345', role: 'supervisor' } });
  await api('/admin/staff', { method: 'POST', token: adm, body: { name: 'فني', email: tech, password: 'TechPass12345', role: 'technician' } });
  await api('/auth/register', { method: 'POST', body: { name: 'مواطن', phone, password: 'CitPass12345' } });
  const cit = (await api('/auth/login', { method: 'POST', body: { identifier: phone, password: 'CitPass12345' } })).access_token;
  const t = await api('/tickets', { method: 'POST', token: cit, body: { description: 'عمود إنارة مكسور أمام المدرسة', title: 'عمود إنارة', lat: 30.05, lng: 31.24 } });
  const b = await chromium.launch(); const res = {};
  const run = async (label, id, pw, role, pages) => {
    const ctx = await b.newContext({ viewport: { width: 1100, height: 800 } }); await ctx.addInitScript(() => { try { if (!localStorage.getItem('s')) { localStorage.setItem('s', '1'); localStorage.setItem('egc.lang', 'ar'); } } catch {} });
    const p = await ctx.newPage();
    if (id) { await p.goto(WEB + '/login'); await p.locator('input').first().fill(id); await p.locator('input[type=password]').fill(pw); await p.locator('button[type=submit]').click(); await p.waitForURL('**/' + role, { timeout: 10000 }).catch(() => {}); }
    for (const pg of pages) { await p.goto(WEB + pg.replace(':id', t.id)); await p.waitForTimeout(1000); const bad = await p.evaluate(check); if (bad.length) res[label + ' ' + pg] = [...new Set(bad)]; }
    await ctx.close();
  };
  await run('public', null, null, null, ['/', '/login', '/register']);
  await run('citizen', phone, 'CitPass12345', 'citizen', ['/citizen', '/citizen/new', '/citizen/tickets', '/citizen/tickets/:id', '/citizen/notifications', '/citizen/profile']);
  await run('supervisor', sup, 'SupPass12345', 'supervisor', ['/supervisor', '/supervisor/incidents', '/supervisor/incidents/:id', '/supervisor/notifications']);
  await run('technician', tech, 'TechPass12345', 'technician', ['/technician', '/technician/tasks', '/technician/notifications']);
  await run('admin', 'e2e.admin@example.com', 'AdminPass123', 'admin', ['/admin', '/admin/users', '/admin/departments', '/admin/categories', '/admin/teams', '/admin/audit-logs']);
  await b.close(); const k = Object.keys(res); console.log(k.length ? 'ACCESSIBILITY FINDINGS' : 'No unnamed controls found');
  k.forEach((x) => console.log('\n' + x + '\n  ' + res[x].join('\n  ')));
})().catch((e) => { console.error(e); process.exit(1); });
