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
  radius_km: number;
  top_district: string;
  crime_type_breakdown: Record<string, number>;
  sample_fir_ids: string[];
  geo_precise_fraction: number;
}

export interface HotspotResponse {
  filters: Record<string, unknown>;
  eps_km: number;
  min_points: number;
  total_points_considered: number;
  noise_points: number;
  clusters: HotspotCluster[];
}

export interface DistrictSeverityItem {
  district: string;
  state: string;
  total_crimes: number;
  violent_crime_ratio: number;
  property_crime_ratio: number;
  avg_property_value_inr: number;
  crime_type_diversity: number;
  unresolved_ratio: number;
  severity_tier: string;
  pca_x: number;
  pca_y: number;
}

export interface DistrictSeverityResponse {
  min_crimes_threshold: number;
  districts_included: number;
  tiers: DistrictSeverityItem[];
}

export interface TrendPoint {
  bucket: string;
  count: number;
}

export interface TrendResponse {
  granularity: string;
  filters: Record<string, unknown>;
  points: TrendPoint[];
}

export interface EmergingItem {
  district: string;
  state: string;
  crime_type_code: string;
  recent_count: number;
  baseline_count: number;
  recent_period_days: number;
  baseline_period_days: number;
  pct_change: number | null;
  flagged_reason: string;
}

export interface EmergingResponse {
  recent_window_days: number;
  baseline_window_days: number;
  min_recent_count: number;
  alerts: EmergingItem[];
}

export interface SimilarCase {
  fir_id: string;
  similarity: number;
  crime_type_code: string;
  district: string;
  state: string;
  date_occurred: string;
  status: string;
  matching_features: string[];
}

export interface SimilarCasesResponse {
  source_fir_id: string;
  source_crime_type: string;
  top_n: number;
  results: SimilarCase[];
}

// Pattern Analytics' DatasetStats - see also the differently-shaped
// DatasetStats variants for financial-crime / crime-forecasting below;
// each service defines its own even though the frontend historically
// treated them as interchangeable via index signature. Kept separate now.
export interface PatternDatasetStats {
  total_firs: number;
  date_range_start: string;
  date_range_end: string;
  distinct_districts: number;
  distinct_crime_types: number;
  crime_type_counts: Record<string, number>;
}

// ── Sociological Insights ─────────────────────────────────────────────────────
export interface DistrictSummary {
  state: string;
  district: string;
  match_type: string;
  population: number;
  crime_rate_per_100k: number | null;
}

export interface DistrictListResponse {
  total_census_districts: number;
  matched_districts: number;
  match_rate: number;
  districts: DistrictSummary[];
}

export interface DistrictProfile {
  state: string;
  district: string;
  fir_district_label: string;
  match_type: string;
  match_score: number;
  population: number;
  literacy_rate: number;
  urbanization_rate: number;
  workforce_participation_rate: number;
  higher_education_rate: number;
  amenity_index: number;
  sc_st_share: number;
  hindu_share: number;
  muslim_share: number;
  christian_share: number;
  sikh_share: number;
  total_crimes: number;
  violent_crimes: number;
  property_crimes: number;
  violent_ratio: number;
  property_ratio: number;
  crime_rate_per_100k: number;
  violent_crime_rate_per_100k: number;
  property_crime_rate_per_100k: number;
}

export interface CorrelationResult {
  indicator: string;
  crime_metric: string;
  pearson_r: number;
  p_value: number;
  n: number;
  interpretation: string;
}

export interface CorrelationsResponse {
  districts_included: number;
  indicators_used: string[];
  crime_metrics_used: string[];
  excluded_fields_note: string;
  results: CorrelationResult[];
}

export interface RankingEntry {
  state: string;
  district: string;
  value: number;
  population: number;
  crime_rate_per_100k: number;
}

export interface RankingResponse {
  sort_by: string;
  order: string;
  limit: number;
  districts: RankingEntry[];
}

export interface ScatterPoint {
  state: string;
  district: string;
  x: number;
  y: number;
  population: number;
}

export interface ScatterResponse {
  indicator: string;
  crime_metric: string;
  points: ScatterPoint[];
}

// ── Offender Profiling ────────────────────────────────────────────────────────
export interface ModelComparisonEntry {
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
}

export interface ModelInfo {
  follow_up_days: number;
  dataset_max_date: string;
  eligibility_cutoff_date: string;
  total_case_appearances: number;
  eligible_case_appearances: number;
  censored_case_appearances: number;
  positive_rate: number;
  train_appearances: number;
  test_appearances: number;
  train_persons: number;
  test_persons: number;
  selected_model: string;
  model_comparison: Record<string, ModelComparisonEntry>;
  feature_importances: Record<string, number>;
  risk_tier_thresholds: Record<string, number>;
  risk_tier_counts: Record<string, number>;
  total_accused_persons_scored: number;
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
export interface FinancialDatasetStats {
  total_accounts: number;
  total_transactions: number;
  ground_truth_laundering_accounts: number;
  ground_truth_laundering_transactions: number;
  risk_tier_counts: Record<string, number>;
  thresholds: Record<string, unknown>;
}

export interface AccountProfile {
  account_id: string;
  bank_name: string | null;
  entity_id: string | null;
  entity_name: string | null;
  out_amount: number;
  out_count: number;
  out_degree: number;
  in_amount: number;
  in_count: number;
  in_degree: number;
  distinct_currencies: number;
  max_single_txn: number;
  laundering_txn_count: number;
  ground_truth_laundering: boolean;
  flag_high_fan_out: boolean;
  flag_high_fan_in: boolean;
  flag_rapid_passthrough: boolean;
  flag_cross_currency: boolean;
  flag_high_value_txn: boolean;
  risk_score: number;
  risk_tier: string;
}

export interface SuspiciousAccountsResponse {
  risk_tier: string;
  count: number;
  accounts: AccountProfile[];
}

export interface PatternTransaction {
  timestamp: string;
  from_bank: string;
  from_account: string;
  to_bank: string;
  to_account: string;
  amount_received: number;
  receiving_currency: string;
  amount_paid: number;
  payment_currency: string;
  payment_format: string;
  is_laundering: number;
}

export interface AMLPattern {
  pattern_id: string;
  typology: string;
  descriptor: string;
  n_transactions: number;
  accounts_involved: string[];
  transactions: PatternTransaction[];
}

export interface PatternsResponse {
  typologies: string[];
  total_patterns: number;
  patterns: AMLPattern[];
}

export interface FinancialEdgeOut {
  from_id: string;
  to_id: string;
  shared_txn_count: number;
  total_amount_paid: number;
  laundering_txn_count: number;
}

export interface FinancialPathResponse {
  source: string;
  target: string;
  found: boolean;
  path: string[];
  hops: FinancialEdgeOut[];
}

export interface PRFResult {
  flagged_accounts: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface EvaluationResponse {
  ground_truth_laundering_accounts: number;
  total_accounts: number;
  total_transactions: number;
  ground_truth_laundering_transactions: number;
  thresholds: Record<string, unknown>;
  high_only: PRFResult;
  medium_or_high: PRFResult;
}

// ── Crime Forecasting ─────────────────────────────────────────────────────────
export interface ForecastDatasetStats {
  total_ncrb_districts: number;
  districts_with_complete_2001_2012_history: number;
  districts_excluded_incomplete_history: number;
  series_forecast: number;
  train_years: number[];
  test_years: number[];
  forecast_years: number[];
  model_win_counts: Record<string, number>;
  series_where_naive_was_beaten: number;
  series_where_naive_was_beaten_pct: number;
  mean_backtest_mae_by_model: Record<string, number>;
}

export interface ForecastSeries {
  series: string;
  selected_model: string;
  backtest_mae: number;
  backtest_mape: number | null;
  naive_backtest_mae: number;
  linear_trend_backtest_mae: number;
  moving_average_backtest_mae: number;
  last_observed_year: number;
  last_observed_value: number;
  forecast_2013: number;
  forecast_2014: number;
  forecast_2015: number;
}

export interface DistrictForecastBundle {
  state: string;
  district: string;
  series: ForecastSeries[];
}

export interface ForecastRankingEntry {
  state: string;
  district: string;
  last_observed_value: number;
  forecast_2015: number;
  pct_change: number | null;
  selected_model: string;
  backtest_mae: number;
}

export interface ForecastRankingResponse {
  series: string;
  order: string;
  limit: number;
  districts: ForecastRankingEntry[];
}

// ── Explainable AI ────────────────────────────────────────────────────────────
export interface FeatureContribution {
  feature: string;
  feature_value: number;
  shap_value: number;
}

export interface PersonExplanation {
  person_id: string;
  full_name: string | null;
  risk_tier: string;
  predicted_reoffend_probability_365d: number;
  base_value: number;
  reconstruction_error: number;
  top_drivers: FeatureContribution[];
  all_contributions: FeatureContribution[];
}

export interface PredictExplainResponse {
  predicted_reoffend_probability_365d: number;
  risk_tier: string;
  base_value: number;
  top_drivers: FeatureContribution[];
  all_contributions: FeatureContribution[];
  inputs: Record<string, unknown>;
}

export interface MethodologyEntry {
  service: string;
  approach: string;
  transparency_mechanism: string;
}

export interface MethodologyOverview {
  summary: string;
  pillars: MethodologyEntry[];
}

export interface ConcordanceInfo {
  metric: string;
  value: number;
  note: string;
}

export interface ModelExplainabilityInfo {
  method: string;
  base_value: number;
  mean_abs_shap_by_feature: Record<string, number>;
  top_5_drivers: string[];
  concordance_with_rf_builtin_importance: ConcordanceInfo;
  total_persons_explained: number;
  max_reconstruction_error: number;
}

// ── Investigator Decision Support ─────────────────────────────────────────────
export interface CasePriority {
  fir_id: string;
  state: string;
  district: string;
  crime_type_code: string;
  status: string;
  date_reported: string;
  age_days: number;
  violent_points: number;
  accused_risk_points: number;
  hotspot_points: number;
  stale_points: number;
  priority_score: number;
  priority_tier: string;
  highest_accused_risk_tier: string | null;
}

export interface CasePriorityListResponse {
  priority_tier: string | null;
  count: number;
  cases: CasePriority[];
}

export interface DecisionSupportStats {
  total_cases: number;
  total_unresolved_cases: number;
  priority_tier_counts: Record<string, number>;
  priority_tier_thresholds: Record<string, number>;
  stale_case_days_threshold: number;
  stale_unresolved_case_count: number;
  dataset_reference_date: string;
}

export interface OffenderRiskSummary {
  prior_case_count: number;
  distinct_crime_types_count: number;
  predicted_reoffend_probability_365d: number;
  risk_tier: string;
}

export interface Associate {
  person_id: string;
  full_name: string | null;
  shared_fir_count: number;
}

export interface CaseAppearance {
  fir_id: string;
  role: string;
  crime_type_code: string;
  date_reported: string;
  status: string;
  district: string;
}

export interface PersonDossier {
  person_id: string;
  full_name: string | null;
  gender: string | null;
  age: number | null;
  address_district: string | null;
  address_state: string | null;
  offender_risk: OffenderRiskSummary | null;
  network_degree: number;
  top_associates: Associate[];
  cases: CaseAppearance[];
}

export interface SocioeconomicContext {
  available: boolean;
  literacy_rate?: number | null;
  urbanization_rate?: number | null;
  crime_rate_per_100k?: number | null;
}

export interface ForecastContext {
  available: boolean;
  last_observed_year?: number | null;
  last_observed_value?: number | null;
  forecast_2015?: number | null;
  pct_change?: number | null;
  selected_model?: string | null;
}

export interface DistrictBriefing {
  state: string;
  district: string;
  total_cases: number;
  unresolved_cases: number;
  violent_ratio: number;
  property_ratio: number;
  case_volume_percentile_rank: number;
  is_hotspot: boolean;
  socioeconomic: SocioeconomicContext;
  forecast: ForecastContext;
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
