-- Synthetic read fixtures, not results computed by LR3.
BEGIN;
INSERT INTO bank_clients (id, external_id, display_name, segment, is_active) VALUES ('e18fb698-c300-5dd6-a11d-9d4a0afbba4c', 'SYNTH-EMPTY', 'Клиент без операций', 'RETAIL', true) ON CONFLICT DO NOTHING;
INSERT INTO accounts (id, client_id, external_id, currency, status) VALUES ('58983bcd-04c3-5e08-825d-ae655b36d4ab', 'e18fb698-c300-5dd6-a11d-9d4a0afbba4c', 'EMPTY-USD-001', 'USD', 'OPEN') ON CONFLICT DO NOTHING;
INSERT INTO transactions (id, source, external_id, account_id, counterparty_id, batch_id, amount, currency, direction, occurred_at, ingested_at) VALUES ('6cc2afed-690b-527f-9d0c-293f4f7f8d96', 'lab3_fixture', 'LR3-5000', '61a7e4b0-fb59-56a8-aa69-b24a5340ca8d', '5dc118ce-a9b6-52e3-80b8-e5531d6c5206', NULL, 5000, 'BYN', 'OUT', '2026-09-30T12:00:00Z', '2026-09-30T12:00:00Z') ON CONFLICT DO NOTHING;
COMMIT;
