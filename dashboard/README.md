# Website

A telemetry dashboard that monitors Base Station and Rover performance metrics.

## Prerequisites

Navigate to https://cloud2.influxdata.com/ and gather the required secrets.

`polaris/rover/.env` containing:

```yaml
INFLUXDB_URL = "URL"
INFLUXDB_TOKEN = "API_KEY"
GF_SECURITY_ADMIN_USER= "USER"
GF_SECURITY_ADMIN_PASSWORD= "PASSWORD"
```

## Usage

```bash
docker-compose up --build
```