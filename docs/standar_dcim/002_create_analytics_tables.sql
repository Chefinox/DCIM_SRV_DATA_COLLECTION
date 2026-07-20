-- ============================================================================
-- DCIM Analytics & AI Engine - Complete Schema Setup
-- Migration: 002_create_analytics_tables.sql
-- ⚠️  RUN BY: analytics_user (schema owner)
-- Purpose: Create all analytics tables + grant permissions to ai_team
-- ============================================================================

-- ============================================================================
-- 1. ANOMALY EVENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.anomaly_events (
    anomaly_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    ci_id UUID,
    asset_id UUID,
    detection_method VARCHAR(50) NOT NULL,
    current_value DOUBLE PRECISION NOT NULL,
    expected_min DOUBLE PRECISION,
    expected_max DOUBLE PRECISION,
    anomaly_score DECIMAL(5,4) NOT NULL CHECK (anomaly_score >= 0 AND anomaly_score <= 1),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT,
    possible_causes JSONB DEFAULT '[]'::jsonb,
    recommended_actions JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved', 'false_positive')),
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_timestamp ON anomaly_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_ci_id ON anomaly_events (ci_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomaly_events (severity, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_status ON anomaly_events (status, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_metric_name ON anomaly_events (metric_name, timestamp DESC);

-- ============================================================================
-- 2. PREDICTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ci_id UUID NOT NULL,
    asset_id UUID,
    prediction_type VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    model_version VARCHAR(20),
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prediction_window VARCHAR(20) NOT NULL,
    failure_probability DECIMAL(5,4) CHECK (failure_probability >= 0 AND failure_probability <= 1),
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    contributing_factors JSONB DEFAULT '[]'::jsonb,
    recommended_actions JSONB DEFAULT '[]'::jsonb,
    maintenance_window JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'scheduled', 'completed', 'cancelled')),
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_ci_id ON predictions (ci_id, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_risk ON predictions (risk_level, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions (status, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions (model, model_version, predicted_at DESC);

-- ============================================================================
-- 3. ML MODELS REGISTRY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ml_models (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    domain VARCHAR(50),
    trained_at TIMESTAMPTZ,
    training_data_size INTEGER,
    training_duration_seconds INTEGER,
    accuracy DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall_score DECIMAL(5,4),
    f1_score DECIMAL(5,4),
    auc_roc DECIMAL(5,4),
    status VARCHAR(20) DEFAULT 'registered' CHECK (status IN ('registered', 'staging', 'production', 'archived')),
    deployed_at TIMESTAMPTZ,
    artifact_path VARCHAR(500) NOT NULL,
    artifact_size_bytes BIGINT,
    artifact_checksum VARCHAR(64),
    hyperparameters JSONB,
    features_used JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_name, model_type, version)
);

CREATE INDEX IF NOT EXISTS idx_models_name_type ON ml_models (model_name, model_type);
CREATE INDEX IF NOT EXISTS idx_models_status ON ml_models (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_models_type ON ml_models (model_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_models_domain ON ml_models (domain, created_at DESC);

-- ============================================================================
-- 4. RCA REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.rca_reports (
    rca_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id VARCHAR(100) NOT NULL,
    ci_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('reactive', 'forward', 'hybrid')),
    root_cause VARCHAR(200) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    causal_chain JSONB DEFAULT '[]'::jsonb,
    explanation TEXT,
    timeline JSONB DEFAULT '[]'::jsonb,
    correlated_events JSONB DEFAULT '[]'::jsonb,
    recommended_action TEXT,
    analysis_duration_seconds DECIMAL(8,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(incident_id)
);

CREATE INDEX IF NOT EXISTS idx_rca_incident ON rca_reports (incident_id);
CREATE INDEX IF NOT EXISTS idx_rca_ci_id ON rca_reports (ci_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rca_timestamp ON rca_reports (timestamp DESC);

-- ============================================================================
-- 5. CAPACITY FORECASTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.capacity_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type VARCHAR(50) NOT NULL,
    ci_id UUID,
    forecast_date DATE NOT NULL,
    current_usage_pct DECIMAL(5,2),
    projected_usage_pct DECIMAL(5,2),
    projected_exhaustion_date DATE,
    confidence DECIMAL(5,4),
    model VARCHAR(50) NOT NULL,
    recommendations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_capacity_resource ON capacity_forecasts (resource_type, forecast_date DESC);
CREATE INDEX IF NOT EXISTS idx_capacity_ci_id ON capacity_forecasts (ci_id, forecast_date DESC);
CREATE INDEX IF NOT EXISTS idx_capacity_exhaustion ON capacity_forecasts (projected_exhaustion_date);

-- ============================================================================
-- 6. ENERGY REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.energy_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL,
    pue DECIMAL(5,3),
    total_power_kw DECIMAL(10,2),
    it_power_kw DECIMAL(10,2),
    cooling_power_kw DECIMAL(10,2),
    cooling_efficiency DECIMAL(5,4),
    power_load_balance DECIMAL(5,4),
    carbon_intensity_gco2_kwh DECIMAL(8,2),
    recommendations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_energy_date ON energy_reports (report_date DESC);
CREATE INDEX IF NOT EXISTS idx_energy_pue ON energy_reports (pue, report_date DESC);

-- ============================================================================
-- 7. MODEL DRIFT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.model_drift_tracking (
    drift_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID REFERENCES ml_models(model_id),
    check_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drift_score DECIMAL(5,4) NOT NULL,
    metric_drifts JSONB DEFAULT '{}'::jsonb,
    threshold DECIMAL(5,4) DEFAULT 0.15,
    status VARCHAR(20) CHECK (status IN ('ok', 'warning', 'critical')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_model ON model_drift_tracking (model_id, check_date DESC);
CREATE INDEX IF NOT EXISTS idx_drift_status ON model_drift_tracking (status, check_date DESC);

-- ============================================================================
-- 8. AUDIT LOG TABLE
-- ============================================================================
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

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log (resource_type, resource_id, timestamp DESC);

-- ============================================================================
-- 9. GRANT ALL PERMISSIONS TO ai_team
-- ============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_team;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ai_team;

-- Also grant future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai_team;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO ai_team;

-- ============================================================================
-- CONTINUOUS AGGREGATES (already exist from 001, skip errors)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'metrics'
    ) THEN
        BEGIN
            CREATE MATERIALIZED VIEW IF NOT EXISTS public.metrics_hourly
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', time) AS bucket,
                metric_name,
                ci_id,
                source,
                COUNT(*) AS sample_count,
                AVG(value) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                STDDEV(value) AS stddev_value
            FROM metrics
            GROUP BY bucket, metric_name, ci_id, source
            WITH NO DATA;
        EXCEPTION WHEN OTHERS THEN NULL;
        END;

        BEGIN
            CREATE MATERIALIZED VIEW IF NOT EXISTS public.metrics_daily
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 day', time) AS bucket,
                metric_name,
                ci_id,
                source,
                COUNT(*) AS sample_count,
                AVG(value) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                STDDEV(value) AS stddev_value
            FROM metrics
            GROUP BY bucket, metric_name, ci_id, source
            WITH NO DATA;
        EXCEPTION WHEN OTHERS THEN NULL;
        END;
    END IF;
END $$;

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE public.anomaly_events IS 'Anomaly detection events with severity classification';
COMMENT ON TABLE public.predictions IS 'Predictive maintenance forecasts and failure predictions';
COMMENT ON TABLE public.ml_models IS 'ML model registry with versioning and performance tracking';
COMMENT ON TABLE public.rca_reports IS 'Root cause analysis reports with causal chains';
COMMENT ON TABLE public.capacity_forecasts IS 'Capacity forecasting reports for resource planning';
COMMENT ON TABLE public.energy_reports IS 'Energy optimization reports (PUE, cooling, power)';
COMMENT ON TABLE public.model_drift_tracking IS 'Model drift monitoring over time';
COMMENT ON TABLE public.audit_log IS 'Audit trail for all analytics operations';
