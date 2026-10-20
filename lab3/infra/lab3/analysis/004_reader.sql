CREATE ROLE bank_analysis_reader LOGIN PASSWORD 'lab3_read_only';
REVOKE CONNECT ON DATABASE bank_analysis FROM PUBLIC;
GRANT CONNECT ON DATABASE bank_analysis TO bank_analysis_reader;
GRANT USAGE ON SCHEMA public TO bank_analysis_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bank_analysis_reader;
ALTER ROLE bank_analysis_reader SET default_transaction_read_only = on;
