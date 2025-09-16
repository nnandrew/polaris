# Lighthouse

A public server to initiate Nebula mesh network connectivity.

## Prerequisites

Create a `polaris/rover/.env` containing:

```yaml
INFLUXDB_URL = "URL"
INFLUXDB_TOKEN = "API_KEY"
```

## Usage

Configure GPS_TYPE and NTRIP Server in `polaris/rover/ntrip-client/app.py`.

Then run:

```bash
docker-compose up --build
```