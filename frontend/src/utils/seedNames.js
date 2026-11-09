import { LANG } from '../i18n';

// The database ships with English names for the default departments and categories.
// In the Arabic UI they are shown in Arabic (display only — stored data is untouched).
// Names created by an admin are shown exactly as typed.
const SEED = {
  'Cleaning & Beautification Authority': 'هيئة النظافة والتجميل',
  'Electricity Company': 'شركة الكهرباء',
  'Local Administration': 'الإدارة المحلية',
  'Roads & Bridges Authority': 'هيئة الطرق والكباري',
  'Water & Wastewater Company': 'شركة المياه والصرف الصحي',
  'Waste collection, street cleaning, public spaces': 'جمع القمامة ونظافة الشوارع والأماكن العامة',
  'Street lighting, electrical infrastructure faults': 'إنارة الشوارع وأعطال شبكات الكهرباء',
  'General governorate/local-administration matters not owned by a specialized authority': 'الشؤون العامة للمحافظة والإدارة المحلية التي لا تختص بها جهة متخصصة',
  'Road surface, potholes, bridges, traffic infrastructure': 'أسطح الطرق والحفر والكباري والبنية التحتية المرورية',
  'Water mains, sewage, drainage': 'خطوط المياه والصرف الصحي والتصريف',
  'Garbage buildup': 'تراكم القمامة',
  'Other': 'أخرى',
  'Pothole / road damage': 'حفر وتلف الطرق',
  'Sewage overflow': 'طفح الصرف الصحي',
  'Street light outage': 'انقطاع إنارة الشوارع',
  'Water main break': 'كسر خط مياه رئيسي',
};
export const seedLabel = (v) => (LANG === 'ar' && v && SEED[v]) || v;
export const localizeRow = (r) => (LANG === 'ar' && r ? { ...r, name: seedLabel(r.name), description: seedLabel(r.description) } : r);
