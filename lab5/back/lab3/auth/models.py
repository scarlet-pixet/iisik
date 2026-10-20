from dataclasses import dataclass

@dataclass(frozen=True, kw_only=True)
class User:
    id: str
    login: str
    role: str
    is_active: bool
