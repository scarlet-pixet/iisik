CREATE ROLE bank_transaction_reader LOGIN PASSWORD 'lab3_read_only';
REVOKE CONNECT ON DATABASE bank_transaction FROM PUBLIC;
GRANT CONNECT ON DATABASE bank_transaction TO bank_transaction_reader;
GRANT USAGE ON SCHEMA public TO bank_transaction_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bank_transaction_reader;
ALTER ROLE bank_transaction_reader SET default_transaction_read_only = on;
