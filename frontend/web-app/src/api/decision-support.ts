import { decisionClient } from '../lib/axios';
import type {
  CasePriority, CasePriorityListResponse, DecisionSupportStats,
  DistrictBriefing, PersonDossier,
} from '../types/api';

export const decisionApi = {
  stats: () =>
    decisionClient.get<DecisionSupportStats>('/api/decision-support/stats').then((r) => r.data),

  casePriority: (params?: { priority_tier?: 'LOW' | 'MEDIUM' | 'HIGH'; limit?: number }) =>
    decisionClient.get<CasePriorityListResponse>('/api/decision-support/case-priority', { params }).then((r) => r.data),

  caseDetail: (fir_id: string) =>
    decisionClient.get<CasePriority>(`/api/decision-support/case/${encodeURIComponent(fir_id)}`).then((r) => r.data),

  personDossier: (person_id: string) =>
    decisionClient.get<PersonDossier>(`/api/decision-support/person-dossier/${encodeURIComponent(person_id)}`).then((r) => r.data),

  districtBriefing: (district: string) =>
    decisionClient.get<DistrictBriefing>(`/api/decision-support/district-briefing/${encodeURIComponent(district)}`).then((r) => r.data),
};
