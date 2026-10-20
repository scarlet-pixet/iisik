CREATE ROLE bank_auth_reader LOGIN PASSWORD 'lab3_read_only';
REVOKE CONNECT ON DATABASE bank_auth FROM PUBLIC;
GRANT CONNECT ON DATABASE bank_auth TO bank_auth_reader;
GRANT USAGE ON SCHEMA public TO bank_auth_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bank_auth_reader;
ALTER ROLE bank_auth_reader SET default_transaction_read_only = on;
