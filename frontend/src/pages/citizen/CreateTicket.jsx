import { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Building2, Camera, CheckCircle2, FilePlus2, IdCard, MapPin, Phone, Send, Tag, User } from 'lucide-react';
import { Button, Card, Input, Textarea, FileUpload, EndpointRequired, CopyButton, PageHeader, useToast } from '../../components/common';
import LocationPicker from '../../components/common/LocationPicker';
import VoiceRecorder from '../../components/common/VoiceRecorder';
import { createTicket } from '../../api/tickets';
import { UPLOADS_ENABLED, uploadFile } from '../../api/storage';
import useFetch from '../../hooks/useFetch';
import { getMyProfile } from '../../api/users';
import { errorMessage } from '../../utils/errors';
import { reverseGeocode } from '../../utils/geocode';
import { ticketRef } from '../../utils/format';
import { tr } from '../../i18n';

// Single-page report form (prototype layout): reporter · problem · media on one side, location on the other.
// The reporter card is read-only (from the signed-in account). There is deliberately NO AI step for citizens:
// the backend only lets supervisors/admins trigger analysis, and a ticket must exist before media can be attached.
export default function CreateTicket() {
  const toast = useToast();
  const { data: user } = useFetch(getMyProfile, []); // /users/me carries the phone; the auth context only has id/name/role
  const [f, setF] = useState({ title: '', description: '', address: '', governorate: '', city: '' });
  const [pos, setPos] = useState(null); // [lat, lng]
  const [files, setFiles] = useState([]);
  const [touched, setTouched] = useState(false);
  const [geoBusy, setGeoBusy] = useState(false);
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null); // { ticket, failedMedia }
  const geoSeq = useRef(0);
  const [pickerKey, setPickerKey] = useState(0);

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const descError = f.description.trim().length < 10 ? tr("اكتب وصفًا لا يقل عن 10 أحرف") : null;

  const movePin = useCallback(async (np) => {
    setPos(np);
    const id = ++geoSeq.current;
    setGeoBusy(true);
    try {
      await new Promise((r) => setTimeout(r, 700)); // debounce: GPS refinement emits many fixes; Nominatim allows ~1 req/s
      if (id !== geoSeq.current) return;
      const g = await reverseGeocode(np);
      if (id === geoSeq.current) setF((s) => ({ ...s, address: g.street || s.address, governorate: g.governorate || s.governorate, city: g.city || s.city }));
    } catch { /* manual entry stays available */ }
    if (id === geoSeq.current) setGeoBusy(false);
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setTouched(true);
    if (descError) { setFormError(tr("اكتب وصف المشكلة (10 أحرف على الأقل).")); return; }
    if (!pos) { setFormError(tr("حدّد موقع المشكلة على الخريطة: اضغط عليها أو اسحب الدبوس.")); return; }
    setFormError('');
    setBusy(true);
    let ticket;
    try {
      ticket = await createTicket({
        description: f.description.trim(),
        title: f.title.trim() || undefined,
        lat: pos[0], lng: pos[1],
        address: f.address.trim() || undefined,
        governorate: f.governorate.trim() || undefined,
        city: f.city.trim() || undefined,
      });
    } catch (err) {
      setFormError(errorMessage(err, tr("تعذّر إرسال البلاغ")));
      setBusy(false);
      return;
    }
    // The ticket exists now. Media is best-effort: a media failure must not look like the ticket failed.
    let failed = 0;
    for (const file of files) {
      try { await uploadFile(ticket.id, file); } catch { failed += 1; }
    }
    setBusy(false);
    setDone({ ticket, failed });
  };

  const reset = () => { setDone(null); setF({ title: '', description: '', address: '', governorate: '', city: '' }); setFiles([]); setPos(null); setTouched(false); setPickerKey((k) => k + 1); };

  if (done) {
    const ref = ticketRef(done.ticket.id, done.ticket.created_at);
    return (
      <div className="mx-auto max-w-xl animate-rise rounded-2xl border border-slate-700 bg-slate-800/80 p-8 text-center shadow-xl">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-500/20"><CheckCircle2 className="h-9 w-9 text-emerald-400" aria-hidden /></div>
        <h1 className="mt-4 text-2xl font-extrabold text-slate-50">{tr("تم استلام بلاغك")}</h1>
        <p className="mt-2 text-slate-300">{tr("سيراجعه المشرف ويحدد الإجراء المناسب، وستصلك إشعارات بكل تحديث.")}</p>
        <div className="mt-5 rounded-xl border border-slate-600 bg-slate-900 p-4">
          <p className="text-sm text-slate-400">{tr("رقم البلاغ")}</p>
          <p className="mt-1 font-mono text-2xl font-bold text-blue-300" dir="ltr">{ref}</p>
          <div className="mt-2"><CopyButton text={ref} /></div>
        </div>
        {done.failed > 0 && <p role="status" className="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">{tr("تم إرسال البلاغ، لكن تعذّر رفع")} {done.failed} {tr("من المرفقات.")}</p>}
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to={`/citizen/tickets/${done.ticket.id}`}><Button size="lg" className="!h-12 !text-base">{tr("متابعة البلاغ")}</Button></Link>
          <Button variant="secondary" size="lg" className="!h-12 !text-base" onClick={reset}>{tr("بلاغ جديد")}</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={tr("تقديم بلاغ جديد")} subtitle={tr("وصف المشكلة وموقعها يكفيان لبدء المراجعة.")} icon={FilePlus2} />
      <form onSubmit={submit} noValidate className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card title={tr("بيانات مقدّم البلاغ")} icon={IdCard} subtitle={tr("من حسابك — لا يمكن تعديلها هنا")}>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div className="flex items-center gap-2"><User className="h-4 w-4 text-slate-400" aria-hidden /><div><dt className="text-xs text-slate-400">{tr("الاسم")}</dt><dd className="font-bold text-slate-100">{user?.name || '—'}</dd></div></div>
              <div className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" aria-hidden /><div><dt className="text-xs text-slate-400">{tr("رقم الموبايل")}</dt><dd className="font-bold text-slate-100" dir="ltr">{user?.phone || '—'}</dd></div></div>
            </dl>
          </Card>

          <Card title={tr("وصف المشكلة")} icon={Tag}>
            <div className="space-y-4">
              <Input label={tr("عنوان البلاغ (اختياري)")} value={f.title} onChange={set('title')} placeholder={tr("مثال: كسر في ماسورة مياه")} />
              <Textarea label={tr("وصف المشكلة")} required rows={5} value={f.description} onChange={set('description')} error={touched ? descError : null}
                hint={tr("اشرح المشكلة ومكانها بوضوح ليسهل على المشرف مراجعتها.")} placeholder={tr("اشرح المشكلة بالتفصيل…")} />
            </div>
          </Card>

          <Card title={tr("وسائط البلاغ")} icon={Camera}>
            {UPLOADS_ENABLED ? (
              <div className="space-y-5">
                <VoiceRecorder onRecorded={(file) => setFiles((fs) => [...fs, file])} onClear={() => setFiles((fs) => fs.filter((x) => !x.type.startsWith('audio/')))} onError={toast.error} />
                <FileUpload files={files.filter((x) => !x.type.startsWith('audio/'))} onChange={(imgs) => setFiles((fs) => [...fs.filter((x) => x.type.startsWith('audio/')), ...imgs])} accept="image/*,video/*" onReject={toast.error} />
              </div>
            ) : (
              <EndpointRequired endpoint={tr("رفع الملفات (رابط رفع مباشر)")}>
                {tr("الخادم يحفظ روابط المرفقات فقط ولا يوفّر رفعًا للملفات بعد، لذلك يمكنك إرسال البلاغ بالوصف والموقع الآن وإضافة الصور لاحقًا.")}
              </EndpointRequired>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title={tr("موقع المشكلة")} icon={MapPin}>
            <LocationPicker key={pickerKey} value={pos} onChange={(p) => movePin(p)} />
            <div className="mt-5 space-y-4">
              <Input label={tr("الشارع / العنوان")} value={f.address} onChange={set('address')} placeholder={geoBusy ? tr("جارٍ التحديد…") : tr("اسم الشارع")} />
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label={tr("المحافظة")} icon={Building2} value={f.governorate} onChange={set('governorate')} placeholder={geoBusy ? tr("جارٍ التحديد…") : tr("المحافظة")} />
                <Input label={tr("المدينة")} value={f.city} onChange={set('city')} placeholder={geoBusy ? tr("جارٍ التحديد…") : tr("المدينة")} />
              </div>
            </div>
          </Card>

          {formError && <p role="alert" className="flex items-start gap-2 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-red-200"><AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />{formError}</p>}
          <Button type="submit" size="lg" icon={Send} loading={busy} className="w-full">{tr("إرسال البلاغ")}</Button>
        </div>
      </form>
    </div>
  );
}
