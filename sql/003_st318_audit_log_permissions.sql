-- ============================================================================
-- ST-318: Audit Database Schema & Permissions (TimescaleDB / dcim_analytics)
-- Target Database: dcim_analytics
-- Target Schema: public
-- Target Table: audit_log
-- ============================================================================

-- 1. Ensure Table Structure
CREATE TABLE IF NOT EXISTS public.audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    details JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT
);

-- 2. Ensure Required Indexes for High-Performance Querying
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON public.audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON public.audit_log (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON public.audit_log (resource_type, resource_id, timestamp DESC);

-- 3. Comments
COMMENT ON TABLE public.audit_log IS 'Audit trail for all Block 7 analytics operations (ST-318)';
COMMENT ON COLUMN public.audit_log.log_id IS 'Unique UUID for audit record';
COMMENT ON COLUMN public.audit_log.timestamp IS 'Timestamp when the action occurred';
COMMENT ON COLUMN public.audit_log.user_id IS 'Subject/User ID from JWT token or service account';
COMMENT ON COLUMN public.audit_log.action IS 'HTTP Method or action performed';
COMMENT ON COLUMN public.audit_log.resource_type IS 'Resource category (e.g. LLM_QUERY, ANOMALY, MODEL)';
COMMENT ON COLUMN public.audit_log.resource_id IS 'Specific resource identifier';
COMMENT ON COLUMN public.audit_log.details IS 'Non-sensitive metadata JSON';

-- 4. DB Permissions (Least Privilege & Verification)
DO $$
BEGIN
    -- Grant INSERT, SELECT on public.audit_log to ai_team role if exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_team') THEN
        GRANT SELECT, INSERT ON public.audit_log TO ai_team;
    END IF;
    
    -- Grant to dcim_analytics_user if exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcim_analytics_user') THEN
        GRANT SELECT, INSERT ON public.audit_log TO dcim_analytics_user;
    END IF;
END $$;
