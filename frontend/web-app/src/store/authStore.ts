import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Role = 'ANALYST' | 'INVESTIGATOR' | 'ADMIN';

export const ROLE_RANK: Record<Role, number> = {
  ANALYST: 1,
  INVESTIGATOR: 2,
  ADMIN: 3,
};

interface AuthState {
  token: string | null;
  role: Role | null;
  full_name: string | null;
  username: string | null;
  isAuthenticated: boolean;

  login: (token: string, role: Role, full_name: string, username: string) => void;
  logout: () => void;
  hasRole: (required: Role) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      role: null,
      full_name: null,
      username: null,
      isAuthenticated: false,

      login: (token, role, full_name, username) =>
        set({ token, role, full_name, username, isAuthenticated: true }),

      logout: () =>
        set({ token: null, role: null, full_name: null, username: null, isAuthenticated: false }),

      hasRole: (required: Role) => {
        const { role } = get();
        if (!role) return false;
        return ROLE_RANK[role] >= ROLE_RANK[required];
      },
    }),
    {
      name: 'crimint-auth',
      partialize: (state) => ({
        token: state.token,
        role: state.role,
        full_name: state.full_name,
        username: state.username,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
