import { explainClient } from '../lib/axios';
import type { MethodologyOverview, ModelExplainabilityInfo, PersonExplanation, PredictExplainResponse } from '../types/api';

export const explainApi = {
  methodology: () =>
    explainClient.get<MethodologyOverview>('/api/explainability/methodology').then((r) => r.data),

  modelInfo: () =>
    explainClient.get<ModelExplainabilityInfo>('/api/explainability/model-info').then((r) => r.data),

  personExplanation: (person_id: string) =>
    explainClient.get<PersonExplanation>(`/api/explainability/person/${encodeURIComponent(person_id)}`).then((r) => r.data),

  predictExplain: (params: {
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
    explainClient.get<PredictExplainResponse>('/api/explainability/predict-explain', { params }).then((r) => r.data),
};
