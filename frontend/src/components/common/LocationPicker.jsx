import { useCallback, useEffect, useRef, useState } from 'react';
import { Crosshair, Loader2, MapPinned, Search, TriangleAlert } from 'lucide-react';
import MapView from './MapView';
import { inputCls } from './Field';
import { searchPlaces } from '../../utils/geocode';
import { tr } from '../../i18n';

const GOOD = 15; // metres — stop refining once the fix is this tight
const WATCH_MS = 25000; // give the GPS up to 25 s to settle on its best fix
// Rough bounding box of Egypt; only used to warn, never to block.
const inEgypt = ([lat, lng]) => lat >= 21.9 && lat <= 31.9 && lng >= 24.6 && lng <= 37.0;

export const accuracyLevel = (m) => (m <= 15 ? 'excellent' : m <= 50 ? 'good' : 'poor');
const LEVEL_STYLE = {
  excellent: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300',
  good: 'border-amber-500/40 bg-amber-500/15 text-amber-300',
  poor: 'border-red-500/40 bg-red-500/15 text-red-300',
};

// Controlled location picker. `value` = [lat,lng] | null; `onChange(pos, { source, accuracy })`.
// Ways to set the spot: refined GPS fix (shows accuracy radius), drag the pin / tap the map, search an address,
// or paste exact coordinates. Moving the pin by hand clears the GPS radius because a manual pin is exact.
export default function LocationPicker({ value, onChange, height = 320, autoLocate = true }) {
  const [accuracy, setAccuracy] = useState(null);
  const [gps, setGps] = useState('idle'); // idle | locating | done | denied | unsupported
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null); // null | []
  const [searching, setSearching] = useState(false);
  const [searchErr, setSearchErr] = useState('');
  const [coords, setCoords] = useState('');
  const [coordErr, setCoordErr] = useState('');
  const watch = useRef(null);
  const stopTimer = useRef(null);
  const best = useRef(Infinity);

  const stop = useCallback(() => {
    if (watch.current != null) navigator.geolocation.clearWatch(watch.current);
    clearTimeout(stopTimer.current);
    watch.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const set = (pos, meta) => { setCoordErr(''); setCoords(`${pos[0].toFixed(6)}, ${pos[1].toFixed(6)}`); onChange(pos, meta); };

  const pick = (pos) => { stop(); setAccuracy(null); setGps((g) => (g === 'locating' ? 'idle' : g)); set(pos, { source: 'pin' }); };

  const locate = useCallback(() => {
    if (!navigator.geolocation) { setGps('unsupported'); return; }
    stop();
    best.current = Infinity;
    setGps('locating');
    watch.current = navigator.geolocation.watchPosition(
      (p) => {
        const acc = p.coords.accuracy;
        if (acc <= best.current) { // only ever move to an equal-or-better fix
          best.current = acc;
          setAccuracy(acc);
          set([p.coords.latitude, p.coords.longitude], { source: 'gps', accuracy: acc });
        }
        if (acc <= GOOD) { stop(); setGps('done'); }
      },
      () => { stop(); setGps('denied'); },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 },
    );
    stopTimer.current = setTimeout(() => { stop(); setGps((g) => (g === 'locating' ? 'done' : g)); }, WATCH_MS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stop]);

  useEffect(() => { if (autoLocate) locate(); }, [autoLocate, locate]);

  const runSearch = async (e) => {
    e?.preventDefault();
    if (query.trim().length < 3) return;
    setSearching(true); setSearchErr(''); setResults(null);
    try { setResults(await searchPlaces(query.trim())); } catch { setSearchErr(tr('تعذّر البحث الآن. حرّك الدبوس يدويًا أو جرّب لاحقًا.')); }
    setSearching(false);
  };

  const applyCoords = () => {
    const m = coords.trim().match(/^(-?\d{1,3}(?:\.\d+)?)\s*[,،;\s]\s*(-?\d{1,3}(?:\.\d+)?)$/);
    if (!m) { setCoordErr(tr('اكتب الإحداثيات هكذا: 30.0444, 31.2357')); return; }
    const pos = [Number(m[1]), Number(m[2])];
    if (Math.abs(pos[0]) > 90 || Math.abs(pos[1]) > 180) { setCoordErr(tr('إحداثيات غير صالحة')); return; }
    stop(); setAccuracy(null); setGps('idle'); set(pos, { source: 'manual' });
  };

  const level = accuracy != null ? accuracyLevel(accuracy) : null;

  return (
    <div className="space-y-3">
      <div className="flex gap-2" role="search">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input className={`${inputCls} border-slate-600 !py-2.5 ps-10`} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); runSearch(); } }} placeholder={tr('ابحث عن شارع أو منطقة أو معلم…')} aria-label={tr('بحث عن عنوان')} />
        </div>
        <button type="button" onClick={runSearch} disabled={searching || query.trim().length < 3} className="flex items-center gap-2 rounded-xl bg-slate-700 px-4 text-sm font-bold text-slate-100 hover:bg-slate-600 disabled:opacity-50">
          {searching ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Search className="h-4 w-4" aria-hidden />}{tr('بحث')}
        </button>
      </div>
      {searchErr && <p role="alert" className="text-sm text-red-300">{searchErr}</p>}
      {results && (
        <ul className="max-h-48 overflow-auto rounded-xl border border-slate-600 bg-slate-900/70 text-sm" aria-label={tr('نتائج البحث')}>
          {results.length === 0 && <li className="px-4 py-3 text-slate-400">{tr('لا توجد نتائج. جرّب كلمات أدق أو أضف اسم المدينة.')}</li>}
          {results.map((r) => (
            <li key={r.id}>
              <button type="button" onClick={() => { setResults(null); pick(r.position); }} className="flex w-full items-start gap-2 px-4 py-2.5 text-start hover:bg-slate-700/60">
                <MapPinned className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden /><span className="text-slate-100">{r.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={locate} disabled={gps === 'locating'} className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-500 disabled:opacity-70">
          {gps === 'locating' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Crosshair className="h-4 w-4" aria-hidden />}
          {gps === 'locating' ? tr('جارٍ تحسين الدقة…') : tr('موقعي الحالي')}
        </button>
        {level && (
          <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${LEVEL_STYLE[level]}`} role="status">
            {tr('دقة GPS ±{n} م', { n: Math.round(accuracy) })} — {({ excellent: tr("ممتازة"), good: tr("جيدة"), poor: tr("ضعيفة") }[level])}
          </span>
        )}
      </div>

      <MapView position={value} onPick={pick} height={height} accuracy={accuracy} labels={{ street: tr('خريطة'), satellite: tr('قمر صناعي') }} />

      <p className="text-sm text-slate-400" role="status">
        {gps === 'locating' && tr('نقرّب موقعك من أدق قراءة ممكنة… ابقَ في مكان مكشوف إن أمكن.')}
        {gps === 'denied' && tr('لم نتمكن من تحديد موقعك. فعّل خدمة الموقع للمتصفح أو اضغط على الخريطة لوضع الدبوس.')}
        {gps === 'unsupported' && tr('المتصفح لا يدعم تحديد الموقع. اضغط على الخريطة لوضع الدبوس.')}
        {gps === 'done' && level !== 'poor' && tr('تم تحديد موقعك. اسحب الدبوس لضبطه على المكان بالضبط.')}
        {gps === 'done' && level === 'poor' && tr('دقة الـ GPS ضعيفة هنا (غالبًا داخل مبنى). بدّل إلى «قمر صناعي» وحرّك الدبوس إلى المكان الصحيح.')}
        {gps === 'idle' && !value && tr('اضغط على الخريطة أو ابحث عن العنوان لتحديد مكان المشكلة.')}
        {gps === 'idle' && value && tr('اسحب الدبوس أو اضغط على الخريطة لتعديل الموقع بدقة.')}
      </p>
      {value && !inEgypt(value) && (
        <p role="alert" className="flex items-start gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{tr('هذا الموقع خارج حدود مصر. تأكد من مكان الدبوس.')}</p>
      )}

      <div>
        <label htmlFor="coords" className="mb-1.5 block text-xs font-semibold text-slate-400">{tr('الإحداثيات (خط العرض، خط الطول)')}</label>
        <input id="coords" dir="ltr" inputMode="decimal" className={`${inputCls} border-slate-600 !py-2 font-mono text-sm ${coordErr ? '!border-red-500/70' : ''}`}
          value={coords} onChange={(e) => setCoords(e.target.value)} onBlur={() => coords.trim() && applyCoords()} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); applyCoords(); } }} placeholder="30.044420, 31.235712" />
        {coordErr && <p role="alert" className="mt-1.5 text-sm text-red-300">{coordErr}</p>}
      </div>
    </div>
  );
}
