# Quick Start Guide

## ✅ System Status

Your Heart Failure IoT Platform is **running successfully!**

### Services Running

- **EMQX Broker**: localhost:1883 (Dashboard: http://localhost:18083)
- **TimescaleDB**: localhost:5432
- **ML Service**: http://localhost:8000
- **Router**: Processing telemetry
- **Simulator**: 500 devices publishing every 60 seconds

### Current Data

- **500 telemetry records** stored in database
- **500 unique devices** (250 per tenant)
- **2 tenants**: clinic-alpha, hospital-beta
- **Anomalies**: ~5% injection rate (~25 per batch)

---

## 🚀 Start the Dashboard

```bash
cd dashboard
npm run dev
```

Then open: **http://localhost:3000**

### Dashboard Features

- ✅ Real-time telemetry display (auto-refresh every 5s)
- ✅ Multi-tenant selector
- ✅ Statistics cards (readings, devices, PAP averages, alerts)
- ✅ Color-coded alerts (elevated PAP > 28 mmHg)
- ✅ Recent telemetry table with 20 latest readings

---

## 📊 Explore the Data

### View Live Telemetry (CLI)

```bash
# Subscribe to MQTT topics
make mqtt-sub

# Or with mosquitto directly
mosquitto_sub -h localhost -p 1883 -t 'tenants/#' -v
```

### Query Database

```bash
# Open psql shell
make db-shell

# Run queries
SELECT COUNT(*) FROM telemetry.heart_failure_measurements;
SELECT * FROM telemetry.recent_measurements LIMIT 10;
SELECT * FROM alerts.active_alerts;
```

### Check Services

```bash
# View all service status
docker compose ps

# View logs
make logs              # All services
make logs-simulator    # Simulator only
make logs-router       # Router only
```

### Test ML API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs  # OpenAPI docs
```

---

## 🔍 API Endpoints

Test the dashboard APIs directly:

```bash
# Get stats
curl "http://localhost:3000/api/stats?tenant_id=clinic-alpha"

# Get telemetry
curl "http://localhost:3000/api/telemetry?tenant_id=clinic-alpha&limit=10"

# Get devices
curl "http://localhost:3000/api/devices?tenant_id=clinic-alpha"
```

---

## 🛑 Stop Everything

```bash
make down        # Stop all services
make clean       # Stop and remove volumes
```

---

## 🐛 Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker ps

# Rebuild containers
docker compose build --no-cache
docker compose up -d
```

### No telemetry in database

```bash
# Check simulator is running
docker logs hf-simulator --tail 50

# Check router is processing
docker logs hf-router --tail 50

# Restart services
docker compose restart simulator router
```

### Dashboard errors

```bash
cd dashboard

# Check .env.local exists
cat .env.local

# Reinstall dependencies
rm -rf node_modules
npm install

# Run in debug mode
npm run dev
```

---

## 📈 Next Steps

### Add Advanced ML

```bash
cd ml_service
python train.py --data ../data/labeled_data.csv
```

### Deploy to AWS

```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

### Load Testing

```bash
# Increase simulator scale
# Edit .env:
DEVICE_COUNT=5000
MESSAGE_INTERVAL=10  # 10 seconds = 500 msg/s

docker compose restart simulator
```

### Add Real-Time Charts

The dashboard is ready for charts. Add Recharts components:

```typescript
import { LineChart, Line, XAxis, YAxis } from 'recharts';
// See dashboard/README.md for examples
```

---

## 📚 Documentation

- **Architecture**: docs/ARCHITECTURE.md
- **API Reference**: http://localhost:8000/docs (ML Service)
- **Database Schema**: config/timescaledb/init.sql
- **README**: README.md (main project)

---

## 🎉 Success!

You now have a fully functional, multi-tenant Heart Failure IoT platform running locally!

**Key Achievements:**
- ✅ 500 devices streaming telemetry
- ✅ Multi-tenant isolation (RLS enabled)
- ✅ Real-time anomaly detection
- ✅ Responsive Next.js dashboard
- ✅ Production-ready architecture

**What's Working:**
- MQTT ingestion → TimescaleDB storage
- ML scoring with baseline stats
- API routes with tenant filtering
- Auto-refreshing dashboard
- Docker-based local dev environment

Enjoy exploring your Heart Failure IoT Platform! 🚀
