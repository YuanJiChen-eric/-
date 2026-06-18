import axios from 'axios';

const request = axios.create({
    baseURL: 'http://localhost:8082/api',  // 后端地址，等队友告诉你后改
    timeout: 30000,
});

// 智能问答
export const chat = (question) => request.post('/chat', { query: question });

// 转人工
export const createTicket = (data) => request.post('/tickets', data);

// 账号管理
export const getUsers = () => request.get('/operators');
export const createUser = (data) => request.post('/operators', data);
export const updateUser = (id, data) => request.put(`/operators/${id}`, data);
export const deleteUser = (id) => request.delete(`/operators/${id}`);

// 工单管理
export const getTickets = (params) => request.get('/tickets', { params });
export const resolveTicket = (id, data) => request.post(`/tickets/${id}/resolve`, data);
