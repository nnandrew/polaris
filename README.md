# Polaris

A low latency, centimeter accurate, 5G RTK Base Station and testing system for UT Capstone Design and Qualcomm.

## Prerequisites

- Server with public static IP
- Base Station with raw GNSS data and internet access
- Rover with raw GNSS data and internet access

## Architecture

Polaris uses HTTPS network enrollment for security purposes.

Polaris uses NTRIP over a Nebula mesh network for latency purposes.

### EC2 Lighthouse

- enrollment-server service:
  - Generate CA certificate and private key if none with
  ```nebula-cert ca -name "Polaris"```
  - Configure HTTPS
  - Start HTTPS Server and Simple REST API for Base Station/Rover Enrollment
  - Generate Keys/Certificates when requested
  - Send config with key/crt/ca to Base Station/Rover

- nebula service:
  - Runs Nebula Lighthouse

### RB5 Base Station

- ntrip-server service:
  - Read raw GNSS data
  - Continuously generate improving RTCM data
  - Unix Socket Send to ntrip-caster service

- ntrip-caster service:
  - Unix Socket Receive from ntrip-server service
  - Run HTTP server to stream data in response to a NTRIP Client GET

- enrollment-client service:
  - Use REST enrollment endpoint to get mesh network secrets

- nebula service:
  - Join Nebula mesh network

### RB5 Rover

- ntrip-client service:
  - HTTP GET RTCM stream
  - Apply to raw GNSS data
  - Output corrected NMEA string

- enrollment-client service:
  - Use REST enrollment endpoint to get mesh network secrets

- nebula service:
  - Join Nebula mesh network

### Laptop Dashboard

- telemetry-receiver service:
  - Receive lighthouse status into InfluxDB
    - Online?
    - Hosts + Latencies?
  - Receive base station status into InfluxDB
    - Online?
    - Location?
    - NTRIP Server Latency?
    - NTRIP Caster Latency?
  - Receive rover status into InfluxDB
    - Online?
    - Location?
    - Base Station to Rover Latency?
    - Corrected NMEA Latency?

- grafana service:
  - Query from InfluxDB
  - Display all telemetry data

- enrollment-client service:
  - Use REST enrollment endpoint to get mesh network secrets

- nebula service:
  - Join Nebula mesh network

## Setup

**All nodes on the Nebula network require a ```.env``` file with below format:**

```yaml
LIGHTHOUSE_PUBLIC_IP = "IPSTRING"
NETWORK_KEY = "KEYSTRING"
```

### Lighthouse

```bash
git clone https://github.com/nnandrew/polaris.git
cd polaris/lighthouse
docker-compose up
```

Create ```polaris/lighthouse/enrollment-server/.env```

### Base Station

```bash
git clone https://github.com/nnandrew/polaris.git
cd polaris/base-station
docker-compose up
```

Create ```polaris/lighthouse/enrollment-client/.env```

### Rover

```bash
git clone https://github.com/nnandrew/polaris.git
cd polaris/rover
docker-compose up
```

Requires ```polaris/lighthouse/enrollment-client/.env```

## Usage

TBD

## Useful Links

- Setting up SSH for the RB5: [LINK](https://developer.ridgerun.com/wiki/index.php/Qualcomm_Robotics_RB5/Development_in_the_Board/Getting_into_the_Board/Using_SSH)
- Link to access the InfluxDB website/data: [LINK](https://us-east-1-1.aws.cloud2.influxdata.com")
