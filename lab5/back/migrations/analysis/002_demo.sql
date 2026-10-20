BEGIN;
INSERT INTO analysis_rules (id, code, name, description) VALUES ('64107af6-c93e-5010-a350-c5e42a2e413a', 'AMOUNT', 'AMOUNT', 'Учебное правило AMOUNT') ON CONFLICT DO NOTHING;
INSERT INTO rule_versions (id, rule_id, version, parameters, weight, status, published_by, published_at) VALUES ('22e19a56-c9b2-5650-865f-d8aef08d428a', '64107af6-c93e-5010-a350-c5e42a2e413a', 1, '{"multiplier": 5, "min_samples": 5}', 60, 'PUBLISHED', '43817961-b437-5313-9754-19535c80b1b9', '2026-09-30T11:00:00Z') ON CONFLICT DO NOTHING;
INSERT INTO analysis_rules (id, code, name, description) VALUES ('918aec28-31c5-5fe9-a2a7-336464efdda0', 'FREQUENCY', 'FREQUENCY', 'Учебное правило FREQUENCY') ON CONFLICT DO NOTHING;
INSERT INTO rule_versions (id, rule_id, version, parameters, weight, status, published_by, published_at) VALUES ('cbd9d23b-d75d-590f-9cc3-caf3c3c2553a', '918aec28-31c5-5fe9-a2a7-336464efdda0', 1, '{"window_minutes": 60, "limit": 5}', 25, 'PUBLISHED', '43817961-b437-5313-9754-19535c80b1b9', '2026-09-30T11:00:00Z') ON CONFLICT DO NOTHING;
INSERT INTO analysis_rules (id, code, name, description) VALUES ('89fccfd1-3be5-5d81-a879-70f08d04418c', 'NEW_COUNTERPARTY', 'NEW_COUNTERPARTY', 'Учебное правило NEW_COUNTERPARTY') ON CONFLICT DO NOTHING;
INSERT INTO rule_versions (id, rule_id, version, parameters, weight, status, published_by, published_at) VALUES ('7f84728d-b28a-5dc8-aa5d-3a054d7d1732', '89fccfd1-3be5-5d81-a879-70f08d04418c', 1, '{"min_samples": 5}', 15, 'PUBLISHED', '43817961-b437-5313-9754-19535c80b1b9', '2026-09-30T11:00:00Z') ON CONFLICT DO NOTHING;
COMMIT;
