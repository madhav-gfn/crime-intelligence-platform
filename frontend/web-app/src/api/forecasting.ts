import { forecastingClient } from '../lib/axios';
import type { ForecastDatasetStats, DistrictForecastBundle, ForecastRankingResponse } from '../types/api';

export const forecastingApi = {
  stats: () =>
    forecastingClient.get<ForecastDatasetStats>('/api/forecasting/stats').then((r) => r.data),

  districtForecast: (district: string) =>
    forecastingClient.get<DistrictForecastBundle>(`/api/forecasting/district/${encodeURIComponent(district)}`).then((r) => r.data),

  rankings: (params?: { series?: 'TOTAL' | 'VIOLENT' | 'PROPERTY'; order?: 'asc' | 'desc'; limit?: number }) =>
    forecastingClient.get<ForecastRankingResponse>('/api/forecasting/rankings', { params }).then((r) => r.data),
};
