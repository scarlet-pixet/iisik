-- Initial schema. Apply to its own database only.

BEGIN;

CREATE TABLE roles (
  id UUID PRIMARY KEY,
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(80) NOT NULL
);

COMMENT ON TABLE roles IS 'E02 Три роли и их коды; SC01';

CREATE TABLE users (
  id UUID PRIMARY KEY,
  role_id UUID REFERENCES roles(id) NOT NULL,
  login VARCHAR(128) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  disabled_at TIMESTAMPTZ,
  CHECK ((is_active AND disabled_at IS NULL) OR (NOT is_active AND disabled_at IS NOT NULL))
);

COMMENT ON TABLE users IS 'E01 Учётные записи сотрудников; SC01, SC06–09';

CREATE TABLE command_receipts (
  id UUID PRIMARY KEY,
  actor_id UUID NOT NULL,
  command VARCHAR(64) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(actor_id, command, idempotency_key)
);

COMMENT ON TABLE command_receipts IS 'T06 Повтор команды с тем же ключом и проверка совпадения входа; SC01';

COMMIT;
