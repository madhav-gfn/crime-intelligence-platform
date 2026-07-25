from pydantic import BaseModel


class DatasetStats(BaseModel):
    total_accounts: int
    total_transactions: int
    ground_truth_laundering_accounts: int
    ground_truth_laundering_transactions: int
    risk_tier_counts: dict[str, int]
    thresholds: dict


class AccountProfile(BaseModel):
    account_id: str
    bank_name: str | None
    entity_id: str | None
    entity_name: str | None
    out_amount: float
    out_count: int
    out_degree: int
    in_amount: float
    in_count: int
    in_degree: int
    distinct_currencies: int
    max_single_txn: float
    laundering_txn_count: int
    ground_truth_laundering: bool
    flag_high_fan_out: bool
    flag_high_fan_in: bool
    flag_rapid_passthrough: bool
    flag_cross_currency: bool
    flag_high_value_txn: bool
    risk_score: int
    risk_tier: str


class SuspiciousAccountsResponse(BaseModel):
    risk_tier: str
    count: int
    accounts: list[AccountProfile]


class PatternTransaction(BaseModel):
    timestamp: str
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_received: float
    receiving_currency: str
    amount_paid: float
    payment_currency: str
    payment_format: str
    is_laundering: int


class LaunderingPattern(BaseModel):
    pattern_id: str
    typology: str
    descriptor: str
    n_transactions: int
    accounts_involved: list[str]
    transactions: list[PatternTransaction]


class PatternsResponse(BaseModel):
    typologies: list[str]
    total_patterns: int
    patterns: list[LaunderingPattern]


class EdgeOut(BaseModel):
    from_id: str
    to_id: str
    shared_txn_count: int
    total_amount_paid: float
    laundering_txn_count: int


class PathResponse(BaseModel):
    source: str
    target: str
    found: bool
    path: list[str]
    hops: list[EdgeOut]


class PRFResult(BaseModel):
    flagged_accounts: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


class EvaluationResponse(BaseModel):
    ground_truth_laundering_accounts: int
    total_accounts: int
    total_transactions: int
    ground_truth_laundering_transactions: int
    thresholds: dict
    high_only: PRFResult
    medium_or_high: PRFResult
