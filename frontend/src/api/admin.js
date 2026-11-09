import client from './client';
import { localizeRow } from '../utils/seedNames';

export const listDepartments = () => client.get('/admin/departments').then((r) => r.data.map(localizeRow));
export const createDepartment = (payload) => client.post('/admin/departments', payload).then((r) => r.data);
export const listCategories = () => client.get('/admin/categories').then((r) => r.data.map(localizeRow));
export const createCategory = (payload) => client.post('/admin/categories', payload).then((r) => r.data);
export const listAuditLogs = (params) => client.get('/admin/audit-logs', { params }).then((r) => r.data);
