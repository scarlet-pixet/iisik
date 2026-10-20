-- Initial schema. Apply to its own database only.

BEGIN;

CREATE TABLE analysis_rules (
  id UUID PRIMARY KEY,
  code VARCHAR(40) UNIQUE NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT NOT NULL
);

COMMENT ON TABLE analysis_rules IS 'E08 Именованные проверки; SC04–05';

CREATE TABLE rule_versions (
  id UUID PRIMARY KEY,
  rule_id UUID REFERENCES analysis_rules(id) NOT NULL,
  version INTEGER NOT NULL,
  parameters JSONB NOT NULL,
  weight SMALLINT NOT NULL,
  status VARCHAR(16) NOT NULL,
  published_by UUID,
  published_at TIMESTAMPTZ,
  UNIQUE(rule_id, version),
  CHECK (version > 0 AND weight BETWEEN 0 AND 100),
  CHECK (status IN ('DRAFT','PUBLISHED')),
  CHECK (status <> 'PUBLISHED' OR (published_by IS NOT NULL AND published_at IS NOT NULL))
);

COMMENT ON TABLE rule_versions IS 'E09 Версионированные параметры; SC04–05';

COMMENT ON COLUMN rule_versions.published_by IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE analysis_runs (
  id UUID PRIMARY KEY,
  mode VARCHAR(16) NOT NULL,
  scope JSONB NOT NULL,
  cutoff TIMESTAMPTZ NOT NULL,
  status VARCHAR(16) NOT NULL,
  initiated_by UUID,
  counters JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED'))
);

COMMENT ON TABLE analysis_runs IS 'E10 Отдельные расчёты; SC03–05';

COMMENT ON COLUMN analysis_runs.initiated_by IS 'Logical external reference to Auth.users; no cross-database FK';

CREATE TABLE run_rule_versions (
  run_id UUID REFERENCES analysis_runs(id) NOT NULL,
  version_id UUID REFERENCES rule_versions(id) NOT NULL,
  PRIMARY KEY(run_id, version_id)
);

COMMENT ON TABLE run_rule_versions IS 'T02 Фиксация версий в запуске; SC04–05';

CREATE TABLE behavior_profiles (
  id UUID PRIMARY KEY,
  run_id UUID REFERENCES analysis_runs(id) NOT NULL,
  client_id UUID NOT NULL,
  currency CHAR(3) NOT NULL,
  direction VARCHAR(8) NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  cutoff_transaction_id UUID,
  ingested_before TIMESTAMPTZ NOT NULL,
  sample_size INTEGER NOT NULL,
  median_amount NUMERIC(20,4),
  mad_amount NUMERIC(20,4),
  metrics JSONB NOT NULL,
  algorithm_version VARCHAR(32) NOT NULL,
  data_status VARCHAR(20) NOT NULL,
  UNIQUE NULLS NOT DISTINCT (run_id, client_id, currency, direction, window_end, cutoff_transaction_id),
  CHECK (sample_size >= 0 AND window_start <= window_end),
  CHECK (direction IN ('IN','OUT')),
  CHECK (data_status IN ('SUFFICIENT','INSUFFICIENT')),
  UNIQUE(id, run_id)
);

COMMENT ON TABLE behavior_profiles IS 'E11 Снимки обычной активности; SC03–05, SC10';

COMMENT ON COLUMN behavior_profiles.client_id IS 'Logical external reference to Transaction.bank_clients; no cross-database FK';

COMMENT ON COLUMN behavior_profiles.cutoff_transaction_id IS 'Logical external reference to Transaction.transactions; no cross-database FK';

CREATE TABLE analysis_results (
  id UUID PRIMARY KEY,
  transaction_id UUID NOT NULL,
  run_id UUID REFERENCES analysis_runs(id) NOT NULL,
  profile_id UUID REFERENCES behavior_profiles(id),
  score SMALLINT NOT NULL,
  threshold SMALLINT NOT NULL,
  data_status VARCHAR(20) NOT NULL,
  missing_reasons JSONB NOT NULL,
  calculated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(run_id, transaction_id),
  CHECK (score BETWEEN 0 AND 100 AND threshold BETWEEN 0 AND 100),
  FOREIGN KEY(profile_id, run_id) REFERENCES behavior_profiles(id, run_id)
);

COMMENT ON TABLE analysis_results IS 'E12 Оценка одной операции в запуске; SC04–05, SC07, SC10';

COMMENT ON COLUMN analysis_results.transaction_id IS 'Logical external reference to Transaction.transactions; no cross-database FK';

CREATE TABLE rule_hits (
  id UUID PRIMARY KEY,
  result_id UUID REFERENCES analysis_results(id) NOT NULL,
  rule_version_id UUID REFERENCES rule_versions(id) NOT NULL,
  feature_value JSONB NOT NULL,
  limit_value JSONB NOT NULL,
  contribution SMALLINT NOT NULL,
  UNIQUE(result_id, rule_version_id),
  CHECK (contribution BETWEEN 0 AND 100)
);

COMMENT ON TABLE rule_hits IS 'E13 Объяснение сработавшего правила; SC04–05, SC07';

CREATE TABLE inbox_events (
  event_id UUID PRIMARY KEY,
  event_type VARCHAR(80) NOT NULL,
  consumed_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE inbox_events IS 'T03 Дедупликация входных событий; SC04';

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

COMMENT ON TABLE outbox_events IS 'T04 Надёжная публикация AnalysisCompleted; SC04–05';

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

COMMENT ON TABLE command_receipts IS 'T08 Повтор команды с тем же ключом и проверка совпадения входа; SC03–05';

CREATE INDEX ix_results_transaction ON analysis_results(transaction_id, calculated_at);

CREATE INDEX ix_profiles_client ON behavior_profiles(client_id, currency, direction, window_end);

CREATE INDEX ix_analysis_outbox_pending ON outbox_events(created_at) WHERE published_at IS NULL;

COMMIT;
