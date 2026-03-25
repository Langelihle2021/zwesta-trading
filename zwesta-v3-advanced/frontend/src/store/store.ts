import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  phone?: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  setAuth: (user: User, token: string, refreshToken: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,
      setAuth: (user, token, refreshToken) =>
        set({ user, token, refreshToken }),
      logout: () => {
        localStorage.clear();
        set({ user: null, token: null, refreshToken: null });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
      }),
    }
  )
);

interface TradingStore {
  selectedAccountId: number | null;
  setSelectedAccount: (id: number) => void;
  accounts: any[];
  setAccounts: (accounts: any[]) => void;
}

export const useTradingStore = create<TradingStore>((set) => ({
  selectedAccountId: null,
  setSelectedAccount: (id) => set({ selectedAccountId: id }),
  accounts: [],
  setAccounts: (accounts) => set({ accounts }),
}));
