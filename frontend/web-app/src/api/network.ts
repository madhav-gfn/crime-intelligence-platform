import { networkClient } from '../lib/axios';
import type {
  CommunityOut, EgoNetworkResponse, GraphResponse, GraphStats,
  HubOut, NetworkPathResponse, PersonNode, RepeatOffenderOut,
} from '../types/api';

export const networkApi = {
  stats: () =>
    networkClient.get<GraphStats>('/api/network/stats').then((r) => r.data),

  graph: (params?: { district?: string; min_shared_cases?: number; limit_nodes?: number }) =>
    networkClient.get<GraphResponse>('/api/network/graph', { params }).then((r) => r.data),

  person: (person_id: string) =>
    networkClient.get<PersonNode>(`/api/network/person/${encodeURIComponent(person_id)}`).then((r) => r.data),

  egoNetwork: (person_id: string, depth = 1) =>
    networkClient
      .get<EgoNetworkResponse>(`/api/network/person/${encodeURIComponent(person_id)}/ego`, { params: { depth } })
      .then((r) => r.data),

  communities: (min_size = 3) =>
    networkClient.get<CommunityOut[]>('/api/network/communities', { params: { min_size } }).then((r) => r.data),

  hubs: (top_n = 20) =>
    networkClient.get<HubOut[]>('/api/network/hubs', { params: { top_n } }).then((r) => r.data),

  path: (source: string, target: string) =>
    networkClient
      .get<NetworkPathResponse>('/api/network/path', { params: { source, target } })
      .then((r) => r.data),

  repeatOffenders: (min_cases = 2, limit = 50) =>
    networkClient
      .get<RepeatOffenderOut[]>('/api/network/repeat-offenders', { params: { min_cases, limit } })
      .then((r) => r.data),
};
