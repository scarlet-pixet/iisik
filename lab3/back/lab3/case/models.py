from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True, kw_only=True)
class Comment:
    id:str
    author_id:str
    kind:str
    text:str
    created_at:datetime

@dataclass(frozen=True, kw_only=True)
class Decision:
    id:str
    author_id:str
    review_cycle:int
    outcome:str
    reason:str
    decided_at:datetime

@dataclass(frozen=True, kw_only=True)
class Case:
    id:str
    transaction_id:str
    client_id:str
    latest_result_id:str
    latest_score:int
    status:str
    priority:str
    assignee_id:str|None
    review_cycle:int
    row_version:int
    comments:list[Comment]=field(default_factory=list)
    decisions:list[Decision]=field(default_factory=list)

@dataclass(frozen=True, kw_only=True)
class Report:
    id:str
    period_start:datetime
    period_end:datetime
    filters:Any
    snapshot:Any
    created_at:datetime

@dataclass(frozen=True, kw_only=True)
class Notification:
    id:str
    case_id:str|None
    type:str
    created_at:datetime
    read_at:datetime|None
