const { chromium } = require('playwright');
const http = require('http');

const API = 'http://127.0.0.1:8000/api/v1';
const WEB = 'http://localhost:5173';
const SECRET = 'test-ai-secret';
const OUT = process.env.SHOTS || '/tmp/claude-0/shots7';
require('fs').mkdirSync(OUT, { recursive: true });

const results = [];
const consoleErrors = [];
const step = async (name, fn) => {
  try { await fn(); results.push(['PASS', name]); console.log('PASS', name); }
  catch (e) { results.push(['FAIL', name, String(e.message).split('\n')[0]]); console.log('FAIL', name, '-', String(e.message).split('\n')[0]); }
};

const api = async (path, { method = 'GET', token, body, headers = {} } = {}) => {
  const r = await fetch(API + path, { method, headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }), ...headers }, body: body && JSON.stringify(body) });
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${text.slice(0, 200)}`);
  return data;
};
const login = async (identifier, password) => (await api('/auth/login', { method: 'POST', body: { identifier, password } })).access_token;

// Fake AI service: records the run the backend triggers. (The real AI team's service is not part of this repo.)
const runs = [];
const fakeAi = http.createServer((req, res) => {
  let b = ''; req.on('data', (c) => (b += c));
  req.on('end', () => { try { runs.push(JSON.parse(b)); } catch {} res.writeHead(202, { 'Content-Type': 'application/json' }); res.end('{"accepted":true}'); });
}).listen(9000);

const sfx = Math.random().toString(36).slice(2, 8);
const sup = { email: `e2e.sup.${sfx}@example.com`, password: 'SupPass1234' };
const tech = { email: `e2e.tech.${sfx}@example.com`, password: 'TechPass1234' };
const citizen = { name: 'مواطن اختبار رباعي كامل', phone: '010' + String(Date.now()).slice(-8), password: 'CitizenPass1' };
let ticketId, taskId;

async function newPage(browser, viewport = { width: 1280, height: 860 }) {
  const ctx = await browser.newContext({ viewport, locale: 'ar-EG' });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (/ERR_TUNNEL|ERR_NAME|Failed to load resource|tile\.openstreetmap|fonts\.g/.test(t)) return;
    consoleErrors.push('console: ' + t);
  });
  return page;
}
const uiLogin = async (page, identifier, password) => {
  await page.goto(WEB + '/login');
  await page.getByLabel('رقم الموبايل أو البريد').fill(identifier);
  await page.getByLabel('كلمة المرور').fill(password);
  await page.getByRole('button', { name: 'دخول' }).click();
};
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });

(async () => {
  const browser = await chromium.launch();
  const catName = 'Pothole / road damage', depName = 'Roads & Bridges Authority';

  await step('setup: admin creates supervisor, technician, team', async () => {
    const adminToken = await login('e2e.admin@example.com', 'AdminPass123');
    await api('/admin/staff', { method: 'POST', token: adminToken, body: { name: 'مشرف اختبار', email: sup.email, password: sup.password, role: 'supervisor' } });
    const t = await api('/admin/staff', { method: 'POST', token: adminToken, body: { name: 'فني اختبار', email: tech.email, password: tech.password, role: 'technician' } });
    const deps = await api('/admin/departments', { token: adminToken });
    const deptId = deps.find((d) => d.name === depName).id;
    const team = await api('/maintenance/teams', { method: 'POST', token: adminToken, body: { department_id: deptId, name: `فريق ${sfx}` } });
    await api(`/maintenance/teams/${team.id}/members`, { method: 'POST', token: adminToken, body: { user_id: t.id } });
  });

  // ---------------- Citizen ----------------
  const cp = await newPage(browser, { width: 390, height: 800 });
  await step('citizen: register via UI lands on /citizen', async () => {
    await cp.goto(WEB + '/register');
    // validation first: a short name and a missing national ID must be blocked, in Arabic
    await cp.getByLabel('الاسم الرباعي', { exact: false }).first().fill('أحمد محمد');
    await cp.getByLabel('رقم الموبايل').fill(citizen.phone);
    await cp.getByLabel('كلمة المرور').fill(citizen.password);
    await cp.getByRole('button', { name: 'إنشاء الحساب' }).click();
    await cp.getByText('اكتب الاسم رباعيًا', { exact: false }).waitFor({ timeout: 4000 });
    await cp.getByText('الرقم القومي مطلوب').waitFor({ timeout: 4000 });
    await cp.getByLabel('الاسم الرباعي', { exact: false }).first().fill(citizen.name);
    await cp.getByLabel('الرقم القومي').fill('2900101' + '01' + String(Math.floor(1000 + Math.random() * 8999)) + '7');
    await cp.getByRole('button', { name: 'إنشاء الحساب' }).click();
    await cp.waitForURL('**/citizen', { timeout: 10000 });
  });
  await step('citizen: empty state shown', async () => {
    await cp.getByText('لا توجد بلاغات حتى الآن').first().waitFor({ timeout: 8000 });
    await shot(cp, '01-citizen-dashboard-mobile');
  });
  await step('citizen: form validation blocks short description', async () => {
    await cp.goto(WEB + '/citizen/new');
    await cp.getByRole('button', { name: 'إرسال البلاغ' }).click();
    await cp.getByText('اكتب وصفًا لا يقل عن 10 أحرف').waitFor({ timeout: 4000 });
    await shot(cp, '02-report-form-validation-mobile');
  });
  await step('citizen: submit without a pin is blocked', async () => {
    await cp.getByLabel('وصف المشكلة', { exact: false }).fill('توجد حفرة كبيرة وعميقة في منتصف الشارع تعيق المرور وتسبب خطرًا.');
    await cp.getByRole('button', { name: 'إرسال البلاغ' }).click();
    await cp.getByText('حدّد موقع المشكلة على الخريطة').first().waitFor({ timeout: 4000 });
  });
  await step('citizen: create ticket (single-page form, upload gap shown, no AI step)', async () => {
    await cp.getByLabel('عنوان البلاغ', { exact: false }).fill('حفرة كبيرة في الطريق');
    await cp.getByText('رفع الملفات (رابط رفع مباشر)').waitFor({ timeout: 4000 });
    await cp.locator('.leaflet-container').click({ position: { x: 120, y: 120 } });
    await shot(cp, '03-report-form-filled-mobile');
    await cp.getByRole('button', { name: 'إرسال البلاغ' }).click();
    await cp.getByText('تم استلام بلاغك').waitFor({ timeout: 12000 });
    await shot(cp, '04-report-success-mobile');
    await cp.getByRole('link', { name: 'متابعة البلاغ' }).click();
    await cp.waitForURL(/\/citizen\/tickets\/[0-9a-f-]{36}/, { timeout: 12000 });
    ticketId = cp.url().split('/').pop();
    await cp.getByText('تم الإرسال').first().waitFor({ timeout: 6000 });
    await shot(cp, '04b-citizen-ticket-details-mobile');
  });
  await step('guard: citizen typing /admin is redirected to /citizen', async () => {
    await cp.goto(WEB + '/admin/users');
    await cp.waitForURL('**/citizen', { timeout: 6000 });
  });
  await step('guard: unauthenticated visitor is sent to /login', async () => {
    const anon = await newPage(browser);
    await anon.goto(WEB + '/supervisor');
    await anon.waitForURL('**/login', { timeout: 6000 });
    await anon.close();
  });

  // ---------------- Supervisor ----------------
  const sp = await newPage(browser);
  await step('supervisor: login lands on operations room', async () => {
    await uiLogin(sp, sup.email, sup.password);
    await sp.waitForURL('**/supervisor', { timeout: 10000 });
    await sp.waitForTimeout(900);
    await shot(sp, '05-supervisor-ops-dashboard');
  });
  await step('supervisor: opens ticket in two-pane incidents view', async () => {
    await sp.goto(WEB + `/supervisor/incidents/${ticketId}`);
    await sp.getByText('خطوة المراجعة الآلية').waitFor({ timeout: 8000 });
    await shot(sp, '06-supervisor-submitted');
  });
  await step('supervisor: triggers AI run (backend calls AI service)', async () => {
    await sp.getByRole('button', { name: 'تشغيل التحليل الآلي' }).click();
    await sp.getByRole('button', { name: 'تشغيل', exact: true }).click();
    await sp.getByText('الذكاء الاصطناعي يحلل البلاغ الآن').waitFor({ timeout: 8000 });
    for (let i = 0; i < 20 && !runs.length; i++) await new Promise((r) => setTimeout(r, 200));
    if (!runs.length) throw new Error('fake AI service never received the trigger');
  });
  await step('AI service callback delivers recommendation', async () => {
    const run = runs[0];
    await api('/ai/recommendations', {
      method: 'POST', headers: { 'X-AI-Service-Secret': SECRET },
      body: { run_id: run.run_id, ticket_id: ticketId, status: 'succeeded', model: { provider: 'fake', name: 'e2e-stub' },
        recommendation: { category: catName, severity: 'high', department: depName, confidence: 0.86, explanation: 'e2e callback', factors: [] }, evidence: [] },
    });
  });
  await step('supervisor: AI region + human decision region + endpoint gap notice', async () => {
    await sp.reload();
    await sp.getByText('توصية الذكاء الاصطناعي').first().waitFor({ timeout: 8000 });
    await sp.getByText('قرار المشرف').first().waitFor();
    await sp.getByText('GET /api/v1/ai/tickets').waitFor();
    await shot(sp, '07-supervisor-awaiting-approval');
  });
  await step('supervisor: reject confirm disabled until reason typed', async () => {
    await sp.getByRole('button', { name: 'رفض', exact: true }).click();
    const confirm = sp.getByRole('button', { name: 'تأكيد الرفض' });
    if (!(await confirm.isDisabled())) throw new Error('reject confirm should be disabled without reason');
    await sp.keyboard.press('Escape');
  });
  await step('supervisor: approve -> assign panel appears', async () => {
    await sp.getByRole('button', { name: 'اعتماد التوصية' }).click();
    await sp.getByRole('button', { name: 'اعتماد', exact: true }).click();
    await sp.getByText('إسناد إلى فريق صيانة').waitFor({ timeout: 8000 });
  });
  await step('supervisor: assigns task to team', async () => {
    await sp.getByLabel('الفريق').selectOption({ label: `فريق ${sfx}` });
    await sp.getByRole('button', { name: 'إسناد المهمة' }).click();
    await sp.getByText('مهمة الصيانة').first().waitFor({ timeout: 8000 });
  });
  await step('supervisor: tasks-by-ticket gap shown, not faked', async () => {
    await sp.getByText('GET /api/v1/maintenance/tickets').waitFor({ timeout: 6000 });
    await shot(sp, '08-supervisor-task-gap');
  });

  // ---------------- Technician ----------------
  const tp = await newPage(browser, { width: 390, height: 800 });
  await step('technician: sees own team task and starts it', async () => {
    await uiLogin(tp, tech.email, tech.password);
    await tp.waitForURL('**/technician', { timeout: 10000 });
    await tp.goto(WEB + '/technician/tasks');
    await tp.getByText('حفرة كبيرة في الطريق').first().waitFor({ timeout: 8000 });
    await shot(tp, '09-technician-tasks-mobile');
    await tp.getByText('حفرة كبيرة في الطريق').first().click();
    await tp.waitForURL(/\/technician\/tasks\/[0-9a-f-]{36}/);
    taskId = tp.url().split('/').pop();
    await tp.getByRole('button', { name: 'بدء التنفيذ' }).click();
    await tp.getByRole('button', { name: /تم التنفيذ/ }).waitFor({ timeout: 8000 });
  });
  await step('technician: evidence upload gap shown honestly', async () => {
    await tp.getByText('رفع الملفات (رابط رفع مباشر)').waitFor();
  });
  await step('technician: sends task for verification', async () => {
    await tp.getByRole('button', { name: /تم التنفيذ/ }).click();
    await tp.getByText('تم إرسال المهمة للتحقق').first().waitFor({ timeout: 8000 });
    await shot(tp, '10-technician-task-details-mobile');
  });
  await step('guard: technician cannot open supervisor UI', async () => {
    await tp.goto(WEB + '/supervisor/incidents');
    await tp.waitForURL('**/technician', { timeout: 6000 });
  });
  let supToken2;
  await step('rework: failed verification shows result card to technician (Arabic)', async () => {
    supToken2 = await login(sup.email, sup.password);
    await api(`/verification/tasks/${taskId}`, { method: 'POST', token: supToken2, body: { result: 'fail', note: 'الأعمال غير مكتملة' } });
    await tp.goto(WEB + `/technician/tasks/${taskId}`);
    await tp.getByText('نتيجة التحقق').waitFor({ timeout: 8000 });
    await tp.getByText('لم ينجح التحقق (الأعمال غير مكتملة)', { exact: false }).waitFor({ timeout: 4000 });
    await shot(tp, '10b-technician-verification-failed-mobile');
  });
  await step('rework: re-assign creates attempt 2 with rework banner', async () => {
    const teams = await api('/maintenance/teams', { token: supToken2 });
    const team = teams.find((x) => x.name === `فريق ${sfx}`);
    const t2 = await api(`/maintenance/tickets/${ticketId}/tasks`, { method: 'POST', token: supToken2, body: { team_id: team.id, notes: 'أعد الأعمال' } });
    taskId = t2.id;
    await tp.goto(WEB + `/technician/tasks/${taskId}`);
    await tp.getByText('هذه مهمة إعادة عمل (المحاولة 2)', { exact: false }).waitFor({ timeout: 8000 });
    await tp.getByText('الخطوة التالية: توجّه إلى الموقع', { exact: false }).waitFor();
    await shot(tp, '10c-technician-rework-mobile');
  });
  await step('rework: technician completes attempt 2 (banner stays while in progress)', async () => {
    await tp.getByRole('button', { name: 'بدء التنفيذ' }).click();
    await tp.getByRole('button', { name: /تم التنفيذ/ }).waitFor({ timeout: 8000 });
    await tp.getByText('هذه مهمة إعادة عمل', { exact: false }).waitFor();
    await tp.getByRole('button', { name: /تم التنفيذ/ }).click();
    await tp.getByText('تم إرسال المهمة للتحقق').first().waitFor({ timeout: 8000 });
  });
  await step('verification via API (UI needs the missing endpoint) completes ticket', async () => {
    await api(`/verification/tasks/${taskId}`, { method: 'POST', token: supToken2, body: { result: 'pass', note: 'e2e' } });
  });
  await step('citizen sees ticket completed + notifications page works', async () => {
    await cp.goto(WEB + `/citizen/tickets/${ticketId}`);
    await cp.getByText('مكتمل').first().waitFor({ timeout: 8000 });
    await cp.goto(WEB + '/citizen/notifications');
    await cp.waitForTimeout(800);
    await shot(cp, '11-citizen-notifications-mobile');
  });

  // ---------------- Admin ----------------
  const ap = await newPage(browser);
  await step('admin: login + dashboard', async () => {
    await uiLogin(ap, 'e2e.admin@example.com', 'AdminPass123');
    await ap.waitForURL('**/admin', { timeout: 10000 });
    await ap.waitForTimeout(900);
    await shot(ap, '12-admin-dashboard');
  });
  for (const [path, text, file] of [['users', 'المستخدمون', '13-admin-users'], ['departments', 'الجهات', '14-admin-departments'], ['categories', 'التصنيفات', '15-admin-categories'], ['teams', 'فرق الصيانة', '16-admin-teams'], ['audit-logs', 'سجل التدقيق', '17-admin-audit']]) {
    await step(`admin: /${path} loads without error state`, async () => {
      await ap.goto(WEB + '/admin/' + path);
      await ap.getByRole('heading', { name: text }).waitFor({ timeout: 8000 });
      await ap.waitForTimeout(700);
      if (await ap.getByText('حدث خطأ').count()) throw new Error('error state visible');
      await shot(ap, file);
    });
  }
  await step('admin: create department via UI', async () => {
    await ap.goto(WEB + '/admin/departments');
    await ap.getByRole('button', { name: 'إضافة جهة' }).click();
    await ap.getByLabel('اسم الجهة').fill(`جهة اختبار ${sfx}`);
    await ap.getByRole('button', { name: 'حفظ' }).click();
    await ap.getByText(`جهة اختبار ${sfx}`).waitFor({ timeout: 8000 });
  });
  await step('admin: team members shows endpoint-required notice', async () => {
    await ap.goto(WEB + '/admin/teams');
    await ap.getByRole('button', { name: 'الأعضاء' }).first().click();
    await ap.getByText('GET /api/v1/maintenance/teams').waitFor({ timeout: 6000 });
  });
  await step('guard: admin cannot open technician UI', async () => {
    await ap.goto(WEB + '/technician');
    await ap.waitForURL('**/admin', { timeout: 6000 });
  });

  await browser.close();
  fakeAi.close();
  console.log('\n=== SUMMARY ===');
  const fails = results.filter((r) => r[0] === 'FAIL');
  console.log(`${results.length - fails.length}/${results.length} passed`);
  fails.forEach((f) => console.log('FAIL:', f[1], '-', f[2]));
  console.log('console/page errors:', consoleErrors.length ? JSON.stringify([...new Set(consoleErrors)].slice(0, 10), null, 1) : 'none');
  process.exit(0);
})();
