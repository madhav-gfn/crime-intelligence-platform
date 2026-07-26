import { patternsClient } from '../lib/axios';
import type {
  DatasetStats, DistrictSeverityResponse, EmergingResponse,
  HotspotResponse, SimilarCasesResponse, TrendResponse,
} from '../types/api';

export const patternsApi = {
  stats: () =>
    patternsClient.get<DatasetStats>('/api/patterns/stats').then((r) => r.data),

  hotspots: (params?: {
    crime_type?: string;
    district?: string;
    start_date?: string;
    end_date?: string;
    eps_km?: number;
    min_points?: number;
  }) =>
    patternsClient.get<HotspotResponse>('/api/patterns/hotspots', { params }).then((r) => r.data),

  districtSeverity: (min_crimes = 10) =>
    patternsClient
      .get<DistrictSeverityResponse>('/api/patterns/district-severity', { params: { min_crimes } })
      .then((r) => r.data),

  trends: (granularity: 'monthly' | 'weekday' | 'hourly', params?: { crime_type?: string; district?: string }) =>
    patternsClient
      .get<TrendResponse>(`/api/patterns/trends/${granularity}`, { params })
      .then((r) => r.data),

  emerging: (params?: { recent_days?: number; baseline_days?: number; min_recent_count?: number }) =>
    patternsClient.get<EmergingResponse>('/api/patterns/emerging', { params }).then((r) => r.data),

  similarCases: (fir_id: string, top_n = 10) =>
    patternsClient
      .get<SimilarCasesResponse>(`/api/patterns/similar-cases/${encodeURIComponent(fir_id)}`, { params: { top_n } })
      .then((r) => r.data),
};
