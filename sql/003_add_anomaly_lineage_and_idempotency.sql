-- =============================================================================
-- Migration 003: Anomaly Lineage and Idempotency Columns (ST-316 / ST-318)
-- =============================================================================
-- Tanggal: 2026-08-04
-- Author: Imam Syauqi Achmad (DBA / Ingestion Team)
-- Database: dcim_analytics
-- Target Table: public.anomaly_events
-- =============================================================================

BEGIN;

-- 1) Tambah Kolom Lineage & Tracking pada anomaly_events
ALTER TABLE public.anomaly_events
    ADD COLUMN IF NOT EXISTS correlation_id UUID,
    ADD COLUMN IF NOT EXISTS dedup_key TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS event_state VARCHAR(20) DEFAULT 'anomaly',
    ADD COLUMN IF NOT EXISTS source_event_id UUID,
    ADD COLUMN IF NOT EXISTS test_run_id UUID,
    ADD COLUMN IF NOT EXISTS scenario_id VARCHAR(100);

-- 2) Index Dedup Key untuk Query Idempotensi Cepat
CREATE INDEX IF NOT EXISTS idx_anomaly_dedup_key 
    ON public.anomaly_events (dedup_key);

-- 3) Index Lineage Tracing
CREATE INDEX IF NOT EXISTS idx_anomaly_correlation_id 
    ON public.anomaly_events (correlation_id);

COMMIT;
