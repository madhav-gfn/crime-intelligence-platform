import { profilingClient } from '../lib/axios';
import type { ModelInfo, PersonRiskProfile, PredictResponse, RiskListResponse } from '../types/api';

export const profilingApi = {
  modelInfo: () =>
    profilingClient.get<ModelInfo>('/api/offender-profiling/model-info').then((r) => r.data),

  person: (person_id: string) =>
    profilingClient.get<PersonRiskProfile>(`/api/offender-profiling/person/${encodeURIComponent(person_id)}`).then((r) => r.data),

  riskList: (risk_tier: 'LOW' | 'MEDIUM' | 'HIGH' = 'HIGH', limit = 100) =>
    profilingClient
      .get<RiskListResponse>('/api/offender-profiling/risk-list', { params: { risk_tier, limit } })
      .then((r) => r.data),

  predict: (params: {
    prior_case_count: number;
    distinct_prior_crime_types: number;
    prior_violent_count?: number;
    prior_property_count?: number;
    days_since_first_case?: number;
    current_is_violent?: boolean;
    current_is_property?: boolean;
    gender?: 'M' | 'F';
    age: number;
    state?: string;
  }) =>
    profilingClient.get<PredictResponse>('/api/offender-profiling/predict', { params }).then((r) => r.data),
};
