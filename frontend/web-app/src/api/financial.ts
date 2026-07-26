import { financialClient } from '../lib/axios';
import type {
  AccountProfile, DatasetStats, EvaluationResponse,
  FinancialPathResponse, PatternsResponse, SuspiciousAccountsResponse,
} from '../types/api';

export const financialApi = {
  stats: () =>
    financialClient.get<DatasetStats>('/api/financial/stats').then((r) => r.data),

  account: (account_id: string) =>
    financialClient.get<AccountProfile>(`/api/financial/account/${encodeURIComponent(account_id)}`).then((r) => r.data),

  suspiciousAccounts: (risk_tier: 'LOW' | 'MEDIUM' | 'HIGH' = 'HIGH', limit = 100) =>
    financialClient
      .get<SuspiciousAccountsResponse>('/api/financial/suspicious-accounts', { params: { risk_tier, limit } })
      .then((r) => r.data),

  patterns: (params?: { typology?: string; limit?: number }) =>
    financialClient.get<PatternsResponse>('/api/financial/patterns', { params }).then((r) => r.data),

  path: (source: string, target: string) =>
    financialClient.get<FinancialPathResponse>('/api/financial/path', { params: { source, target } }).then((r) => r.data),

  evaluate: () =>
    financialClient.get<EvaluationResponse>('/api/financial/evaluate').then((r) => r.data),
};
