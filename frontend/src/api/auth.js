import client from './client';

export const login = (identifier, password) => client.post('/auth/login', { identifier, password }).then((r) => r.data);
export const register = (payload) => client.post('/auth/register', payload).then((r) => r.data);
export const me = () => client.get('/auth/me').then((r) => r.data);
