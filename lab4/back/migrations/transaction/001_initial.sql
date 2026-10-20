-- Initial schema. Apply to its own database only.

BEGIN;

CREATE TABLE bank_clients (
  id UUID PRIMARY KEY,
  external_id VARCHAR(64) UNIQUE NOT NULL,
  display_name VARCHAR(160) NOT NULL,
  segment VARCHAR(50),
  is_active BOOLEAN NOT NULL
);

COMMENT ON TABLE bank_clients IS 'E03 Клиенты — объекты анализа; SC02–05, SC10';

CREATE TABLE accounts (
  id UUID PRIMARY KEY,
  client_id UUID REFERENCES bank_clients(id) NOT NULL,
  external_id VARCHAR(64) UNIQUE NOT NULL,
  currency CHAR(3) NOT NULL,
  status VARCHAR(16) NOT NULL,
  CHECK (currency ~ '^[A-Z]{3}$'),
  CHECK (status IN ('OPEN','CLOSED')),
  UNIQUE(id, currency)
);

COMMENT ON TABLE accounts IS 'E04 Счета клиентов; SC02–05, SC10';

CREATE TABLE counterparties (
  id UUID PRIMARY KEY,
  external_id VARCHAR(64) UNIQUE NOT NULL,
  display_name VARCHAR(160) NOT NULL,
  category VARCHAR(50)
);

COMMENT ON TABLE counterparties IS 'E05 Отправители и получатели; SC02, SC04, SC10';

CREATE TABLE import_batches (
  id UUID PRIMARY KEY,
  file_hash CHAR(64) UNIQUE NOT NULL,
  status VARCHAR(16) NOT NULL,
  received_count INTEGER NOT NULL,
  new_count INTEGER NOT NULL,
  duplicate_count INTEGER NOT NULL,
  validation_errors JSONB NOT NULL,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CHECK (status IN ('ACCEPTED','REJECTED')),
  CHECK (received_count >= 0 AND new_count >= 0 AND duplicate_count >= 0),
  CHECK (file_hash ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE import_batches IS 'E06 Проверка и итог импорта; SC02';

COMMENT ON COLUMN import_batches.created_by IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE transactions (
  id UUID PRIMARY KEY,
  source VARCHAR(32) NOT NULL,
  external_id VARCHAR(100) NOT NULL,
  account_id UUID REFERENCES accounts(id) NOT NULL,
  counterparty_id UUID REFERENCES counterparties(id),
  batch_id UUID REFERENCES import_batches(id),
  amount NUMERIC(18,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  direction VARCHAR(8) NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL,
  UNIQUE(source, external_id),
  CHECK (amount > 0),
  CHECK (direction IN ('IN','OUT')),
  CHECK (currency ~ '^[A-Z]{3}$'),
  FOREIGN KEY(account_id, currency) REFERENCES accounts(id, currency)
);

COMMENT ON TABLE transactions IS 'E07 Операции учебного источника; SC02–05, SC10';

CREATE TABLE outbox_events (
  id UUID PRIMARY KEY,
  aggregate_id UUID NOT NULL,
  event_type VARCHAR(80) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  published_at TIMESTAMPTZ,
  attempts INTEGER NOT NULL,
  CHECK (attempts >= 0)
);

COMMENT ON TABLE outbox_events IS 'T01 Надёжная публикация TransactionRegistered; SC02, SC04';

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

COMMENT ON TABLE command_receipts IS 'T07 Повтор команды с тем же ключом и проверка совпадения входа; SC02';

CREATE INDEX ix_transactions_history ON transactions(account_id, occurred_at, id);

CREATE INDEX ix_outbox_pending ON outbox_events(created_at) WHERE published_at IS NULL;

COMMIT;
