import { authClient } from '../lib/axios';
import type { AuditLogResponse, LoginRequest, TokenResponse, UserOut } from '../types/api';

export const authApi = {
  login: (body: LoginRequest) =>
    authClient.post<TokenResponse>('/api/auth/login', body).then((r) => r.data),

  me: () =>
    authClient.get<UserOut>('/api/auth/me').then((r) => r.data),

  auditLog: (limit = 100) =>
    authClient.get<AuditLogResponse>('/api/auth/audit-log', { params: { limit } }).then((r) => r.data),
};
