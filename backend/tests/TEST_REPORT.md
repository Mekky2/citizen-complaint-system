# تقرير الاختبارات والتحقق — نظام إدارة شكاوى المواطنين

**التاريخ:** 2026-11-18  
**الفرع المحلي:** `feature/complaint-and-rag-agents`  
**النطاق:** الـ backend، وكيل الشكاوى، وكيل RAG، قاعدة المعرفة، الـ API، وقالب الواجهة الأمامية.  
**ملاحظة:** كل النتائج أدناه ناتجة عن تشغيل فعلي. لا شيء «مفترض» أو «متوقع» بدون تشغيل.

---

## 1. الملخص التنفيذي

| البند | النتيجة |
|---|---|
| اختبارات backend الكاملة | **225 ناجح، 4 متخطّى، 0 فاشل** |
| تكرار التشغيل الكامل | **نفس النتيجة مرتين** (لا اختبارات متذبذبة) |
| `ruff check .` | **All checks passed** |
| مقاييس RAG | **hit@1 88.9%، hit@3 100%، recall@5 100%، MRR 0.944** |
| واجهة Vite | `npm install` نجح، lint نجح، build نجح |
| CORS | Preflight من `localhost:5173` و`127.0.0.1:5173` = 200، وأصل غير مسموح = 400 |
| اختبار المتصفح | **لم يُنفّذ**: الواجهة قالب Vite فقط بلا صفحات أو API client |
| الحالة العامة | الوظائف الأساسية تعمل Offline؛ توجد قيود موثّقة أدناه |

---

## 2. بيئة التشغيل

| المكوّن | الإصدار |
|---|---|
| Python | 3.14.10 |
| pytest | 9.2.0 |
| ruff | 0.17.5 |
| FastAPI | 0.165.0 |
| httpx | 0.28.1 |
| Node.js | v26.11.1 |
| npm | 12.2.2 |
| Vite | 8.3.4 |

---

## 3. الاختبارات الآلية للـ backend

### 3.1 التشغيل الكامل (مرتين)

```bash
cd backend
.venv/bin/python -m pytest -q
```

```text
=== RUN 1 ===
225 passed, 4 skipped, 17 warnings in 7.86s
=== RUN 2 ===
225 passed, 4 skipped, 17 warnings in 10.25s
```

### 3.2 تشغيل المجموعات منفصلة

```text
=== complaint_agent ===
166 passed, 1 skipped, 17 warnings in 2.31s

=== rag_agent ===
10 passed, 17 warnings in 0.11s

=== retrieval_golden ===
RAG golden metrics: hit@1=32/36 (88.9%) hit@3=36/36 (100.0%)
recall@5=100.0% MRR=0.944
3 passed, 17 warnings in 2.36s

=== integration ===
15 passed, 3 skipped, 17 warnings in 6.79s
```

### 3.3 فحص الأسلوب

```bash
cd backend
.venv/bin/ruff check .
```

```text
All checks passed!
```

### 3.4 الاختبارات المتخطّاة

```text
SKIPPED [1] tests/integration/test_nim_live.py:29: LLM_API_KEY is not configured
SKIPPED [1] tests/integration/test_nim_live.py:33: LLM_API_KEY is not configured
SKIPPED [1] tests/integration/test_nim_live.py:38: LLM_API_KEY is not configured
SKIPPED [1] tests/unit/complaint_agent/test_conversation.py:52:
            Franco-Arabic needs the LLM extractor; covered by test_franco_with_fake_llm
```

---

## 4. مقاييس RAG

على 15 مستندًا و136 مقطعًا و36 سؤالًا عربيًا، باستخدام مُضمِّن `hashing` الحتمي:

```text
hit@1=32/36=88.9%
hit@3=36/36=100.0%
recall@5=100.0%
MRR=0.944
```

هذه أرقام خط أساس Offline وليست جودة نموذج دلالي إنتاجي. عند تشغيل `openai_compatible` يجب إعادة القياس.

---

## 5. اختبار الـ API الحقيقي (سيرفر فعلي + curl)

تعذّر تشغيل السيرفر على المنفذ 8000 في هذه البيئة (المنفذ غير متاح للمستخدم)، فتم التشغيل على المنفذ **8010**:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

معظم الطلبات نُفّذت بـ `curl` مع `Content-Type: application/json` و`Origin: http://127.0.0.1:5173`.

| # | الاختبار | المتوقع | الفعلي | النتيجة |
|---|---|---|---|---|
| a | `GET /api/v1/knowledge/status` | 15 مستندًا | `documents=15, chunks=136` | PASS |
| b | سؤال عربي في النطاق | إجابة عربية + مصدر | إجابة عربية + `sources[0].title` + «المصدر:» | PASS |
| c | سؤال خارج النطاق | `found_in_kb=false` + «المعلومات غير متوفرة» | `NO_LEXICAL_SUPPORT` + الرسالة المطلوبة | PASS |
| d | شكوى → متابعة → تأكيد | لا تذكرة قبل التأكيد، ثم `Pending` | `awaiting_confirmation` ثم `TKT-2026-0001` بحالة `Pending` | PASS |
| d2 | دورة حياة التذكرة | `Pending → Approved → In Progress → Verifying → Done` | كل انتقال أعاد 200 والحالة الصحيحة | PASS |
| e | تحية | رد عربي، بلا تذكرة | `handoff_to=complaint`، عدد التذاكر لم يزد | PASS |
| f | طوارئ (سلك كهرباء مكشوف) | رسالة طوارئ وأرقام رسمية فقط | `EMERGENCY_DETECTED` + كل الأرقام من JSON | PASS بعد الإصلاح |
| g | رسالة مسيئة | رفض عربي مهذب، بلا تذكرة | `ABUSIVE_LANGUAGE` + رد مهذب | PASS |
| h | حقن أوامر | تجاهل دون تنفيذ | `PROMPT_INJECTION_IGNORED` | PASS |
| i | شكوى مكررة بجلسة جديدة | اقتراح ربط، بلا تذكرة ثانية | ذكر `TKT-2026-0001` ونسبة تشابه 100% | PASS |
| j1 | رسالة فارغة | 422 نظيف | `string_too_short` | PASS |
| j2 | رسالة 5000 حرف | 422 نظيف بلا صدى للنص | `string_too_long`، لا يُعاد النص | PASS بعد الإصلاح |
| j3 | JSON غير صالح | 422 نظيف | `json_invalid` | PASS |
| j4 | حقول ناقصة | 422 نظيف | `missing` على `message` | PASS |
| j5 | معرّف تذكرة غير موجود | 404 نظيف | `{"detail":"Ticket not found"}` | PASS |
| j6 | إنجليزي فقط | رد عربي نظيف | `found_in_kb=false` + رسالة عربية | PASS (لا إجابة من KB) |
| j7 | Franco-Arabic | تعامل بلا انهيار | سؤال متابعة عربي | PASS (يحتاج LLM للاستخراج الكامل) |
| j8 | أرقام عربية-هندية | تعامل سليم | ملخص عربي صحيح | PASS |
| j9 | عربي/إنجليزي مختلط | استخراج الفئة والموقع | `Water` + `street=النيل` + تأكيد | PASS بعد الإصلاح |
| k | PII في السجل | لا رقم هوية/هاتف صريح | `[PHONE]` و`[ID]` في الرد، ولا شيء في log | PASS |

### 5.1 أمثلة استجابات حقيقية

سؤال في النطاق:

```json
{
  "type": "rag",
  "found_in_kb": true,
  "reply_ar": "بحسب المعلومات المتاحة في قاعدة المعرفة عن «كيفية تقديم شكوى»: ... المصدر: كيفية تقديم شكوى",
  "sources": [{"title": "كيفية تقديم شكوى", "excerpt": "...", "page": null}]
}
```

شكوى مؤكدة:

```json
{
  "stage": "submitted",
  "ticket": {
    "ticket_id": "TKT-2026-0001",
    "category": "Water",
    "authority": "مديرية المياه",
    "status": "Pending"
  }
}
```

انتقال غير مسموح:

```json
HTTP 409
{"detail": "انتقال حالة غير مسموح به: cannot move ticket from 'Pending' to 'Done'"}
```

---

## 6. CORS والواجهة الأمامية

### 6.1 CORS

```text
OPTIONS /api/v1/chat  Origin: http://127.0.0.1:5173   -> 200 OK
access-control-allow-origin: http://127.0.0.1:5173

OPTIONS /api/v1/chat  Origin: http://localhost:5173   -> 200 OK
access-control-allow-origin: http://localhost:5173

OPTIONS /api/v1/chat  Origin: http://evil.example    -> 400 Bad Request

POST /api/v1/chat     Origin: http://127.0.0.1:5173   -> 200 OK
access-control-allow-origin: http://127.0.0.1:5173
```

الأصول قابلة للضبط عبر `CORS_ORIGINS` (مفصولة بفواصل)، والافتراضي هو أصلا Vite.

### 6.2 تشغيل الواجهة

```bash
cd frontend
npm install
npm run lint
npm run build
```

```text
npm install: added 30 packages, found 0 vulnerabilities
package-lock.json: unchanged
npm run lint: oxlint (لا أخطاء)
npm run build: tsc -b && vite build
  ✓ 20 modules transformed
  ✓ built in 1.69s
```

لا يوجد script باسم `test` أو `type-check` في `package.json`؛ الـ `build` يشغّل `tsc -b`.

### 6.3 اختبار المتصفح

**لم يُنفّذ** لأن `frontend/src/App.tsx` هو قالب Vite الافتراضي فقط: لا توجد صفحة مواطن، ولا Dashboard، ولا API client، ولا `VITE_*` URL. تشغيل Playwright سيفتح صفحة «Get started» ولا يمكنه إرسال شكوى. بدلًا من ذلك تم اختبار كل endpoint حقيقي بـ curl بنفس شكل الطلب الذي سيستخدمه أي frontend لاحقًا.

---

## 7. الأخطاء التي وُجدت وأُصلحت

| # | الملف | المشكلة | الإصلاح |
|---|---|---|---|
| 1 | `backend/app/main.py` | لا يوجد CORS middleware | إضافة `CORSMiddleware` وربطه بـ `CORS_ORIGINS` |
| 2 | `backend/app/services/ticket_store.py` | الحالة `pending_review` تخالف الوثائق | الحالات السبعة الرسمية + آلة انتقالات |
| 3 | `backend/app/api/routes.py` | يقبل `approved/rejected/in_progress` | `Pending/Approved/In Progress/Verifying/Done/Declined/Dismissed` + 409 للانتقال غير المسموح |
| 4 | `backend/app/agents/complaint_agent/conversation.py` | «سلك كهرباء مكشوف» لا يُعتبر طوارئ | إضافة صيغ المفرد والكابل والماس الكهربائي |
| 5 | `backend/app/agents/complaint_agent/authorities.py` | النص المختلط عربي/إنجليزي لا يُستخرج منه Category/Street | كلمات إنجليزية للفئات و`street/road` للموقع |
| 6 | `backend/app/main.py` | 422 يعيد نص الرسالة كاملًا (قد يحتوي PII) | معالج `RequestValidationError` يحذف `input` و`ctx` |
| 7 | `backend/.env.example` | نسخه إلى `.env` يفشل لأن متغيرات int/float فارغة | تحويل الأسماء إلى تعليقات مع توضيح القيم الافتراضية |
| 8 | `app/agents/rag_agent/interfaces.py` | `Any` غير مستورد | إضافة `Any` |
| 9 | ملفات prompts والـ RAG | أخطاء `ruff` (E501/F401) | ضبط الاستيرادات و`# ruff: noqa: E501` للنصوص الطويلة |

### أخطاء/فجوات في ملفات الفريق الآخر (لم أعدّلها)

| الملف | السطر | المشكلة | الاقتراح |
|---|---|---|---|
| `frontend/src/App.tsx` | 1-120 | قالب Vite فقط، لا Portal ولا Dashboard ولا API client | بناء الصفحات وربطها بعقد الـ API أدناه |
| `frontend/package.json` | 6-10 | لا يوجد script `test` أو `type-check` | إضافة `test` و`type-check` عند إضافة الاختبارات |
| `docs/system_architecture.md` | статус model | كان يخالف أسماء الـ API القديمة | **تم التوافق الآن** في الـ backend؛ الوثائق تحتاج فقط تأكيد أن الـ API يطبّقها |
| `backend/app/agents/orchestrator/*` | — | لا يوجد endpoint لتقديم شكوى منظم (authority/form) | إضافة endpoint لاحقًا إن كان مطلوبًا في Phase 2 |

---

## 8. فحص الأمان والجودة

### 8.1 البحث عن أسرار

- لا توجد مفاتيح حقيقية في الملفات المتتبعة.
- النمط `nvapi-...` ظهر فقط في `backend/tests/unit/complaint_agent/test_nim_client.py` كقيمة اختبار وهمية (`SECRET`)، وليس مفتاحًا فعليًا.
- `.env` و`.venv` و`node_modules` **غير متتبعة** في git.
- لا توجد مجلدات باسم `Kayla`.

### 8.2 git status

```text
 M backend/.env.example
 M backend/app/core/config.py
 M backend/app/knowledge_base/__init__.py
 M backend/app/main.py
?? ... (ملفات الوكلاء والخدمات والاختبارات الجديدة)
```

الملفات الموجودة سابقًا والمعدّلة هي 4 فقط، وكلها إضافات wiring صغيرة (CORS، إعدادات، ربط router، تصدير الحزمة). لا تعديل على ملفات الفريق الآخر.

### 8.3 أرقام الطوارئ

`backend/data/emergency_numbers.json` يحتوي: 122 شرطة، 123 إسعاف، 180 حماية مدنية، 129 غاز، 121 كهرباء، 125 مياه، 16528 شكاوى حكومية.  
**يجب التحقق من هذه الأرقام مقابل المصادر الحكومية المصرية الرسمية قبل العرض النهائي.** الاختبارات تتحقق فقط من أن الوكيل لا يخترع أرقامًا خارج هذا الملف.

### 8.4 مراجعة المحتوى العربي

كل المستندات الـ15 تحمل `source_type: "sample"`، ومعظمها ينتهي بعبارة «هذا المحتوى للأغراض التوضيحية». النقاط التي تحتاج تأكيدًا رسميًا:

1. `04-الزمن-المتوقع-للاستجابة.md`: مدد محددة (24-48 ساعة، 3-5 أيام، 10-15 يومًا، 20-30 يومًا) — توضيحية لكنها تبدو كالتزام رسمي.
2. `13-كيفية-المتابعة.md`: تكرر 24-48 ساعة / 3-5 أيام / 10-15 يومًا.
3. `01-كيفية-تقديم-شكوى.md`: تطلب «الاسم» و«رقم الهوية الوطنية» كبيانات إلزامية، بينما وكيل المحادثة الحالي لا يجمعهما عمدًا.
4. `14-كيفية-إرفاق-الصور.md`: تذكر الاتصال بـ16528 لإرفاق الصور، وهي صياغة غير واضحة ويجب مراجعتها.
5. أرقام الطوارئ متسقة مع JSON لكنها تحتاج تحققًا رسميًا.

---

## 9. عقد الـ API لفريق الواجهة الأمامية

### 9.1 عام

- Base URL محلي: `http://127.0.0.1:8010` (أو 8000 عند توفره).
- كل الطلبات `Content-Type: application/json`.
- لا يوجد auth حاليًا. عند إضافته سيكون `Authorization: Bearer <token>`.
- CORS يسمح بأصلي Vite افتراضيًا.
- كل النصوص للمواطن عربية.

### 9.2 `POST /api/v1/chat`

الطلب:

```json
{
  "message": "ماسورة مياه مكسورة في شارع النيل",
  "session_id": "citizen-session-1",
  "user_id": null
}
```

الحقول: `message` مطلوب (1-4000 حرف)، `session_id` مطلوب (افتراضي `demo-session`)، `user_id` اختياري.

الاستجابة (شكوى):

```json
{
  "type": "complaint",
  "session_id": "citizen-session-1",
  "reply_ar": "ملخص الشكوى: ... هل تأكد إرسال الشكوى؟",
  "stage": "awaiting_confirmation",
  "ticket": null,
  "missing_fields": [],
  "requires_confirmation": true,
  "handoff_to": null,
  "sources": [],
  "confidence": null,
  "found_in_kb": null,
  "review_notes": []
}
```

الاستجابة (سؤال/RAG):

```json
{
  "type": "rag",
  "reply_ar": "... المصدر: كيفية تقديم شكوى",
  "sources": [{"title": "كيفية تقديم شكوى", "excerpt": "...", "page": null}],
  "found_in_kb": true,
  "confidence": "low"
}
```

مراحل المحادثة `stage`: `collecting` → `awaiting_confirmation` → `submitted` (أو `linked`)، مع `handoff` للتحويل إلى RAG.

مثال تأكيد:

```json
{"message": "نعم أكد الإرسال", "session_id": "citizen-session-1"}
```

### 9.3 `GET /api/v1/tickets`

يعيد مصفوفة تذاكر. كل تذكرة:

```json
{
  "ticket_id": "TKT-2026-0001",
  "title": "ماسورة مياه مكسورة",
  "description": "...",
  "category": "Water",
  "authority": "مديرية المياه",
  "location": {"governorate": "الجيزة", "city": "", "street": "النيل", "landmark": ""},
  "urgency": "high",
  "urgency_reason": "...",
  "incident_date": null,
  "attachments_mentioned": [],
  "contact_preference": null,
  "status": "Pending",
  "created_at": "...",
  "updated_at": "...",
  "linked_to": null
}
```

`review_notes` لا تُعاد للعميل (داخلية).

### 9.4 `GET /api/v1/tickets/{ticket_id}`

- 200: نفس شكل التذكرة.
- 404: `{"detail": "Ticket not found"}`.

### 9.5 `POST /api/v1/tickets/{ticket_id}/review`

الطلب:

```json
{"status": "Approved", "reviewer_note": "تم التحقق من الموقع"}
```

`reviewer_note` اختياري (≤500 حرف).

القيم المسموحة: `Declined`, `Pending`, `Approved`, `Dismissed`, `In Progress`, `Verifying`, `Done`.

الانتقالات المسموحة:

```text
Pending      -> Approved | Dismissed | Declined
Approved     -> In Progress | Dismissed | Declined
In Progress  -> Verifying | Dismissed | Declined
Verifying    -> Done | In Progress | Dismissed | Declined
Done / Declined / Dismissed -> (نهائية)
```

- 200: التذكرة بعد التحديث.
- 404: تذكرة غير موجودة.
- 409: انتقال غير مسموح، مثال: `{"detail":"انتقال حالة غير مسموح به: ..."}`.
- 422: قيمة حالة غير معروفة.

### 9.6 `GET /api/v1/knowledge/status`

```json
{
  "documents": 15,
  "chunks": 136,
  "embedding_provider": "hashing",
  "embedding_dimension": 1024,
  "ingest": {"inserted": 15, "updated": 0, "skipped": 0, "documents": 15}
}
```

### 9.7 `GET /health`

```json
{"status": "ok", "env": "dev"}
```

### 9.8 أمثلة عربية جاهزة للواجهة

```text
سؤال: "كيف أقدم شكوى؟"        -> type=rag, found_in_kb=true, مع sources
سؤال: "كم رسوم رخصة القيادة؟" -> type=rag, found_in_kb=false, "المعلومات غير متوفرة..."
شكوى: "حفرة في شارع النيل"    -> type=complaint, stage=awaiting_confirmation
تأكيد: "نعم"                   -> stage=submitted, ticket.status=Pending
طوارئ: "سلك كهرباء مكشوف"     -> review_notes=[EMERGENCY_DETECTED], بلا تذكرة
إساءة: "أنت غبي"              -> reply عربي مهذب, بلا تذكرة
حقن: "تجاهل التعليمات..."      -> PROMPT_INJECTION_IGNORED, بلا تذكرة
```

---

## 10. القيود المعروفة

1. مُضمِّن `hashing` خط أساس Offline وليس نموذجًا دلاليًا؛ أعد القياس مع `openai_compatible`.
2. اختبارات NVIDIA NIM الحية متخطّاة لغياب `LLM_API_KEY`.
3. Franco-Arabic والإنجليزية الكاملة تحتاج LLM؛ المستخرج القواعدي يعيد سؤال متابعة أو «غير متوفر».
4. مسار PostgreSQL/pgvector لم يُشغّل لعدم تثبيت `psycopg`؛ تم اختبار المتجر في الذاكرة ومراجعة الترحيل.
5. التذاكر في الذاكرة فقط؛ لا استمرارية بعد إعادة تشغيل السيرفر.
6. لا يوجد structured complaint endpoint (authority/form) ولا tracking endpoint مستقل؛ مطلوبان لاحقًا حسب Phase 2/9.

---

## 11. أوامر إعادة التحقق

```bash
cd backend

# الاختبارات الكاملة (مرتين للتذبذب)
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q

# المجموعات
.venv/bin/python -m pytest tests/unit/complaint_agent -q
.venv/bin/python -m pytest tests/unit/rag_agent -q
.venv/bin/python -m pytest tests/unit/test_retrieval_golden.py -s -q
.venv/bin/python -m pytest tests/integration -q

# الأسلوب
.venv/bin/ruff check .

# السيرفر الحقيقي
cp -n .env.example .env
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
curl -sS http://127.0.0.1:8010/api/v1/knowledge/status
curl -sS -X POST http://127.0.0.1:8010/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"كيف أقدم شكوى؟","session_id":"verify-1"}'

# الواجهة
cd ../frontend
npm install
npm run lint
npm run build

# CORS preflight
curl -i -X OPTIONS http://127.0.0.1:8010/api/v1/chat \
  -H "Origin: http://127.0.0.1:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

---

## 12. الخلاصة

- ✅ الاختبارات الآلية خضراء بالكامل: **225 passed / 4 skipped / 0 failed** مرتين.
- ✅ `ruff` نظيف.
- ✅ RAG: hit@3 = 100% وrecall@5 = 100% على المجموعة الذهبية.
- ✅ الـ API يعمل فعليًا: شكوى، تأكيد، دورة حياة كاملة، RAG، طوارئ، تكرار، أخطاء 4xx نظيفة.
- ✅ CORS يعمل مع أصلَي Vite ويرفض غير المسموح.
- ✅ قالب الواجهة يبني بنجاح lint/build دون تعديل ملفاته.
- ⚠️ الواجهة نفسها غير مبنية بعد (قالب Vite فقط)، واختبار المتصفح غير ممكن.
- ⚠️ أرقام الطوارئ ومدد الاستجابة تحتاج تحققًا رسميًا قبل العرض.
- ⚠️ LLM الحقيقي وpgvector وTicketService الدائم لم تُختبر بعد.
