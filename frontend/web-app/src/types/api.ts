// ─────────────────────────────────────────────────────────────────────────────
// API TypeScript interfaces — derived directly from every backend schema.py
// ─────────────────────────────────────────────────────────────────────────────

// ── Auth Service ─────────────────────────────────────────────────────────────
export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: 'ANALYST' | 'INVESTIGATOR' | 'ADMIN';
  full_name: string;
}

export interface UserOut {
  username: string;
  full_name: string;
  role: 'ANALYST' | 'INVESTIGATOR' | 'ADMIN';
  rank_context: string;
}

export interface AuditLogEntry {
  timestamp: string;
  event: string;
  username: string;
  success: boolean;
  detail: string;
}

export interface AuditLogResponse {
  count: number;
  entries: AuditLogEntry[];
}

// ── Network Analysis ─────────────────────────────────────────────────────────
export interface PersonNode {
  person_id: string;
  full_name: string;
  gender: string;
  age: number;
  address_district: string;
  address_state: string;
  roles: string[];
  prior_case_count: number;
  risk_tier?: string | null;
  degree: number;
}

export interface NetworkEdgeOut {
  person_id_a: string;
  person_id_b: string;
  shared_fir_count: number;
  fir_ids: string[];
}

export interface GraphResponse {
  nodes: PersonNode[];
  edges: NetworkEdgeOut[];
  node_count: number;
  edge_count: number;
}

export interface EgoNetworkResponse {
  center: PersonNode;
  depth: number;
  nodes: PersonNode[];
  edges: NetworkEdgeOut[];
}

export interface CommunityOut {
  community_id: number;
  size: number;
  member_ids: string[];
  core_member_id: string;
  core_member_name: string;
  internal_edge_count: number;
  total_shared_cases: number;
  distinct_crime_types: string[];
}

export interface HubOut {
  person_id: string;
  full_name: string;
  degree: number;
  betweenness: number;
  risk_tier?: string | null;
  prior_case_count: number;
}

export interface PathHop {
  person_id_a: string;
  person_id_b: string;
  shared_fir_count: number;
  fir_ids: string[];
}

export interface NetworkPathResponse {
  source: string;
  target: string;
  found: boolean;
  path: string[];
  hops: PathHop[];
}

export interface GraphStats {
  total_persons_in_network: number;
  total_edges: number;
  total_communities: number;
  largest_community_size: number;
  average_degree: number;
  total_firs: number;
  total_accused_links: number;
}

export interface RepeatOffenderOut {
  person_id: string;
  full_name: string;
  address_district: string;
  prior_case_count: number;
  distinct_crime_types: string[];
  used_weapon_ever: boolean;
  risk_tier: string;
  network_degree: number;
}

// ── Pattern Analytics ─────────────────────────────────────────────────────────
export interface HotspotCluster {
  cluster_id: number;
  point_count: number;
  centroid_lat: number;
  centroid_lon: number;
  top_district: string;
  top_crime_type: string;
  date_range: { start: string; end: string };
  districts: string[];
}

export interface HotspotResponse {
  cluster_count: number;
  noise_points: number;
  eps_km: number;
  min_points: number;
  clusters: HotspotCluster[];
}

export interface DistrictSeverityItem {
  district: string;
  state: string;
  crime_count: number;
  severity_tier: string;
  pca_score: number;
  cluster_id: number;
}

export interface DistrictSeverityResponse {
  tiers: Record<string, DistrictSeverityItem[]>;
  district_count: number;
}

export interface TrendPoint {
  period: string | number;
  count: number;
}

export interface TrendResponse {
  granularity: string;
  crime_type?: string | null;
  district?: string | null;
  series: TrendPoint[];
}

export interface EmergingItem {
  crime_type: string;
  district: string;
  state: string;
  recent_count: number;
  baseline_rate: number;
  growth_ratio: number;
  spike_label: string;
}

export interface EmergingResponse {
  recent_days: number;
  baseline_days: number;
  spikes: EmergingItem[];
}

export interface SimilarCase {
  fir_id: string;
  district: string;
  crime_type: string;
  similarity_score: number;
}

export interface SimilarCasesResponse {
  query_fir_id: string;
  similar: SimilarCase[];
}

export interface DatasetStats {
  [key: string]: number | string;
}

// ── Sociological Insights ─────────────────────────────────────────────────────
export interface DistrictListResponse {
  count: number;
  districts: string[];
}

export interface DistrictProfile {
  district: string;
  state: string;
  population?: number;
  literacy_rate?: number;
  urbanization_rate?: number;
  sex_ratio?: number;
  crime_rate_per_100k?: number;
  total_crimes?: number;
  [key: string]: unknown;
}

export interface CorrelationPair {
  indicator: string;
  crime_metric: string;
  pearson_r: number;
  p_value: number;
}

export interface CorrelationsResponse {
  district_count: number;
  pairs: CorrelationPair[];
}

export interface RankingItem {
  district: string;
  state: string;
  [key: string]: unknown;
}

export interface RankingResponse {
  sort_by: string;
  order: string;
  total: number;
  items: RankingItem[];
}

export interface ScatterPoint {
  district: string;
  state: string;
  x: number;
  y: number;
}

export interface ScatterResponse {
  indicator: string;
  crime_metric: string;
  pearson_r: number;
  points: ScatterPoint[];
}

// ── Offender Profiling ────────────────────────────────────────────────────────
export interface ModelInfo {
  model_name: string;
  algorithm: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  training_size: number;
  test_size: number;
  features: string[];
}

export interface PersonRiskProfile {
  person_id: string;
  full_name: string;
  age: number;
  gender: string;
  address_district: string;
  address_state: string;
  risk_tier: string;
  predicted_reoffend_probability_365d: number;
  prior_case_count: number;
  distinct_crime_types_count: number;
  [key: string]: unknown;
}

export interface PredictResponse {
  risk_tier: string;
  predicted_reoffend_probability_365d: number;
  [key: string]: unknown;
}

export interface RiskListResponse {
  risk_tier: string;
  count: number;
  persons: PersonRiskProfile[];
}

// ── Financial Crime ───────────────────────────────────────────────────────────
export interface AccountProfile {
  account_id: string;
  risk_tier: string;
  risk_score: number;
  total_transactions: number;
  flagged_transactions: number;
  typologies: string[];
  [key: string]: unknown;
}

export interface SuspiciousAccountsResponse {
  risk_tier: string;
  count: number;
  accounts: AccountProfile[];
}

export interface AMLPattern {
  pattern_id: string;
  typology: string;
  account_count: number;
  transaction_count: number;
  total_amount: number;
  [key: string]: unknown;
}

export interface PatternsResponse {
  count: number;
  patterns: AMLPattern[];
}

export interface FinancialPathResponse {
  source: string;
  target: string;
  found: boolean;
  path: string[];
  [key: string]: unknown;
}

export interface EvaluationResponse {
  precision: number;
  recall: number;
  f1_score: number;
  auc_roc?: number;
  [key: string]: unknown;
}

// ── Crime Forecasting ─────────────────────────────────────────────────────────
export interface ForecastSeries {
  series: string;
  last_observed_year: number;
  last_observed_value: number;
  forecast_2013: number;
  selected_model: string;
  [key: string]: unknown;
}

export interface DistrictForecastBundle {
  district: string;
  state: string;
  series: ForecastSeries[];
}

// ── Explainable AI ────────────────────────────────────────────────────────────
export interface ShapDriver {
  feature: string;
  shap_value: number;
  feature_value: unknown;
}

export interface PersonExplanation {
  person_id: string;
  full_name: string;
  risk_tier: string;
  predicted_reoffend_probability_365d: number;
  base_probability: number;
  top_drivers: ShapDriver[];
  [key: string]: unknown;
}

export interface PredictExplainResponse {
  risk_tier: string;
  predicted_reoffend_probability_365d: number;
  base_probability: number;
  top_drivers: ShapDriver[];
}

export interface MethodologyOverview {
  method: string;
  model_explained: string;
  scope: string;
  note: string;
}

export interface ModelExplainabilityInfo {
  [key: string]: unknown;
}

// ── Investigator Decision Support ─────────────────────────────────────────────
export interface CasePriority {
  fir_id: string;
  district: string;
  state: string;
  crime_type: string;
  priority_score: number;
  priority_tier: string;
  accused_ids: string[];
  status: string;
  [key: string]: unknown;
}

export interface CasePriorityListResponse {
  count: number;
  priority_tier?: string | null;
  cases: CasePriority[];
}

export interface DecisionSupportStats {
  [key: string]: number | string;
}

export interface PersonDossier {
  person_id: string;
  full_name: string;
  age: number;
  gender: string;
  address_district: string;
  address_state: string;
  cases: CasePriority[];
  network_degree: number;
  offender_risk?: PersonRiskProfile | null;
  [key: string]: unknown;
}

export interface DistrictBriefing {
  district: string;
  state: string;
  total_cases: number;
  unresolved_cases: number;
  is_hotspot: boolean;
  case_volume_percentile_rank: number;
  socioeconomic?: {
    available: boolean;
    literacy_rate?: number;
    urbanization_rate?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

// ── Chat / Conversational Interface ──────────────────────────────────────────
export interface ChatRequest {
  message: string;
  session_id?: string | null;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  intent: string;
  entities: Record<string, string | null>;
  downstream_service?: string | null;
  downstream_status?: number | null;
  data?: unknown;
}

export interface TurnOut {
  role: 'user' | 'assistant';
  text: string;
  intent?: string;
  timestamp: string;
}

export interface SessionHistoryResponse {
  session_id: string;
  last_person_id?: string | null;
  last_district?: string | null;
  history: TurnOut[];
}

export interface CapabilitiesResponse {
  description: string;
  supported_intents: Record<string, string>;
  note: string;
}
