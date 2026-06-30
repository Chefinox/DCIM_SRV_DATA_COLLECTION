-- PostgreSQL: dcim_sot database
CREATE TABLE IF NOT EXISTS event_lineage (
    lineage_id UUID PRIMARY KEY,
    event_id TEXT NOT NULL,
    source_system VARCHAR(100),
    
    -- Ingestion
    ingested_at TIMESTAMPTZ,
    
    -- Validation (Normalization)
    validation_status VARCHAR(20),
    validated_at TIMESTAMPTZ,
    validation_error TEXT,
    
    -- Enrichment
    enrichment_status VARCHAR(20),
    enriched_at TIMESTAMPTZ,
    enrichment_error TEXT,
    
    -- Routing
    routing_status VARCHAR(20),
    routed_at TIMESTAMPTZ,
    target_store VARCHAR(50),
    target_id VARCHAR(100),
    
    -- Metrics
    processing_ms_total INTEGER
);

CREATE INDEX IF NOT EXISTS idx_lineage_event_id ON event_lineage(event_id);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON event_lineage(source_system);
CREATE INDEX IF NOT EXISTS idx_lineage_ingested ON event_lineage(ingested_at);
CREATE INDEX IF NOT EXISTS idx_lineage_status ON event_lineage(validation_status, enrichment_status, routing_status);
