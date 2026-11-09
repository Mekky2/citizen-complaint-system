import client from './client';

export const listTeams = (params) => client.get('/maintenance/teams', { params }).then((r) => r.data);
export const createTeam = (payload) => client.post('/maintenance/teams', payload).then((r) => r.data);
export const addTeamMember = (teamId, user_id) => client.post(`/maintenance/teams/${teamId}/members`, { user_id }).then((r) => r.data);
// Backend endpoint required: GET /maintenance/teams/{team_id}/members
export const listTeamMembers = (teamId) => client.get(`/maintenance/teams/${teamId}/members`).then((r) => r.data);

export const createTask = (ticketId, payload) => client.post(`/maintenance/tickets/${ticketId}/tasks`, payload).then((r) => r.data);
// Backend endpoint required: GET /maintenance/tickets/{ticket_id}/tasks (supervisor needs the task id to verify)
export const listTicketTasks = (ticketId) => client.get(`/maintenance/tickets/${ticketId}/tasks`).then((r) => r.data);
export const listMyTasks = () => client.get('/maintenance/tasks/mine').then((r) => r.data);
export const updateTaskStatus = (taskId, status, notes) => client.patch(`/maintenance/tasks/${taskId}/status`, { status, notes }).then((r) => r.data);
export const listEvidence = (taskId) => client.get(`/maintenance/tasks/${taskId}/evidence`).then((r) => r.data);
export const addEvidence = (taskId, payload) => client.post(`/maintenance/tasks/${taskId}/evidence`, payload).then((r) => r.data);
