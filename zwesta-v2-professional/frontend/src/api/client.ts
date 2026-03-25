import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for handling 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth endpoints
export const authAPI = {
  signup: (data: { username: string; email: string; password: string; full_name: string }) =>
    apiClient.post('/auth/signup', data),
  
  login: (data: { username: string; password: string }) =>
    apiClient.post('/auth/login', data),
  
  refresh: () => apiClient.post('/auth/refresh'),
  
  me: () => apiClient.get('/auth/me'),
  
  logout: () => apiClient.post('/auth/logout')
}

// Trading endpoints
export const tradingAPI = {
  getTrades: (filters?: { symbol?: string; status?: string }) =>
    apiClient.get('/trading/trades', { params: filters }),
  
  getPositions: () => apiClient.get('/trading/positions'),
  
  getSymbols: () => apiClient.get('/trading/symbols'),
  
  getMarketData: (symbol: string) =>
    apiClient.get(`/trading/market-data/${symbol}`),
  
  getStatistics: () => apiClient.get('/trading/statistics'),
  
  createTrade: (data: {
    symbol: string
    trade_type: string
    entry_price: number
    volume: number
    stop_loss?: number
    take_profit?: number
  }) => apiClient.post('/trading/trades', data),
  
  closePosition: (id: number) =>
    apiClient.post(`/trading/${id}/close`)
}

// Account endpoints
export const accountAPI = {
  getAccounts: () => apiClient.get('/accounts/'),
  
  getAccount: (id: number) => apiClient.get(`/accounts/${id}`),
  
  createDeposit: (account_id: number, data: {
    amount: number
    currency: string
    payment_method: string
  }) => apiClient.post(`/accounts/${account_id}/deposits`, data),
  
  createWithdrawal: (account_id: number, data: {
    amount: number
    currency: string
    payment_method: string
    account_details: string
  }) => apiClient.post(`/accounts/${account_id}/withdrawals`, data),
  
  getDepositHistory: (account_id: number) =>
    apiClient.get(`/accounts/${account_id}/deposits`),
  
  getWithdrawalHistory: (account_id: number) =>
    apiClient.get(`/accounts/${account_id}/withdrawals`)
}

// Alert endpoints
export const alertAPI = {
  getAlerts: () => apiClient.get('/alerts/'),
  
  createAlert: (data: {
    alert_type: string
    symbol: string
    threshold: number
    send_whatsapp: boolean
    send_email: boolean
  }) => apiClient.post('/alerts/', data),
  
  updateAlert: (id: number, data: any) =>
    apiClient.put(`/alerts/${id}`, data),
  
  deleteAlert: (id: number) =>
    apiClient.delete(`/alerts/${id}`),
  
  enableAlert: (id: number) =>
    apiClient.post(`/alerts/${id}/enable`),
  
  disableAlert: (id: number) =>
    apiClient.post(`/alerts/${id}/disable`)
}

// Report endpoints
export const reportAPI = {
  getReports: () => apiClient.get('/reports/'),
  
  generateReport: (data: {
    start_date: string
    end_date: string
    account_id: number
  }) => apiClient.post('/reports/generate', data),
  
  getReport: (id: number) => apiClient.get(`/reports/${id}`),
  
  deleteReport: (id: number) =>
    apiClient.delete(`/reports/${id}`)
}

export default apiClient
