import { useState } from 'react';
import { Send } from 'lucide-react';
import {
  Button, Input, Textarea, Select, Card, Badge, TicketStatusBadge, TaskStatusBadge, SeverityBadge,
  ConfirmDialog, useToast, EmptyState, ErrorState, LoadingState, Table, StatusTimeline, FileUpload,
} from '../../components/common';
import AiRecommendationCard from '../../components/ai/AiRecommendationCard';
import EvidenceGallery from '../../components/maintenance/EvidenceGallery';
import { TICKET_STATUS } from '../../utils/status';
import { tr } from '../../i18n';

// Component specimen page only (dev builds). Values below are visual specimens to review the
// design system — nothing here is, or feeds, application data.
export default function DesignSystemPreview() {
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const [files, setFiles] = useState([]);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
      <header className="rounded-xl bg-blue-600 p-6 text-white">
        <p className="text-xs font-semibold text-blue-300">EG Civic Operations</p>
        <h1 className="text-2xl font-bold">{tr("معاينة نظام التصميم")}</h1>
        <p className="mt-1 text-sm text-slate-300">{tr("صفحة مرجعية للمكوّنات المشتركة — للتطوير فقط.")}</p>
      </header>

      <Card title={tr("الأزرار")}>
        <div className="flex flex-wrap gap-2">
          <Button>{tr("أساسي")}</Button><Button variant="secondary">{tr("ثانوي")}</Button><Button variant="ghost">{tr("شفاف")}</Button>
          <Button variant="success">{tr("اعتماد")}</Button><Button variant="danger">{tr("رفض")}</Button>
          <Button loading>{tr("جارٍ الحفظ")}</Button><Button disabled>{tr("معطّل")}</Button>
          <Button icon={Send} onClick={() => toast.success(tr("تم الإرسال بنجاح"))}>{tr("إظهار إشعار")}</Button>
          <Button variant="secondary" onClick={() => toast.error(tr("تعذّر تنفيذ العملية"))}>{tr("إشعار خطأ")}</Button>
          <Button variant="secondary" onClick={() => setConfirm(true)}>{tr("نافذة تأكيد")}</Button>
        </div>
      </Card>

      <Card title={tr("حقول الإدخال")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label={tr("الاسم")} placeholder={tr("الاسم الثلاثي")} required />
          <Input label={tr("رقم الهاتف")} error={tr("رقم غير صالح")} defaultValue="0123" dir="ltr" />
          <Select label={tr("المحافظة")} placeholder={tr("اختر")} options={[{ value: 'a', label: tr("خيار أ") }, { value: 'b', label: tr("خيار ب") }]} />
          <Textarea label={tr("وصف المشكلة")} hint={tr("اكتب تفاصيل كافية")} />
        </div>
      </Card>

      <Card title={tr("الشارات")}>
        <div className="flex flex-wrap gap-2">
          {Object.keys(TICKET_STATUS).map((s) => <TicketStatusBadge key={s} value={s} />)}
          <TaskStatusBadge value="in_progress" />
          {['low', 'medium', 'high', 'critical'].map((s) => <SeverityBadge key={s} value={s} />)}
          <Badge tone="info">{tr("مخصص")}</Badge>
        </div>
      </Card>

      <Card title={tr("الخط الزمني للبلاغ")}>
        <div className="space-y-6">
          <StatusTimeline current="awaiting_approval" />
          <StatusTimeline current="rejected" />
        </div>
      </Card>

      <Card title={tr("توصية الذكاء الاصطناعي مقابل القرار البشري")}>
        <AiRecommendationCard
          recommendation={{
            severity: 'high', confidence: 0.86, explanation: tr("نص توضيحي تجريبي لعرض التنسيق فقط."),
            evidence: [
              { id: '1', evidence_type: 'LEGAL_EVIDENCE', snippet: tr("مقتطف قانوني تجريبي"), similarity_score: 0.82 },
              { id: '2', evidence_type: 'SIMILAR_CASE', snippet: tr("حالة مشابهة تجريبية"), similarity_score: 0.74 },
            ],
          }}
          categoryName={tr("تصنيف تجريبي")}
          departmentName={tr("جهة تجريبية")}
          actions={<><Button variant="success">{tr("اعتماد")}</Button><Button variant="secondary">{tr("تعديل")}</Button><Button variant="danger">{tr("رفض")}</Button></>}
        />
      </Card>

      <Card title={tr("جدول")}>
        <Table
          columns={[{ key: 'id', header: '#' }, { key: 'title', header: tr("العنوان") }, { key: 's', header: tr("الحالة"), render: (r) => <TicketStatusBadge value={r.s} /> }]}
          rows={[{ id: 1, title: tr("صف تجريبي"), s: 'assigned' }, { id: 2, title: tr("صف تجريبي آخر"), s: 'completed' }]}
        />
      </Card>

      <Card title={tr("رفع الملفات")}><FileUpload files={files} onChange={setFiles} onReject={toast.error} /></Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card title={tr("حالة فارغة")}><EmptyState title={tr("لا توجد بلاغات حتى الآن")} /></Card>
        <Card title={tr("حالة خطأ")}><ErrorState onRetry={() => toast.info(tr("إعادة المحاولة"))} /></Card>
        <Card title={tr("حالة تحميل")}><LoadingState rows={3} /></Card>
      </div>

      <Card title={tr("معرض الأدلة (فارغ)")}><EvidenceGallery items={[]} /></Card>

      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => setConfirm(false)} title={tr("تأكيد الإجراء")} message={tr("هل أنت متأكد من المتابعة؟")} danger />
    </div>
  );
}
