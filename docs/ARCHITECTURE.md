# Architecture Documentation

## System Overview

The Heart Failure IoT Platform is a multi-tenant, cloud-native system for monitoring implanted cardiac devices (CardioMEMS HF) and detecting early signs of heart failure decompensation.

## Design Principles

1. **Multi-Tenancy First**: Strict isolation at every layer
2. **HIPAA Compliance**: No PHI in telemetry streams
3. **Scalability**: Design for 1M+ devices
4. **Local-First Development**: Full stack runs on laptop
5. **Cloud-Ready**: Production path to AWS IoT Core

## Components

### 1. Device Simulator
- Generates realistic CardioMEMS telemetry
- 500 virtual devices (250 per tenant)
- Physiological PAP patterns with noise
- 5% anomaly injection rate

### 2. MQTT Broker (EMQX)
- Local replacement for AWS IoT Core
- Topic structure: `tenants/{tenantId}/devices/{deviceId}/telemetry`
- No authentication in dev (JWT in prod)

### 3. Router Service
- Subscribes to all telemetry topics
- Validates message schema
- Stores in TimescaleDB
- Invokes ML service for scoring
- Mimics AWS IoT Rules Engine

### 4. TimescaleDB
- PostgreSQL with time-series extension
- Hypertables with 1-day chunks
- Row-Level Security for tenant isolation
- Continuous aggregates (hourly/daily rollups)
- 30-day compression, 2-year retention

### 5. ML Service
- FastAPI REST API
- Rule-based + statistical anomaly detection
- Ready for ONNX model integration
- <100ms p95 latency target

### 6. LocalStack (Optional)
- Emulates S3, Kinesis, Lambda for local dev
- Not actively used yet (reserved for Lambda testing)

## Data Flow

```
Device Simulator
    │
    │ MQTT Publish
    ↓
EMQX Broker (topic: tenants/X/devices/Y/telemetry)
    │
    │ Subscribe
    ↓
Router Service
    ├─→ Validate Schema
    ├─→ Store in TimescaleDB
    │     └─→ Update device.last_seen
    │     └─→ Insert telemetry row
    │
    ├─→ Query Baseline Stats (24h lookback)
    │
    └─→ POST to ML Service /score
          └─→ Returns: {anomaly_score, is_anomaly, confidence}
                │
                │ if is_anomaly
                ↓
          Log Alert (TODO: store in alerts table)
```

## Multi-Tenancy Strategy

### Layer 1: MQTT Topics
- Enforced at publish/subscribe level
- AWS IoT Policies with `${iot:ClientId}` variables
- Local dev: no enforcement (trust-based)

### Layer 2: Database RLS
```sql
CREATE POLICY tenant_isolation ON telemetry.heart_failure_measurements
  FOR ALL USING (tenant_id = current_setting('app.current_tenant'));
```

### Layer 3: API Authentication (Production)
- Cognito JWT with `tenant_id` claim
- Lambda authorizer validates claim
- Sets session variable for RLS

### Layer 4: Encryption
- Per-tenant KMS keys
- Column-level encryption for sensitive metadata

## Scalability Design

### Target Metrics
- **Devices**: 1,000,000
- **Message Rate**: 1 msg/min/device = 16,667 msg/s
- **Data Volume**: ~1 KB/msg = 16.7 MB/s ingress
- **Storage**: ~1.4 TB/year raw telemetry

### Scaling Strategy

| Component | Local Dev | Production AWS |
|-----------|-----------|----------------|
| MQTT Broker | EMQX single node | IoT Core (auto-scale) |
| Message Queue | - | Kinesis (10 shards) |
| Ingestion | Router (1 pod) | Lambda (concurrency: 1000) |
| Time-Series DB | TimescaleDB (16GB) | Timestream (auto-scale) |
| ML Inference | FastAPI (1 pod) | Lambda or SageMaker |
| Object Storage | - | S3 (cold tier after 90 days) |

### Cost Optimization
- Use AWS IoT Core **Basic Ingest** (50% cheaper, bypass pub/sub broker)
- Compress TimescaleDB chunks after 30 days
- Tier S3 data: Hot (90d) → IA (1yr) → Glacier (2yr+)
- Use Timestream magnetic store for historical queries

## Security Architecture

### Authentication Flow (Production)

```
User/Device
    │
    ↓
Cognito User Pool / IoT Certificate
    │
    ↓
JWT / X.509 Certificate
    │
    ↓
API Gateway / IoT Core (validates)
    │
    ↓
Lambda Authorizer
    │ Extracts tenant_id from token
    │
    ↓
Application (sets RLS context)
    │
    ↓
TimescaleDB (enforces RLS)
```

### Threat Model (High-Level)

| Threat | Mitigation |
|--------|-----------|
| Cross-tenant data access | RLS + ABAC policies + JWT claims |
| PHI exposure | No PHI in telemetry; separate FHIR store |
| MQTT spoofing | TLS + client certificates + IoT Policies |
| SQL injection | Parameterized queries |
| Insider threat | Audit logs + least privilege IAM |
| DDoS | IoT Core throttling + WAF |

See `THREATMODEL.md` for full details (TODO).

## Observability

### Metrics
- **Telemetry**: Messages/sec, validation errors, latency p50/p95/p99
- **ML**: Scoring latency, anomaly rate, false positive rate
- **Database**: Query time, connection pool, disk usage

### Logging
- Structured JSON logs
- Correlation IDs (trace requests)
- PHI scrubbing filter

### Alerting
- Router error rate > 5%
- ML service latency > 200ms
- Database disk > 80%
- No telemetry from device > 2 hours

## Disaster Recovery

### Backup Strategy
- TimescaleDB: Automated snapshots every 6 hours (retain 7 days)
- S3: Cross-region replication
- Code: GitHub (git-based recovery)

### RTO/RPO Targets
- **RTO**: 1 hour (restore from snapshot)
- **RPO**: 6 hours (max data loss)

### Runbook
See `docs/RUNBOOK.md` (TODO) for:
- Service restart procedures
- Database failover
- Certificate rotation
- On-call escalation

## Future Enhancements

### Phase 2
- [ ] Next.js dashboard with real-time charts
- [ ] Cognito authentication
- [ ] Terraform deployment
- [ ] Load testing (k6)

### Phase 3
- [ ] Advanced ML (LSTM, XGBoost)
- [ ] FHIR integration (HealthLake)
- [ ] Clinician alerting (SMS, email)
- [ ] Multi-region replication

### Phase 4
- [ ] Edge computing (AWS Greengrass)
- [ ] Federated learning (privacy-preserving ML)
- [ ] Real-time dashboards (WebSocket)
- [ ] Predictive maintenance (device battery)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Author**: System Architect
