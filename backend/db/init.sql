-- Rozszerzenie pgvector dla bazy produkcyjnej i testowej.
CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE prawdowid_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'prawdowid_test')\gexec

\c prawdowid_test
CREATE EXTENSION IF NOT EXISTS vector;
