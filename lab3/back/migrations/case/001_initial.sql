-- Initial schema. Apply to its own database only.

BEGIN;

CREATE TABLE review_cases (
  id UUID PRIMARY KEY,
  transaction_id UUID UNIQUE NOT NULL,
  client_id UUID NOT NULL,
  initial_result_id UUID NOT NULL,
  latest_result_id UUID NOT NULL,
  latest_score SMALLINT NOT NULL,
  latest_calculated_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(16) NOT NULL,
  priority VARCHAR(12) NOT NULL,
  assignee_id UUID,
  review_cycle INTEGER NOT NULL,
  row_version INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CHECK (status IN ('NEW','ASSIGNED','IN_PROGRESS','ESCALATED','CLOSED')),
  CHECK (priority IN ('LOW','MEDIUM','HIGH')),
  CHECK (latest_score BETWEEN 0 AND 100 AND review_cycle > 0 AND row_version > 0)
);

COMMENT ON TABLE review_cases IS 'E14 Очередь и состояние рассмотрения; SC04–09';

COMMENT ON COLUMN review_cases.transaction_id IS 'Logical external reference to Transaction.transactions; no cross-database FK';

COMMENT ON COLUMN review_cases.client_id IS 'Logical external reference to Transaction.bank_clients; no cross-database FK';

COMMENT ON COLUMN review_cases.initial_result_id IS 'Logical external reference to Analysis.analysis_results; no cross-database FK';

COMMENT ON COLUMN review_cases.latest_result_id IS 'Logical external reference to Analysis.analysis_results; no cross-database FK';

COMMENT ON COLUMN review_cases.assignee_id IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE case_comments (
  id UUID PRIMARY KEY,
  case_id UUID REFERENCES review_cases(id) NOT NULL,
  author_id UUID NOT NULL,
  kind VARCHAR(20) NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CHECK (length(trim(text)) > 0)
);

COMMENT ON TABLE case_comments IS 'E15 Ход рассмотрения и эскалации; SC07–08';

COMMENT ON COLUMN case_comments.author_id IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE case_decisions (
  id UUID PRIMARY KEY,
  case_id UUID REFERENCES review_cases(id) NOT NULL,
  author_id UUID NOT NULL,
  review_cycle INTEGER NOT NULL,
  outcome VARCHAR(32) NOT NULL,
  reason TEXT NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL,
  UNIQUE(case_id, review_cycle),
  CHECK (outcome IN ('UNUSUAL_CONFIRMED','EXPLAINED')),
  CHECK (length(trim(reason)) > 0 AND review_cycle > 0)
);

COMMENT ON TABLE case_decisions IS 'E16 Итоги циклов рассмотрения; SC08–09';

COMMENT ON COLUMN case_decisions.author_id IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE reports (
  id UUID PRIMARY KEY,
  author_id UUID NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  filters JSONB NOT NULL,
  snapshot JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CHECK (period_start < period_end)
);

COMMENT ON TABLE reports IS 'E17 Снимки сформированных отчётов; SC09';

COMMENT ON COLUMN reports.author_id IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE notifications (
  id UUID PRIMARY KEY,
  case_id UUID REFERENCES review_cases(id),
  recipient_id UUID NOT NULL,
  type VARCHAR(40) NOT NULL,
  source_event_id UUID NOT NULL,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(recipient_id, source_event_id, type)
);

COMMENT ON TABLE notifications IS 'E18 Адресные уведомления; SC05–09';

COMMENT ON COLUMN notifications.recipient_id IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE inbox_events (
  event_id UUID PRIMARY KEY,
  event_type VARCHAR(80) NOT NULL,
  consumed_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE inbox_events IS 'T05 Дедупликация AnalysisCompleted; SC04–05';

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

COMMENT ON TABLE command_receipts IS 'T09 Повтор команды с тем же ключом и проверка совпадения входа; SC06, SC08–09';

CREATE INDEX ix_cases_queue ON review_cases(status, priority, created_at);

CREATE INDEX ix_cases_assignee ON review_cases(assignee_id,status);

CREATE INDEX ix_notifications_unread ON notifications(recipient_id,read_at);

COMMIT;
