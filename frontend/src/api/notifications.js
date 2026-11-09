import client from './client';

export const listNotifications = (params) => client.get('/notifications', { params }).then((r) => r.data);
export const markRead = (id) => client.patch(`/notifications/${id}/read`).then((r) => r.data);
