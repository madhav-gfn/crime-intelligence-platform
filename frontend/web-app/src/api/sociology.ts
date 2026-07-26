import { sociologyClient } from '../lib/axios';
import type {
  CorrelationsResponse, DistrictListResponse, DistrictProfile,
  RankingResponse, ScatterResponse,
} from '../types/api';

export const sociologyApi = {
  districts: () =>
    sociologyClient.get<DistrictListResponse>('/api/sociology/districts').then((r) => r.data),

  districtProfile: (district: string) =>
    sociologyClient.get<DistrictProfile>(`/api/sociology/district/${encodeURIComponent(district)}`).then((r) => r.data),

  correlations: (min_population = 0) =>
    sociologyClient.get<CorrelationsResponse>('/api/sociology/correlations', { params: { min_population } }).then((r) => r.data),

  rankings: (params: { sort_by: string; order?: 'asc' | 'desc'; limit?: number; min_population?: number }) =>
    sociologyClient.get<RankingResponse>('/api/sociology/rankings', { params }).then((r) => r.data),

  scatter: (indicator: string, crime_metric = 'crime_rate_per_100k') =>
    sociologyClient
      .get<ScatterResponse>(`/api/sociology/scatter/${encodeURIComponent(indicator)}`, { params: { crime_metric } })
      .then((r) => r.data),
};
