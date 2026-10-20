from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

@dataclass(frozen=True, kw_only=True)
class Profile:
    id: str
    run_id: str
    client_id: str
    currency: str
    direction: str
    window_start: datetime
    window_end: datetime
    cutoff_transaction_id: str | None
    ingested_before: datetime
    sample_size: int
    median_amount: Decimal | None
    mad_amount: Decimal | None
    metrics: Any
    data_status: str

@dataclass(frozen=True, kw_only=True)
class RuleHit:
    rule_code: str
    version: int
    feature_value: Any
    limit_value: Any
    contribution: int

@dataclass(frozen=True, kw_only=True)
class Result:
    id: str
    transaction_id: str
    run_id: str
    profile_id: str | None
    score: int
    threshold: int
    data_status: str
    missing_reasons: list[str]
    calculated_at: datetime
    hits: list[RuleHit] = field(default_factory=list)

@dataclass(frozen=True, kw_only=True)
class Run:
    id: str
    mode: str
    status: str
    counters: Any
    created_at: datetime
    completed_at: datetime | None

@dataclass(frozen=True, kw_only=True)
class RuleVersion:
    id: str
    rule_id: str
    version: int
    weight: int
    parameters: Any
    status: str
    published_at: datetime | None
