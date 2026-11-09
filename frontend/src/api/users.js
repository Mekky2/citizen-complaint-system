import client from './client';

export const getMyProfile = () => client.get('/users/me').then((r) => r.data);
export const listUsers = (params) => client.get('/users', { params }).then((r) => r.data);
export const updateUser = (id, payload) => client.patch(`/users/${id}`, payload).then((r) => r.data);
export const createStaff = (payload) => client.post('/admin/staff', payload).then((r) => r.data);
