import client from './client';

// supervisor/admin only. Moves a 'submitted' ticket to 'under_ai_review'; the AI service calls back separately.
export const triggerAiRun = (ticketId) => client.post(`/ai/tickets/${ticketId}/trigger`).then((r) => r.data);
// Backend endpoint required: GET /ai/tickets/{ticket_id}/recommendation  (AiRecommendationOut incl. evidence[])
export const getRecommendation = (ticketId) => client.get(`/ai/tickets/${ticketId}/recommendation`).then((r) => r.data);
