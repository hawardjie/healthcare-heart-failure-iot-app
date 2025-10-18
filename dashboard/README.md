# Heart Failure IoT Dashboard

Next.js dashboard for real-time CardioMEMS device monitoring.

## Quick Start

```bash
cd dashboard

# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Features

- Real-time telemetry display (auto-refresh every 5 seconds)
- Multi-tenant filtering
- Statistics overview:
  - Total readings in last hour
  - Active devices
  - Average PAP systolic
  - Elevated PAP alerts
- Recent telemetry table with color-coded alerts
- Responsive design with Tailwind CSS

## API Endpoints

- `GET /api/stats?tenant_id={tenant}` - Get summary statistics
- `GET /api/telemetry?tenant_id={tenant}&limit={n}` - Get recent telemetry
- `GET /api/devices?tenant_id={tenant}` - Get device list with stats

## Environment Variables

See `.env.local`:
- `DATABASE_URL` - PostgreSQL connection string
- `DEFAULT_TENANT` - Default tenant for demo

## Production Deployment

```bash
npm run build
npm start
```

Or deploy to Vercel:
```bash
vercel deploy
```

## Tech Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- PostgreSQL (TimescaleDB)
- Recharts (future: add charts)
