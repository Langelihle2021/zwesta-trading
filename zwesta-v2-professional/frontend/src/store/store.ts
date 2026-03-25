import { create } from 'zustand'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  is_admin: boolean
}

interface AuthStore {
  user: User | null
  token: string | null
  loading: boolean
  error: string | null
  login: (token: string, user: User) => void
  logout: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!) : null,
  token: localStorage.getItem('access_token'),
  loading: false,
  error: null,
  
  login: (token: string, user: User) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ user, token, error: null })
  },
  
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    set({ user: null, token: null })
  },
  
  setLoading: (loading: boolean) => set({ loading }),
  setError: (error: string | null) => set({ error })
}))

interface TradingStore {
  trades: any[]
  positions: any[]
  statistics: any
  selectedSymbol: string | null
  loading: boolean
  error: string | null
  setTrades: (trades: any[]) => void
  setPositions: (positions: any[]) => void
  setStatistics: (stats: any) => void
  setSelectedSymbol: (symbol: string | null) => void
}

export const useTradingStore = create<TradingStore>((set) => ({
  trades: [],
  positions: [],
  statistics: {},
  selectedSymbol: null,
  loading: false,
  error: null,
  
  setTrades: (trades) => set({ trades }),
  setPositions: (positions) => set({ positions }),
  setStatistics: (statistics) => set({ statistics }),
  setSelectedSymbol: (selectedSymbol) => set({ selectedSymbol })
}))
