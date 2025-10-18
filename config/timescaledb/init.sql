-- Heart Failure IoT Platform - TimescaleDB Schema
-- Multi-tenant time-series database for medical device telemetry
-- HIPAA-ready: No PHI in raw telemetry; pseudonymous device IDs only

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schema for tenant isolation
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS alerts;
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================================
-- TENANTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.tenants (
    tenant_id VARCHAR(64) PRIMARY KEY,
    tenant_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_key_id VARCHAR(255),  -- KMS key reference
    metadata JSONB
);

-- Seed default tenants
INSERT INTO public.tenants (tenant_id, tenant_name, metadata) VALUES
    ('clinic-alpha', 'Alpha Cardiology Clinic', '{"location": "Boston, MA", "device_count": 250}'),
    ('hospital-beta', 'Beta Regional Hospital', '{"location": "Seattle, WA", "device_count": 250}')
ON CONFLICT (tenant_id) DO NOTHING;

-- ============================================================================
-- DEVICES TABLE (Registry)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.devices (
    device_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES public.tenants(tenant_id),
    device_type VARCHAR(64) DEFAULT 'CardioMEMS_HF',
    firmware_version VARCHAR(32),
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB
);

CREATE INDEX idx_devices_tenant ON public.devices(tenant_id);
CREATE INDEX idx_devices_last_seen ON public.devices(last_seen_at DESC);

-- ============================================================================
-- TELEMETRY TABLE (Hypertable for time-series data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry.heart_failure_measurements (
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,

    -- CardioMEMS measurements (Pulmonary Artery Pressure)
    pap_systolic NUMERIC(5,2),      -- mmHg
    pap_diastolic NUMERIC(5,2),     -- mmHg
    pap_mean NUMERIC(5,2),          -- Computed or measured
    heart_rate INTEGER,             -- bpm
    signal_quality NUMERIC(3,2),    -- 0.00 to 1.00

    -- Device context
    battery_level INTEGER,          -- percentage
    temperature NUMERIC(4,2),       -- Celsius

    -- Quality flags
    is_valid BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,

    -- Metadata
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable (partition by time)
SELECT create_hypertable(
    'telemetry.heart_failure_measurements',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Create indexes for multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_telemetry_tenant_time
    ON telemetry.heart_failure_measurements (tenant_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
    ON telemetry.heart_failure_measurements (device_id, time DESC);

-- Enable compression (30-day delay)
ALTER TABLE telemetry.heart_failure_measurements
    SET (timescaledb.compress,
         timescaledb.compress_segmentby = 'device_id, tenant_id',
         timescaledb.compress_orderby = 'time DESC');

SELECT add_compression_policy('telemetry.heart_failure_measurements', INTERVAL '30 days', if_not_exists => TRUE);

-- Retention policy: keep raw data for 2 years
SELECT add_retention_policy('telemetry.heart_failure_measurements', INTERVAL '2 years', if_not_exists => TRUE);

-- ============================================================================
-- CONTINUOUS AGGREGATES (Pre-computed rollups for dashboards)
-- ============================================================================

-- Hourly rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.hourly_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    tenant_id,
    device_id,
    COUNT(*) as measurement_count,
    AVG(pap_systolic) as avg_pap_systolic,
    MAX(pap_systolic) as max_pap_systolic,
    MIN(pap_systolic) as min_pap_systolic,
    AVG(pap_diastolic) as avg_pap_diastolic,
    AVG(heart_rate) as avg_heart_rate,
    AVG(signal_quality) as avg_signal_quality
FROM telemetry.heart_failure_measurements
WHERE is_valid = TRUE
GROUP BY bucket, tenant_id, device_id;

-- Daily rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.daily_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    tenant_id,
    device_id,
    COUNT(*) as measurement_count,
    AVG(pap_systolic) as avg_pap_systolic,
    STDDEV(pap_systolic) as stddev_pap_systolic,
    AVG(pap_diastolic) as avg_pap_diastolic,
    STDDEV(pap_diastolic) as stddev_pap_diastolic,
    AVG(heart_rate) as avg_heart_rate
FROM telemetry.heart_failure_measurements
WHERE is_valid = TRUE
GROUP BY bucket, tenant_id, device_id;

-- ============================================================================
-- ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS alerts.anomaly_detections (
    time TIMESTAMPTZ NOT NULL,
    alert_id UUID DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    device_id VARCHAR(64) NOT NULL,

    alert_type VARCHAR(64) NOT NULL,  -- 'ANOMALY', 'THRESHOLD', 'DRIFT'
    severity VARCHAR(16) NOT NULL,     -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'

    anomaly_score NUMERIC(5,4),
    confidence NUMERIC(3,2),

    triggered_by JSONB,  -- Which features triggered
    context JSONB,       -- Relevant telemetry window

    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (time, alert_id)
);

SELECT create_hypertable(
    'alerts.anomaly_detections',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_alerts_tenant_time
    ON alerts.anomaly_detections (tenant_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_device_severity
    ON alerts.anomaly_detections (device_id, severity, time DESC);

-- ============================================================================
-- AUDIT LOG (HIPAA compliance)
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit.access_log (
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    log_id UUID DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64),
    user_id VARCHAR(255),
    action VARCHAR(64) NOT NULL,  -- 'READ', 'WRITE', 'DELETE', 'EXPORT'
    resource_type VARCHAR(64),
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    result VARCHAR(16),  -- 'SUCCESS', 'DENIED', 'ERROR'
    details JSONB,

    PRIMARY KEY (timestamp, log_id)
);

SELECT create_hypertable(
    'audit.access_log',
    'timestamp',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_time
    ON audit.access_log (tenant_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_user
    ON audit.access_log (user_id, timestamp DESC);

-- ============================================================================
-- ROW-LEVEL SECURITY (RLS) for multi-tenancy
-- ============================================================================

-- Enable RLS on telemetry table
ALTER TABLE telemetry.heart_failure_measurements ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tenant's data
-- Note: In production, combine with Cognito JWT claims
CREATE POLICY tenant_isolation_policy ON telemetry.heart_failure_measurements
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', TRUE));

-- Enable RLS on alerts
ALTER TABLE alerts.anomaly_detections ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_alerts ON alerts.anomaly_detections
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', TRUE));

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to compute PAP mean from systolic/diastolic
CREATE OR REPLACE FUNCTION compute_pap_mean(systolic NUMERIC, diastolic NUMERIC)
RETURNS NUMERIC AS $$
BEGIN
    RETURN ROUND((systolic + 2 * diastolic) / 3, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to validate PAP ranges
CREATE OR REPLACE FUNCTION is_valid_pap(systolic NUMERIC, diastolic NUMERIC)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN systolic BETWEEN 15 AND 100
       AND diastolic BETWEEN 5 AND 50
       AND systolic > diastolic;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- SEED DATA (for testing)
-- ============================================================================

-- Register some test devices
INSERT INTO public.devices (device_id, tenant_id, device_type, metadata) VALUES
    ('CM-ALPHA-001', 'clinic-alpha', 'CardioMEMS_HF', '{"patient_id": "PT-A-001", "implant_date": "2024-01-15"}'),
    ('CM-ALPHA-002', 'clinic-alpha', 'CardioMEMS_HF', '{"patient_id": "PT-A-002", "implant_date": "2024-02-20"}'),
    ('CM-BETA-001', 'hospital-beta', 'CardioMEMS_HF', '{"patient_id": "PT-B-001", "implant_date": "2024-01-10"}'),
    ('CM-BETA-002', 'hospital-beta', 'CardioMEMS_HF', '{"patient_id": "PT-B-002", "implant_date": "2024-03-05"}')
ON CONFLICT (device_id) DO NOTHING;

-- Grant permissions (adjust for your application user)
GRANT USAGE ON SCHEMA telemetry TO iot_admin;
GRANT USAGE ON SCHEMA alerts TO iot_admin;
GRANT USAGE ON SCHEMA audit TO iot_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA telemetry TO iot_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA alerts TO iot_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO iot_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO iot_admin;

-- ============================================================================
-- VIEWS FOR EASY QUERYING
-- ============================================================================

-- Recent telemetry with device info
CREATE OR REPLACE VIEW telemetry.recent_measurements AS
SELECT
    t.*,
    d.device_type,
    d.firmware_version,
    tn.tenant_name
FROM telemetry.heart_failure_measurements t
JOIN public.devices d ON t.device_id = d.device_id
JOIN public.tenants tn ON t.tenant_id = tn.tenant_id
WHERE t.time > NOW() - INTERVAL '24 hours'
ORDER BY t.time DESC;

-- Active alerts
CREATE OR REPLACE VIEW alerts.active_alerts AS
SELECT
    a.*,
    d.device_type,
    tn.tenant_name
FROM alerts.anomaly_detections a
JOIN public.devices d ON a.device_id = d.device_id
JOIN public.tenants tn ON a.tenant_id = tn.tenant_id
WHERE a.acknowledged = FALSE
  AND a.time > NOW() - INTERVAL '7 days'
ORDER BY a.severity DESC, a.time DESC;

-- ============================================================================
-- COMPLETE
-- ============================================================================

-- Summary
DO $$
BEGIN
    RAISE NOTICE '✅ Heart Failure IoT Database Initialized';
    RAISE NOTICE '📊 Schemas: telemetry, alerts, audit';
    RAISE NOTICE '🔐 Row-Level Security: ENABLED';
    RAISE NOTICE '📦 Compression: 30-day policy';
    RAISE NOTICE '🗑️  Retention: 2-year policy';
    RAISE NOTICE '👥 Tenants: % (seeded)', (SELECT COUNT(*) FROM public.tenants);
    RAISE NOTICE '📱 Devices: % (seeded)', (SELECT COUNT(*) FROM public.devices);
END $$;
