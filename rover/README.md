# Rover

An NTRIP client, RTCM sender, GPS receiver, and InfluxDB writer app.

## Prerequisites

Navigate to https://cloud2.influxdata.com/ and gather the required secrets.

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
