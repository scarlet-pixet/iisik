from __future__ import annotations
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
import base64, json, re
import psycopg
from psycopg.rows import dict_row

class DomainError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

def uuid(value):
    try: return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise DomainError('BAD_INPUT', 'Идентификатор должен быть UUID') from None

def period(value):
    try:
        start, end = value['from'], value['to']
        start = datetime.fromisoformat(start.replace('Z', '+00:00')) if isinstance(start, str) else start
        end = datetime.fromisoformat(end.replace('Z', '+00:00')) if isinstance(end, str) else end
        if not start.tzinfo or not end.tzinfo or start >= end: raise ValueError()
        return start, end
    except (KeyError, ValueError, TypeError, AttributeError):
        raise DomainError('BAD_INPUT', 'Период требует from < to и часовой пояс') from None

def currency(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Z]{3}', value):
        raise DomainError('BAD_INPUT', 'Валюта задаётся тремя заглавными латинскими буквами')
    return value

def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0: raise ValueError()
        return result
    except (ValueError, InvalidOperation): raise DomainError('BAD_INPUT', 'Некорректная граница суммы') from None

def model(cls, row, **extra):
    if row is None: return None
    values = {k: str(v) if isinstance(v, UUID) else v for k, v in row.items()}
    values.update(extra)
    return cls(**{f.name: values[f.name] for f in fields(cls) if f.name in values})

@dataclass(frozen=True)
class Page:
    limit: int
    offset: int
    sort: str
    direction: str

def pagination(value, allowed, default):
    value = value or {}
    limit = value.get('limit', 20)
    sort = value.get('sortBy') or default
    direction = value.get('sortDirection') or 'ASC'
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise DomainError('BAD_INPUT', 'limit должен быть от 1 до 100')
    if sort not in allowed or direction not in ('ASC', 'DESC'):
        raise DomainError('BAD_INPUT', 'Недопустимое поле или направление сортировки')
    offset = 0
    if value.get('cursor'):
        try:
            parsed = json.loads(base64.b64decode(value['cursor'], validate=True))
            offset = parsed['offset']
            if type(offset) is not int or not 0 <= offset <= 1000000 or parsed['sort'] != sort or parsed['direction'] != direction: raise ValueError()
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            raise DomainError('BAD_INPUT', 'Некорректный курсор или изменена сортировка') from None
    return Page(limit, offset, allowed[sort], direction)

def paged(items, total, page, source):
    source = source or {}
    cursor = None
    if page.offset + len(items) < total:
        cursor = base64.b64encode(json.dumps({'offset': page.offset + len(items), 'sort': source.get('sortBy') or {'display_name':'displayName','occurred_at':'occurredAt','created_at':'createdAt'}.get(page.sort,page.sort), 'direction':page.direction}).encode()).decode()
    return {'items':items, 'totalCount':total, 'nextCursor':cursor}

class Database:
    """Only a repository receives its owner's database handle."""
    def __init__(self, dsn: str, owner: str): self.dsn, self.owner = dsn, owner
    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5,
            options='-c default_transaction_read_only=on -c statement_timeout=5000')
    def query(self, sql, params=()):
        try:
            with self.connect() as conn: return conn.execute(sql, params).fetchall()
        except psycopg.OperationalError:
            raise DomainError('DEPENDENCY_UNAVAILABLE', f'База {self.owner} недоступна') from None
    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None
    def health(self):
        return self.one("SELECT current_database() AS database, current_user AS user, count(*)::int AS tables FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")

class Repository:
    def __init__(self, db: Database): self.db = db
    def page_rows(self, select, clauses, params, page):
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        # select/clauses originate in repositories; all user values remain parameters.
        with self.db.connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            total = conn.execute('SELECT count(*)::int AS n FROM ('+select+where+') q', params).fetchone()['n']
            rows = conn.execute('SELECT * FROM ('+select+where+') q ORDER BY '+page.sort+' '+page.direction+', id '+page.direction+' LIMIT %s OFFSET %s', [*params,page.limit,page.offset]).fetchall()
        return rows, total
