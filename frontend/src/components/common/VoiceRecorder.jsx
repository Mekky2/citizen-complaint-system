import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Mic, Square, X } from 'lucide-react';
import { tr } from '../../i18n';

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

// Prototype voice panel: round button + ping ring + equalizer bars + timer. Hands back a File via onRecorded
// (and onClear when the user discards it). Nothing is sent anywhere here.
export default function VoiceRecorder({ onRecorded, onClear, onError }) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [url, setUrl] = useState(null);
  const [err, setErr] = useState('');
  const rec = useRef(null);
  const chunks = useRef([]);
  const timer = useRef(null);

  useEffect(() => () => { clearInterval(timer.current); rec.current?.stream?.getTracks().forEach((t) => t.stop()); }, []);

  const start = async () => {
    setErr('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: mr.mimeType || 'audio/webm' });
        setUrl(URL.createObjectURL(blob));
        onRecorded(new File([blob], `voice-${Date.now()}.webm`, { type: blob.type }));
      };
      mr.start();
      rec.current = mr;
      setSeconds(0);
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
      setRecording(true);
    } catch {
      const m = tr("تعذّر الوصول للميكروفون. تأكد من منح الإذن للمتصفح.");
      setErr(m); onError?.(m);
    }
  };
  const stop = () => { rec.current?.stop(); clearInterval(timer.current); setRecording(false); };
  const clear = () => { setUrl(null); onClear?.(); };

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
      <div className="flex items-center gap-4">
        <div className="relative shrink-0">
          {recording && <span className="absolute inset-0 animate-ring rounded-full bg-red-500/60" aria-hidden />}
          <button type="button" onClick={recording ? stop : start} aria-label={recording ? tr("إيقاف التسجيل") : tr("بدء التسجيل الصوتي")}
            className={`relative grid h-16 w-16 place-items-center rounded-full text-white focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-400/60 ${recording ? 'bg-red-600' : 'bg-blue-600 hover:bg-blue-500'}`}>
            {recording ? <Square className="h-6 w-6" fill="currentColor" /> : <Mic className="h-7 w-7" />}
          </button>
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-bold text-slate-100">{recording ? tr("جارٍ التسجيل…") : tr("سجّل ملاحظة صوتية")}</p>
          {recording ? (
            <div className="mt-2 flex items-center gap-3">
              <div className="flex h-8 items-center gap-1" aria-hidden>
                {Array.from({ length: 18 }).map((_, i) => <span key={i} className="h-8 w-1 origin-center animate-eq rounded-full bg-red-400" style={{ animationDelay: `${(i % 6) * 0.12}s` }} />)}
              </div>
              <span className="font-mono text-red-300" dir="ltr">{fmt(seconds)}</span>
            </div>
          ) : <p className="text-sm text-slate-400">{tr("اضغط وتحدث لشرح المشكلة بصوتك.")}</p>}
        </div>
      </div>
      {err && <p role="alert" className="mt-3 flex gap-1.5 text-sm text-red-300"><AlertCircle className="mt-0.5 h-4 w-4" aria-hidden />{err}</p>}
      {url && !recording && (
        <div className="mt-3 flex items-center gap-2">
          <audio controls src={url} className="h-10 flex-1" />
          <button type="button" onClick={clear} aria-label={tr("حذف التسجيل")} className="rounded-lg bg-slate-700 p-2 hover:bg-slate-600"><X className="h-4 w-4" /></button>
        </div>
      )}
    </div>
  );
}
