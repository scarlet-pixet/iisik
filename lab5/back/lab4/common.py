import hashlib
import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from back.lab3.common import Database, DomainError


class WritableDatabase(Database):
    """A service owns one writable PostgreSQL connection, never another DB."""

    def connect(self):
        return psycopg.connect(
            self.dsn, row_factory=dict_row, connect_timeout=5,
            options='-c statement_timeout=5000',
        )


def required_text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DomainError('BAD_INPUT', f'{label}: требуется строка от 1 до {maximum} символов')
    return value.strip()


def command(conn, *, actor, name, key, payload, perform):
    """Execute one idempotent command in the same transaction as its receipt."""
    key = required_text(key, 'idempotencyKey', 128)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    # Serialize concurrent requests for one actor/command/key before checking the receipt.
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                 (f'{actor.id}:{name}:{key}',))
    row = conn.execute(
        'SELECT request_hash,response FROM command_receipts '
        'WHERE actor_id=%s AND command=%s AND idempotency_key=%s FOR UPDATE',
        (actor.id, name, key),
    ).fetchone()
    if row:
        if row['request_hash'] != digest:
            raise DomainError('CONFLICT', 'Ключ идемпотентности уже использован с другим содержимым')
        return row['response']['id']
    result_id = perform(conn)
    conn.execute(
        'INSERT INTO command_receipts '
        '(id,actor_id,command,idempotency_key,request_hash,response,created_at) '
        'VALUES (%s,%s,%s,%s,%s,%s::jsonb,now())',
        (str(uuid4()), actor.id, name, key, digest, json.dumps({'id': result_id})),
    )
    return result_id


def require_role(actor, *roles):
    if not actor.is_active or actor.role not in roles:
        raise DomainError('FORBIDDEN', 'Недостаточно прав для бизнес-операции')
