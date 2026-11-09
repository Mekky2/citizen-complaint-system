// Exploratory audit: visits every page as every role, in AR/dark/mobile and EN/light/desktop,
// and reports horizontal overflow, missing translations, console errors and error states.
const { chromium } = require('playwright'); const fs = require('fs');
const WEB = 'http://localhost:5173', API = 'http://127.0.0.1:8000/api/v1';
const OUT = process.env.SHOTS || '/tmp/claude-0/shots10'; fs.mkdirSync(OUT, { recursive: true });
const sfx = Math.random().toString(36).slice(2, 7);
const api = async (p, { method = 'GET', token, body } = {}) => { const r = await fetch(API + p, { method, headers: { 'content-type': 'application/json', ...(token && { authorization: 'Bearer ' + token }) }, body: body && JSON.stringify(body) }); const t = await r.text(); if (!r.ok) throw new Error(p + ' ' + r.status + ' ' + t.slice(0, 150)); return t ? JSON.parse(t) : null; };
const login = async (id, pw) => (await api('/auth/login', { method: 'POST', body: { identifier: id, password: pw } })).access_token;
const findings = [];
(async () => {
  const admin = await login('e2e.admin@example.com', 'AdminPass123');
  const sup = { email: `a.sup.${sfx}@example.com`, pw: 'SupPass12345' }, tech = { email: `a.tech.${sfx}@example.com`, pw: 'TechPass12345' };
  await api('/admin/staff', { method: 'POST', token: admin, body: { name: 'Supervisor Audit', email: sup.email, password: sup.pw, role: 'supervisor' } });
  await api('/admin/staff', { method: 'POST', token: admin, body: { name: 'Tech Audit', email: tech.email, password: tech.pw, role: 'technician' } });
  const phone = '011' + String(Math.floor(10000000 + Math.random() * 89999999));
  await api('/auth/register', { method: 'POST', body: { name: 'Citizen Audit ' + sfx, phone, password: 'CitPass12345' } });
  const cit = await login(phone, 'CitPass12345');
  const t = await api('/tickets', { method: 'POST', token: cit, body: { description: 'Audit ticket: a very long description '.repeat(6), title: 'Audit: broken streetlight near the school entrance on a long street name', lat: 30.05, lng: 31.24, address: 'Very long street name that should truncate or wrap nicely in cards', governorate: 'Cairo', city: 'Cairo' } });

  const browser = await chromium.launch();
  const configs = [
    { name: 'ar-dark-mobile', lang: 'ar', theme: 'dark', vp: { width: 390, height: 800 } },
    { name: 'en-light-desktop', lang: 'en', theme: 'light', vp: { width: 1280, height: 860 } },
    { name: 'ar-light-tablet', lang: 'ar', theme: 'light', vp: { width: 820, height: 900 } },
  ];
  const roles = [
    { role: 'citizen', id: phone, pw: 'CitPass12345', pages: ['', '/new', '/tickets', `/tickets/${t.id}`, '/notifications', '/profile'] },
    { role: 'supervisor', id: sup.email, pw: sup.pw, pages: ['', '/incidents', `/incidents/${t.id}`, '/notifications'] },
    { role: 'technician', id: tech.email, pw: tech.pw, pages: ['', '/tasks', '/notifications'] },
    { role: 'admin', id: 'e2e.admin@example.com', pw: 'AdminPass123', pages: ['', '/users', '/departments', '/categories', '/teams', '/audit-logs'] },
  ];
  for (const c of configs) for (const r of roles) {
    const ctx = await browser.newContext({ viewport: c.vp, geolocation: { latitude: 30.05, longitude: 31.24, accuracy: 25 }, permissions: ['geolocation'] });
    await ctx.addInitScript(([l, th]) => { if (!localStorage.getItem('egc.seeded')) { localStorage.setItem('egc.seeded', '1'); localStorage.setItem('egc.lang', l); localStorage.setItem('egc.theme', th); } }, [c.lang, c.theme]);
    const p = await ctx.newPage(); const errs = [];
    p.on('console', (m) => { if (m.type() === 'error' && !/tile|ERR_|Failed to load resource|nominatim/i.test(m.text())) errs.push(m.text().slice(0, 160)); });
    p.on('pageerror', (e) => errs.push('pageerror ' + e.message));
    await p.goto(WEB + '/login'); await p.locator('input').first().fill(r.id); await p.locator('input[type=password]').fill(r.pw); await p.locator('button[type=submit]').click();
    await p.waitForURL('**/' + r.role, { timeout: 10000 }).catch(() => findings.push(`[${c.name}/${r.role}] login did not land on /${r.role}`));
    for (const pg of r.pages) {
      await p.goto(`${WEB}/${r.role}${pg}`); await p.waitForTimeout(900);
      const info = await p.evaluate(() => ({
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        err: !!document.body.innerText.match(/حدث خطأ|Something went wrong|An unexpected error/),
        missing: [...(window.__missingI18n || [])],
        arabicInEn: document.documentElement.lang === 'en' ? [...document.body.innerText.matchAll(/[؀-ۿ][؀-ۿ\s]{2,}/g)].map((m) => m[0].trim()).slice(0, 4) : [],
        clipped: [...document.querySelectorAll('button,a,h1,h2,h3,p,span,td,th,label')].filter((e) => e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow === 'hidden' && getComputedStyle(e).textOverflow !== 'ellipsis').map((e) => (e.innerText || '').slice(0, 30)).slice(0, 3),
      }));
      const tag = `[${c.name}/${r.role}${pg || '/'}]`;
      if (info.overflowX > 1) findings.push(`${tag} horizontal overflow ${info.overflowX}px`);
      if (info.err) findings.push(`${tag} error state visible`);
      if (info.missing.length) findings.push(`${tag} missing translations ${JSON.stringify(info.missing)}`);
      if (info.arabicInEn.length) findings.push(`${tag} Arabic text in English UI: ${JSON.stringify(info.arabicInEn)}`);
      if (info.clipped.length) findings.push(`${tag} clipped text ${JSON.stringify(info.clipped)}`);
      await p.screenshot({ path: `${OUT}/${c.name}__${r.role}${pg.replace(/[\/-]/g, '_').replace(/[0-9a-f]{8}-[0-9a-f-]{27}/, 'id') || '_home'}.png`, fullPage: true });
    }
    if (errs.length) findings.push(`[${c.name}/${r.role}] console errors: ${JSON.stringify([...new Set(errs)].slice(0, 3))}`);
    await ctx.close();
  }
  await browser.close();
  console.log(findings.length ? findings.join('\n') : 'NO FINDINGS'); console.log('shots in', OUT);
})();
