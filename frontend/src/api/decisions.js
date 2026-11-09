import client from './client';

// action: 'approve' | 'edit' | 'reject'. reject requires `reason`.
export const submitDecision = (ticketId, payload) => client.post(`/supervisor/tickets/${ticketId}/decisions`, payload).then((r) => r.data);
// result: 'pass' | 'fail'
export const verifyTask = (taskId, payload) => client.post(`/verification/tasks/${taskId}`, payload).then((r) => r.data);
