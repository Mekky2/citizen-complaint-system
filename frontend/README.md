# EG Civic Operations — Frontend

React 18 + Vite + Tailwind + React Router + Axios + Lucide + Leaflet (react-leaflet **4**, not 5 — stays on React 18).
Arabic RTL-first, Cairo font. Dark government look ported from the original Citizen Portal prototype and shared by all four roles.

## Run

```bash
npm install
cp .env.example .env      # VITE_API_URL=http://127.0.0.1:8000/api/v1
npm run dev               # http://localhost:5173
npm run build             # production build -> dist/
```

The backend's `CORS_ORIGINS` must include the dev origin (default `http://localhost:5173`).
Dev-only component specimens: `/dev/design-system` (not routed in production builds).

## Design language (from the prototype)

slate-900 canvas · `rounded-2xl bg-slate-800/80 border-slate-700` cards with a blue icon header · blue-600 primary ·
tinted status/severity pills · sticky blurred header with the logo box and pill-segmented nav (desktop) / bottom tab bar (mobile) ·
labelled icon fields · vertical coloured status timeline · before/after slider · voice recorder with ping ring + equaliser ·
dashed dropzone with camera · success screen with copyable ticket number. Tokens live in `tailwind.config.js` / `src/index.css`,
status colours/hints in `src/utils/status.js`.
## Light / dark theme and Arabic / English

- Theme: the slate scale is a set of CSS variables (`src/index.css`) that the light theme inverts, so every component works in both
  modes. Toggle in the header (and on the auth screens); saved in `localStorage` (`egc.theme`) and applied before first paint (`index.html`).
- Language: Arabic is the source language and the Arabic text is the key — `tr('نص')` from `src/i18n`, English in `src/i18n/en.js`.
  Switching reloads the page (so module-level label maps are always in the right language), sets `lang`/`dir` on `<html>`, flips
  directional icons (`ltr:rotate-180`) and uses locale-aware dates. Data that comes from the backend (category names, history notes) is shown as stored.
  Adding text: wrap it in `tr()` and add the English line to `en.js`; in dev, missing keys are collected in `window.__missingI18n`.

## Location picker (precise pin)

Rendering is Leaflet 1.9 via react-leaflet 4 (OpenStreetMap street tiles + Esri satellite imagery, zoom to 19). Address lookup/search uses
OpenStreetMap Nominatim (Egypt only). `LocationPicker` gives: a refined GPS fix (`watchPosition`, high accuracy, keeps only equal-or-better readings,
stops at ±15 m or after 25 s) with an accuracy circle and Excellent/Good/Poor chip; draggable pin and tap-to-place; address search;
exact coordinates input (6 decimals); street/satellite switch; warning when the pin is outside Egypt. GPS accuracy itself depends on the device
(indoors it can be 50 m+ — the UI says so and points to satellite view). The backend stores lat/lng only, not the accuracy.

## Roles and routes

| Role | Base route | Pages |
| --- | --- | --- |
| Citizen | `/citizen` | Dashboard, New report (single-page form -> success screen with ticket number), My tickets, Ticket details (vertical timeline), Notifications, Profile |
| Supervisor | `/supervisor` | Operations room (KPIs + live map + priority queue), Incidents (list + workspace: AI card, decision, assign, verify + before/after), Notifications |
| Technician | `/technician` | Dashboard, My tasks, Task details (status + evidence), Notifications |
| Admin | `/admin` | Dashboard, Users (+ create staff), Departments, Categories, Maintenance teams, Audit logs |

`ProtectedRoute` checks authentication **and** role; typing another role's URL redirects to your own home.
JWT + refresh token live in `AuthContext` / `utils/tokenStore.js`; `api/client.js` attaches the token and does one shared refresh on 401.

## Structure

```
src/api/         one module per backend resource + client.js (axios, refresh)
src/components/  common/ (design system) · ai/ · maintenance/ · tickets/ · layout/
src/layouts/     Citizen / Supervisor / Technician / Admin
src/pages/       auth/ citizen/ supervisor/ technician/ admin/ shared/ dev/
src/context/     AuthContext.jsx
src/hooks/       useFetch.js  (the loading / error / data contract)
src/utils/       status.js (enum -> Arabic label + tone) · validators.js · format.js · errors.js
e2e/             phase7-flow.cjs (Arabic role flows) + i18n-map-flow.cjs (English/light + map logic) — Playwright against a live backend
```

Every API-driven view renders Loading → Error (with retry) → Empty → content, in Arabic.

## Rules this build follows

No mock data, no simulated AI, no invented endpoints. Where the backend has no endpoint for something,
the UI says so with a `Backend endpoint required: …` notice (`components/common/EndpointRequired.jsx`)
and the rest of the screen keeps working.

The AI never appears to decide: the recommendation card has a read-only "AI suggestion" region and a
visually separate "Supervisor decision" region; nothing moves past `awaiting_approval` without a supervisor action.
Citizens never see AI analysis; there is no AI step in the complaint wizard (the backend only lets
supervisors/admins trigger it).

## Backend endpoints required (not invented — flagged)

| # | Endpoint | Blocks |
| --- | --- | --- |
| 1 | `GET /api/v1/ai/tickets/{ticket_id}/recommendation` (`AiRecommendationOut` incl. evidence) | Showing the AI recommendation, legal evidence and similar cases to the supervisor. Approve/edit/reject still work. |
| 2 | `GET /api/v1/maintenance/tickets/{ticket_id}/tasks` | Supervisor seeing the task, its evidence, and verifying pass/fail from the UI (needs the task id). |
| 3 | `GET /api/v1/maintenance/teams/{team_id}/members` | Admin viewing a team's roster. Adding members works. |
| 4 | File upload or pre-signed upload URL | Attaching photos/video/voice to complaints and task evidence. The backend stores URLs only. Set `VITE_UPLOADS_ENABLED=true` and implement `uploadFile()` in `src/api/storage.js` once it exists. |
| 5 | `PATCH /api/v1/users/me` (optional) | Citizen profile editing. Profile is read-only today. |
| 6 | `deactivated` field on `UserOut` (optional) | Showing account state in Admin → Users. Disable/enable actions work; state isn't shown. |

Items 1–3 are small additive reads over logic the backend already has; the frontend already calls them and
lights up automatically when they exist (no frontend change needed).

## Corrections to the design proposal

- First ticket status is `submitted` (not `new`).
- `GET /ai/similar-cases` and `POST /ai/legal-search` are **AI-service-only** (shared secret), so the frontend never calls them.
  Similar cases and legal evidence reach the UI only inside the recommendation's `evidence[]` (gap #1).
- Task evidence stages are `progress | after` (no "before").

## Tested

`e2e/phase7-flow.cjs` drives the real UI against the real backend and database (32 checks) and `e2e/i18n-map-flow.cjs` (12 checks: English/LTR/light, map search/GPS/coordinates, no missing translations) — all passing:
citizen register → single-page report form → ticket; role guards; supervisor AI trigger → (AI-service callback) → approve → assign;
technician start → send for verification; citizen sees completion; every admin page; create department.
Run it with the backend (port 8000) and `npm run dev` up; it starts a stub AI service on port 9000.
Needs `playwright` and an `e2e.admin@example.com` / `AdminPass123` admin account.

## Landing page (`/`)
Public page shown before login. `/login` and `/register` contain only the forms.
The repairs gallery is static content (the backend has no public endpoint for completed repairs): edit `src/content/landing.js` and put files in `public/landing/`.
- Use `{ before, after }` only for two photos of the SAME place and angle; use `{ photo }` for any single photograph.
- Add `credit: { author, license, url }` for real photos (shown under the image); remove `illustrative` once the image is a real photo.
- The four bundled photos were supplied by the project owner; add `credit` to each once the source/licence is confirmed.

## Sessions (multi-tab)
Access/refresh tokens are kept in `sessionStorage` (`src/utils/tokenStore.js`), so each browser tab has its own session: admin, citizen, technician and supervisor can be signed in side by side. A session ends when its tab is closed; a reload keeps it. Theme and language are per-browser preferences (`localStorage`).

## Registration
Required fields: four-part Arabic full name, 14-digit national ID (validated: century, real date, governorate code, 18+), Egyptian mobile number, password.
**Backend change still needed:** `RegisterIn.national_id` is optional (`str | None`) in `app/schemas/auth.py`, and the name rule is not enforced server-side. The UI enforces both; direct API calls can still skip them until the backend is changed.

## Backend dependencies (not faked in the UI)
| Area | Missing in backend | UI behaviour |
|---|---|---|
| Citizen profile edit | self-service `PATCH /users/me` (only admin `PATCH /users/{id}` exists) | profile page is read-only |
| File uploads (images/audio/video, task evidence) | upload endpoint / pre-signed URL (only media URLs are stored) | upload controls disabled with a notice |
| Admin | update/delete for departments, categories, teams; list team members | create/list only; notice where a list is missing |
| Supervisor | tickets-by-AI-run and tasks-by-ticket listing, reporter name | notices; reporter shown as an ID |
| Technician | endpoint telling "no team" apart from "no tasks" | shows an empty tasks state |
| Messages | the backend answers in English; departments/categories are seeded in English | the Arabic UI translates known messages and seeded names (display only: `utils/errors.js`, `utils/seedNames.js`, `utils/status.js#historyReason`) |

## Tests (`e2e/`)
`phase7-flow.cjs` (role flows, Arabic), `i18n-map-flow.cjs` (English/light/map), `multitab.cjs` (session isolation), `latin-scan.cjs` (finds English text in the Arabic UI), `audit.cjs` (overflow/missing translations), `a11y-scan.cjs` (unnamed controls, missing alt, duplicate ids).
