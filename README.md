# Heart Failure IoT Platform - AWS IoT Core Edition

A production-ready, **multi-tenant** IoT platform for CardioMEMS Heart Failure medical devices. Streams telemetry to AWS IoT Core, detects anomalies with ML, and provides a local Mac development environment using Docker.

## Features

- **Multi-Tenant Architecture**: Strict tenant isolation at MQTT topic, database (RLS), and API levels
- **CardioMEMS HF Simulation**: Realistic pulmonary artery pressure (PAP) telemetry with physiological patterns
- **ML Anomaly Detection**: Real-time scoring for heart failure event prediction
- **HIPAA-Ready**: No PHI in raw telemetry; pseudonymous device IDs; audit logging
- **Local Development**: Full stack runs on Mac with Docker (no AWS account needed for dev)
- **Production AWS Path**: Terraform IaC for IoT Core, Lambda, Timestream, Cognito, HealthLake

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOCAL DEVELOPMENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      MQTT Topics:                             │
│  │  Simulator   │   tenants/{tenantId}/devices/{deviceId}/...   │
│  │ 500 Devices  │                                                │
│  │  2 Tenants   │──────┐                                         │
│  └──────────────┘      │                                         │
│                        ↓                                         │
│              ┌──────────────────┐                                │
│              │   EMQX Broker    │  (mimics AWS IoT Core)         │
│              │   localhost:1883 │                                │
│              └─────────┬────────┘                                │
│                        │                                         │
│                        ↓                                         │
│              ┌──────────────────┐                                │
│              │  Router Service  │  (mimics IoT Rules Engine)     │
│              │  - Parse MQTT    │                                │
│              │  - Validate      │                                │
│              │  - Store DB      │                                │
│              │  - Call ML       │                                │
│              └─────────┬────────┘                                │
│                        │                                         │
│         ┌──────────────┴───────────────┐                         │
│         ↓                               ↓                        │
│  ┌──────────────┐             ┌────────────────┐                │
│  │ TimescaleDB  │             │  ML Service    │                │
│  │ (Hypertable) │             │  FastAPI       │                │
│  │ - Telemetry  │             │  Anomaly Score │                │
│  │ - Alerts     │             │  (ONNX Ready)  │                │
│  │ - RLS Enabled│             └────────────────┘                │
│  └──────────────┘                                                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

PRODUCTION AWS (Infrastructure code provided, not deployed locally):
- AWS IoT Core + Device Provisioning Service (DPS)
- Kinesis Data Streams → Lambda → Timestream
- SageMaker / Lambda ML inference
- Cognito (OIDC) + IAM ABAC policies
- AWS HealthLake (FHIR) for PHI
- KMS per-tenant encryption keys
```

---

## Quick Start (Mac)

### Prerequisites

- macOS (tested on Monterey+)
- Docker Desktop installed and running
- Homebrew (for optional tools)

### One-Command Setup

```bash
# Clone/navigate to this repo
cd awsIoTCoreProj

# Install dependencies and start all services
make setup      # Install brew, python, node (one-time)
make up         # Start Docker Compose stack
```

That's it! The platform will start:
- EMQX MQTT broker (port 1883)
- TimescaleDB (port 5432)
- ML Service (port 8000)
- LocalStack (port 4566)
- Device Simulator (500 devices publishing every 60s)
- Router Service (processing telemetry)

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| EMQX Dashboard | http://localhost:18083 | admin / public |
| ML API Docs | http://localhost:8000/docs | - |
| TimescaleDB | localhost:5432 | iot_admin / local_dev_password |
| LocalStack | http://localhost:4566 | - |

---

## Usage

### View Live Telemetry

```bash
# Watch all logs
make logs

# Watch specific service
make logs-simulator
make logs-router
make logs-ml

# Subscribe to MQTT topics directly (requires mosquitto-clients)
make mqtt-sub
```

### Query Database

```bash
# Open psql shell
make db-shell

# Run queries
SELECT * FROM telemetry.recent_measurements LIMIT 10;
SELECT * FROM alerts.active_alerts;
SELECT * FROM telemetry.hourly_stats WHERE tenant_id = 'clinic-alpha';
```

### Test MQTT Manually

```bash
# Publish a test message
make mqtt-test

# Or use mosquitto_pub directly
mosquitto_pub -h localhost -p 1883 \
  -t 'tenants/clinic-alpha/devices/TEST-001/telemetry' \
  -m '{"timestamp":"2025-10-17T12:00:00Z","deviceId":"TEST-001","tenantId":"clinic-alpha","pap_systolic":32,"pap_diastolic":14,"pap_mean":20,"heart_rate":85,"signal_quality":0.92,"battery_level":95,"temperature":37.0}'
```

### Call ML API Directly

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "telemetry": {
      "timestamp": "2025-10-17T12:00:00Z",
      "deviceId": "CM-ALPHA-001",
      "tenantId": "clinic-alpha",
      "pap_systolic": 35.0,
      "pap_diastolic": 16.0,
      "pap_mean": 22.3,
      "heart_rate": 105,
      "signal_quality": 0.88
    }
  }'
```

---

## Project Structure

```
awsIoTCoreProj/
├── docker-compose.yml          # Local dev orchestration
├── Makefile                    # Dev commands
├── .env.example                # Configuration template
│
├── simulator/                  # Device telemetry generator
│   ├── simulator.py            # 500 CardioMEMS devices
│   ├── requirements.txt
│   └── Dockerfile
│
├── router_local/               # MQTT → DB → ML router
│   ├── router.py               # Mimics IoT Core Rules Engine
│   ├── requirements.txt
│   └── Dockerfile
│
├── ml_service/                 # Anomaly detection API
│   ├── service.py              # FastAPI + rule-based ML
│   ├── train.py                # (TODO) Model training
│   ├── requirements.txt
│   ├── Dockerfile
│   └── models/                 # .onnx / .pkl models
│
├── config/
│   ├── timescaledb/
│   │   └── init.sql            # Schema with hypertables, RLS
│   └── emqx/                   # MQTT broker config
│
├── infrastructure/             # (TODO) Terraform for AWS
│   ├── iot_core.tf
│   ├── lambda.tf
│   ├── timestream.tf
│   └── cognito.tf
│
├── lambda_functions/           # (TODO) AWS Lambda handlers
│   ├── ingest_router/
│   ├── score_stream/
│   └── fhir_writer/
│
├── dashboard/                  # (TODO) Next.js UI
│   ├── pages/
│   ├── components/
│   └── lib/
│
├── tests/                      # (TODO) Test suites
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── docs/                       # (TODO) Architecture docs
    ├── RUNBOOK.md
    ├── THREATMODEL.md
    └── DATA_HANDLING.md
```

---

## Multi-Tenancy Design

### Tenant Isolation Layers

1. **MQTT Topic Taxonomy**
   ```
   tenants/{tenantId}/devices/{deviceId}/telemetry
   tenants/{tenantId}/devices/{deviceId}/shadow
   tenants/{tenantId}/alerts
   ```

2. **Database Row-Level Security (RLS)**
   ```sql
   -- See config/timescaledb/init.sql
   CREATE POLICY tenant_isolation_policy ON telemetry.heart_failure_measurements
       FOR ALL USING (tenant_id = current_setting('app.current_tenant'));
   ```

3. **API Authentication** (Production)
   - Cognito OIDC tokens with `tenant_id` claim
   - IAM ABAC policies with `aws:RequestTag/TenantId`
   - Per-tenant KMS encryption keys

### Tenants in Simulator

- `clinic-alpha`: 250 devices
- `hospital-beta`: 250 devices

Change in `.env`:
```bash
SIMULATOR_TENANTS=clinic-alpha,hospital-beta,clinic-gamma
SIMULATOR_DEVICE_COUNT=900  # Split across 3 tenants
```

---

## Telemetry Schema

CardioMEMS HF payload (JSON):

```json
{
  "timestamp": "2025-10-17T12:34:56.789Z",
  "deviceId": "CM-ALPHA-001",
  "tenantId": "clinic-alpha",

  "pap_systolic": 28.5,       // mmHg (normal: 15-28, HF risk: >28)
  "pap_diastolic": 12.3,      // mmHg (normal: 5-12, HF risk: >12)
  "pap_mean": 17.7,           // Computed: (sys + 2*dia) / 3

  "heart_rate": 78,           // bpm
  "signal_quality": 0.94,     // 0.0-1.0

  "battery_level": 87,        // %
  "temperature": 37.1         // Celsius
}
```

**IMPORTANT**: No PHI (patient name, MRN, DOB) in telemetry. Only pseudonymous `deviceId`. Patient linkage happens in separate FHIR store.

---

## ML Anomaly Detection

### Current Implementation (Rule-Based)

- **Clinical Thresholds**: PAP > 28/12 mmHg (elevated), > 35/16 mmHg (critical)
- **Statistical Outliers**: Z-score > 2.5 from device baseline
- **Heart Rate**: Tachy/bradycardia detection
- **Signal Quality**: Poor readings flagged

### Roadmap (Full ML)

- [x] Rule-based scoring (baseline)
- [ ] Feature engineering (rolling stats, trends, circadian patterns)
- [ ] Isolation Forest / One-Class SVM training
- [ ] LSTM for temporal sequences
- [ ] XGBoost with lag features
- [ ] ONNX export for fast inference
- [ ] A/B testing framework
- [ ] Drift monitoring (PSI)

Train model:
```bash
# (TODO)
cd ml_service
python train.py --data ../data/labeled_anomalies.csv --output models/anomaly_model.onnx
```

---

## Testing

```bash
# Unit tests
make test-unit

# Integration tests (requires services running)
make test-integration

# All tests
make test
```

---

## Useful Commands

```bash
make help           # Show all commands
make up             # Start services
make down           # Stop services
make logs           # Tail all logs
make ps             # Show running containers
make db-shell       # Open psql
make db-reset       # Reset database schema
make clean          # Stop and remove volumes
make restart        # Restart all services
```

---

## Configuration

Edit `.env` (copy from `.env.example`):

```bash
# Simulator
DEVICE_COUNT=500                    # Number of virtual devices
MESSAGE_INTERVAL=60                 # Seconds between messages
ANOMALY_PROBABILITY=0.05            # 5% of messages are anomalies

# Database
POSTGRES_PASSWORD=local_dev_password

# MQTT
MQTT_BROKER_HOST=emqx
MQTT_BROKER_PORT=1883
```

---

## Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker ps

# Check ports aren't in use
lsof -i :1883   # MQTT
lsof -i :5432   # PostgreSQL
lsof -i :8000   # ML Service

# Rebuild containers
docker compose build --no-cache
docker compose up -d
```

### No telemetry appearing

```bash
# Check simulator is running
docker logs hf-simulator

# Check MQTT broker
docker logs hf-emqx

# Subscribe to all topics
mosquitto_sub -h localhost -p 1883 -t '#' -v
```

### Database connection errors

```bash
# Check TimescaleDB is ready
docker exec hf-timescaledb pg_isready

# Reinitialize schema
make db-reset

# Check credentials in .env
```

### ML service not responding

```bash
# Check service health
curl http://localhost:8000/health

# View logs
docker logs hf-ml-service

# Restart service
docker compose restart ml_service
```

---

## Production Deployment (AWS)

### Architecture Changes

| Local Dev | AWS Production |
|-----------|---------------|
| EMQX | AWS IoT Core + DPS |
| TimescaleDB | Amazon Timestream + S3 |
| Router Service | IoT Rules Engine + Lambda |
| ML Service | Lambda (container) or SageMaker |
| LocalStack | Real AWS Services |

### Prerequisites

- AWS account with IoT Core enabled
- Terraform installed (`brew install terraform`)
- AWS CLI configured (`aws configure`)

### Deploy

```bash
cd infrastructure/

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy (CAUTION: creates real AWS resources)
terraform apply

# Outputs will include:
# - IoT Core endpoint
# - Cognito User Pool ID
# - API Gateway URL
# - Timestream database name
```

See `infrastructure/README.md` for detailed deployment guide.

---

## Security & Compliance

### HIPAA Considerations

- ✅ **No PHI in telemetry streams** (pseudonymous device IDs only)
- ✅ **Encryption in transit** (MQTT over TLS in production)
- ✅ **Encryption at rest** (KMS per-tenant keys)
- ✅ **Audit logging** (every DB access logged)
- ✅ **Row-level security** (tenant isolation)
- ⚠️ **BAA required** with AWS
- ⚠️ **Private VPC endpoints** (no public internet)

### Authentication Flow (Production)

```
User Login → Cognito → JWT with tenant_id claim → API Gateway
                                                      ↓
                                     Lambda validates JWT + tenant_id
                                                      ↓
                                     Sets session tenant context
                                                      ↓
                                     RLS enforces data isolation
```

---

## Roadmap

### Phase 1: Local MVP ✅ (Current)
- [x] Docker Compose local dev
- [x] Multi-tenant MQTT ingestion
- [x] TimescaleDB with hypertables
- [x] Basic ML anomaly detection
- [x] Device simulator

### Phase 2: AWS Deployment (Next)
- [ ] Terraform IaC for IoT Core, Kinesis, Lambda
- [ ] Cognito authentication
- [ ] Next.js dashboard with charts
- [ ] End-to-end tests (Playwright)
- [ ] Load testing (k6 to 20k msg/s)

### Phase 3: Production Features
- [ ] Advanced ML (LSTM, XGBoost, ONNX)
- [ ] FHIR integration (HealthLake)
- [ ] EHR webhooks (Epic, Cerner)
- [ ] Clinician alerting (SNS, Twilio)
- [ ] Drift monitoring & retraining pipeline
- [ ] Cost optimization (Basic Ingest, S3 tiering)

### Phase 4: Scale & Ops
- [ ] Auto-scaling (1M devices, 16.7k msg/s)
- [ ] Multi-region replication
- [ ] Disaster recovery runbooks
- [ ] On-call SLOs (99.9% uptime)
- [ ] SOC 2 compliance documentation

---

## Contributing

This is a reference implementation. For production use:

1. Review security settings (JWT validation, KMS keys)
2. Conduct threat modeling (see `docs/THREATMODEL.md` TODO)
3. Load test at expected scale
4. Obtain BAA from AWS
5. Configure HIPAA-compliant logging (CloudWatch + S3 encrypted)

---

## License

MIT License - See LICENSE file

---

## Support

For issues or questions:
- GitHub Issues: [link to repo]
- Documentation: `docs/`
- AWS IoT Core Docs: https://docs.aws.amazon.com/iot/

---

**Built with ❤️ for Heart Failure Patients**

This platform aims to enable early detection of cardiac decompensation events, reducing hospital readmissions and improving patient outcomes.
