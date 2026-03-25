import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle responses
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.clear();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Auth
  register: (data: any) => client.post('/auth/register', data),
  login: (data: any) => client.post('/auth/login', data),
  getCurrentUser: () => client.get('/auth/me'),

  // Accounts
  createAccount: (data: any) => client.post('/accounts', data),
  getAccounts: () => client.get('/accounts'),
  getAccount: (id: number) => client.get(`/accounts/${id}`),

  // Bots
  createBot: (accountId: number, data: any) => client.post(`/bots?account_id=${accountId}`, data),
  getBots: (accountId: number) => client.get(`/bots/${accountId}`),
  startBot: (botId: number) => client.post(`/bots/${botId}/start`),
  stopBot: (botId: number) => client.post(`/bots/${botId}/stop`),

  // Trading
  getPositions: (accountId: number) => client.get(`/positions/${accountId}`),
  getTrades: (accountId: number) => client.get(`/trades/${accountId}`),
  getStatistics: (accountId: number) => client.get(`/statistics/${accountId}`),

  // Market
  getPrice: (symbol: string) => client.get(`/market/price/${symbol}`),
  getPrices: (symbols: string) => client.get(`/market/prices?symbols=${symbols}`),

  // Financial
  deposit: (accountId: number, data: any) => client.post(`/deposits?account_id=${accountId}`, data),
  withdraw: (accountId: number, data: any) => client.post(`/withdrawals?account_id=${accountId}`, data),

  // Alerts & Reports
  getAlerts: (accountId: number) => client.get(`/alerts/${accountId}`),
  generateReport: (accountId: number) => client.get(`/reports/${accountId}`),

  // Health
  health: () => client.get('/health'),
};

export default client;
