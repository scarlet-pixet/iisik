from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime

@dataclass(frozen=True, kw_only=True)
class Account:
    id: str
    client_id: str
    external_id: str
    currency: str
    status: str

@dataclass(frozen=True, kw_only=True)
class Client:
    id: str
    external_id: str
    display_name: str
    segment: str | None
    is_active: bool
    accounts: list[Account] = field(default_factory=list)

@dataclass(frozen=True, kw_only=True)
class Transaction:
    id: str
    external_id: str
    source: str
    client_id: str
    account_id: str
    counterparty_id: str | None
    amount: Decimal
    currency: str
    direction: str
    occurred_at: datetime
    ingested_at: datetime
