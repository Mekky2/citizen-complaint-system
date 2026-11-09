import { tr } from '../i18n';

// Human labels for audit-log codes. Unknown codes fall back to the raw value, so new backend actions still show up.
const ACTION = {
  register: tr('تسجيل مواطن جديد'),
  create_ticket: tr('إنشاء بلاغ'),
  create_staff_user: tr('إنشاء حساب موظف'),
  create_department: tr('إضافة جهة'),
  create_maintenance_team: tr('إنشاء فريق صيانة'),
  add_team_member: tr('إضافة فني إلى فريق'),
  trigger_ai_run: tr('تشغيل التحليل الآلي'),
  supervisor_decision: tr('قرار المشرف'),
  create_maintenance_task: tr('إسناد مهمة صيانة'),
  update_task_status: tr('تحديث حالة مهمة'),
  create_verification: tr('التحقق من تنفيذ مهمة'),
};
const ENTITY = {
  ticket: tr('بلاغ'),
  user: tr('مستخدم'),
  department: tr('جهة'),
  maintenance_team: tr('فريق صيانة'),
  maintenance_task: tr('مهمة صيانة'),
};
export const auditAction = (a) => ACTION[a] ?? a;
export const auditEntity = (e) => ENTITY[e] ?? e;
export const AUDIT_ENTITY_TYPES = Object.keys(ENTITY);
