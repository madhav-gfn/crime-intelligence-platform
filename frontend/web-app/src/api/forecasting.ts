import { forecastingClient } from '../lib/axios';
import type { DatasetStats, DistrictForecastBundle, RankingResponse } from '../types/api';

export const forecastingApi = {
  stats: () =>
    forecastingClient.get<DatasetStats>('/api/forecasting/stats').then((r) => r.data),

  districtForecast: (district: string) =>
    forecastingClient.get<DistrictForecastBundle>(`/api/forecasting/district/${encodeURIComponent(district)}`).then((r) => r.data),

  rankings: (params?: { series?: 'TOTAL' | 'VIOLENT' | 'PROPERTY'; order?: 'asc' | 'desc'; limit?: number }) =>
    forecastingClient.get<RankingResponse>('/api/forecasting/rankings', { params }).then((r) => r.data),
};
