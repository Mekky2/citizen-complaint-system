import client from './client';

export const listTickets = (params) => client.get('/tickets', { params }).then((r) => r.data);
export const getTicket = (id) => client.get(`/tickets/${id}`).then((r) => r.data);
export const createTicket = (payload) => client.post('/tickets', payload).then((r) => r.data);
// Metadata only — { type: 'image'|'video'|'audio', url }. The binary goes to object storage (see api/storage.js).
export const addTicketMedia = (id, payload) => client.post(`/tickets/${id}/media`, payload).then((r) => r.data);
