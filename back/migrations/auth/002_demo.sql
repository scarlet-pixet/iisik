BEGIN;
INSERT INTO roles (id, code, name) VALUES ('f91ca18e-fd46-53d3-bf50-010299a37a3a', 'ADMIN', 'ADMIN') ON CONFLICT DO NOTHING;
INSERT INTO users (id, role_id, login, password_hash, is_active, created_at, disabled_at) VALUES ('b4703b75-0c9e-55cf-8ad2-bd607b00f7ed', 'f91ca18e-fd46-53d3-bf50-010299a37a3a', 'admin', 'pbkdf2_sha256$600000$98cf568e41b9bfaa3b1fa57110a18510$8cbdbec415e94db3677525ba944fad9b38d7ad5852caadce444adf5744525597', true, '2026-09-30T11:00:00Z', NULL) ON CONFLICT DO NOTHING;
INSERT INTO roles (id, code, name) VALUES ('ae7a1f33-c33d-5092-b1ed-c54e62d1e44e', 'ANALYST', 'ANALYST') ON CONFLICT DO NOTHING;
INSERT INTO users (id, role_id, login, password_hash, is_active, created_at, disabled_at) VALUES ('c7fba0b2-b5bd-59e7-b722-4f0e6c5b4c45', 'ae7a1f33-c33d-5092-b1ed-c54e62d1e44e', 'analyst', 'pbkdf2_sha256$600000$e5433707df2e770061eda9ed878d5e53$04cf395c9d21f2afe41181d79126ab80eed650427e505c18426d83c13f83c132', true, '2026-09-30T11:00:00Z', NULL) ON CONFLICT DO NOTHING;
INSERT INTO roles (id, code, name) VALUES ('d9d4e3da-4478-5b89-8b3d-97b55f2656cc', 'MANAGER', 'MANAGER') ON CONFLICT DO NOTHING;
INSERT INTO users (id, role_id, login, password_hash, is_active, created_at, disabled_at) VALUES ('43817961-b437-5313-9754-19535c80b1b9', 'd9d4e3da-4478-5b89-8b3d-97b55f2656cc', 'manager', 'pbkdf2_sha256$600000$f27254a422355e370274477353eda87f$e8f8af225b85ba112088b55453a1d8b24e31d8998ea0427cc9b4f596b94cf3c9', true, '2026-09-30T11:00:00Z', NULL) ON CONFLICT DO NOTHING;
COMMIT;
