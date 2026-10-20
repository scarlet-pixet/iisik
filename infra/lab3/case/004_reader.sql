CREATE ROLE bank_case_reader LOGIN PASSWORD 'lab3_read_only';
REVOKE CONNECT ON DATABASE bank_case FROM PUBLIC;
GRANT CONNECT ON DATABASE bank_case TO bank_case_reader;
GRANT USAGE ON SCHEMA public TO bank_case_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bank_case_reader;
ALTER ROLE bank_case_reader SET default_transaction_read_only = on;
