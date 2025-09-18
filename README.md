# Polaris: A High-Precision RTK GNSS System

Polaris is a complete system for Real-Time Kinematic (RTK) GNSS, designed to deliver low-latency, centimeter-level positioning accuracy. It establishes a secure and efficient network for a **Base Station**, a **Rover**, and a **Lighthouse** server to communicate, enabling the Rover to calculate its precise location by receiving correction data from the Base Station.

The system is built with security and performance in mind, using a Nebula mesh network for secure, low-latency data transfer and a simple, robust enrollment system for managing network nodes.

## System Architecture

Polaris consists of three primary components that work together over a secure mesh network.

### 1. Lighthouse (EC2 Server)
The Lighthouse is the central coordination server, typically run on a cloud instance with a public IP address. It is the anchor of the Nebula mesh network.

- **Enrollment Server**: A Flask-based web service that handles requests from new nodes (Base Stations or Rovers) to join the network. It authenticates nodes using a shared secret key, generates unique Nebula certificates and configuration files for them, and maintains a record of all nodes in the network.
- **Nebula Lighthouse**: This core Nebula service acts as the discovery point for all other nodes, allowing them to find each other and establish secure, direct connections.

### 2. Base Station (e.g. Qualcomm RB5, Raspberry Pi)
The Base Station is a stationary GNSS receiver with a known, fixed location. Its primary role is to generate and broadcast correction data.

- **GPS Receiver**: A high-quality GNSS module (like the SparkFun u-blox ZED-F9P) that receives raw satellite signals.
- **NTRIP Caster**: A service (`gnssserver`) that takes the raw GNSS data, generates RTCM 3 correction messages, and broadcasts them over the network via an NTRIP (Networked Transport of RTCM via Internet Protocol) server.
- **Enrollment Client**: A script that runs on startup to enroll with the Lighthouse and retrieve the necessary Nebula configuration to join the mesh network.

### 3. Rover (e.g. Qualcomm RB5, Rasberry Pi)
The Rover is the mobile unit whose position is being tracked.

- **GPS Receiver**: A GNSS module, identical to the one on the Base Station.
- **NTRIP Client**: A multi-threaded Python application that connects to the Base Station's NTRIP caster, receives the RTCM correction stream, and applies it directly to the local GPS module.
- **InfluxDB Logger**: A thread within the NTRIP client that reads the corrected position data (`NAV-PVT` messages) from the GPS and logs it to an InfluxDB time-series database for monitoring and analysis.
- **Enrollment Client**: Same as the Base Station, this script allows the Rover to join the network.

### (Optional) Dashboard
A monitoring dashboard can be set up to visualize the status and data from all components.

- **Grafana**: A data visualization tool that connects to InfluxDB.
- **InfluxDB**: The time-series database where the Rover logs its location data.

## Setup Instructions

Follow these steps to set up each component of the Polaris system.

### Prerequisites
- A server with a public, static IP address to act as the Lighthouse (e.g. an AWS EC2 instance).
- Two single-board computers (e.g. Qualcomm RB5, Raspberry Pi 4) for the Base Station and Rover.
- Two identical high-precision GNSS receiver modules (e.g., SparkFun ZED-F9P) that can output raw GNSS data.

### 1. Lighthouse Setup
First, set up the central server.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/lighthouse
    ```

2.  **Create the environment file:**
    Create a file named `.env` inside the `lighthouse/enrollment-server/` directory with the following content. Choose a strong, unique key for `NETWORK_KEY`.
    ```
    LIGHTHOUSE_PUBLIC_IP="<Your Server's Public IP>"
    NETWORK_KEY="<Your-Secret-Network-Key>"
    ```
    You can optionally create a `.env` file in `lighthouse/` for the Grafana Dashboard with secrets possibly from [here](https://cloud2.influxdata.com/):
    ```
    INFLUXDB_URL="<Your-InfluxDB-Server>"
    INFLUXDB_TOKEN="<Your-InfluxDB-Token>"
    GF_SECURITY_ADMIN_USER="<Your-Grafana-User>"
    GF_SECURITY_ADMIN_PASSWORD="<Your-Grafana-Password>"
    ```
3.  **Start the services:**
    Use Docker Compose to build and run the Lighthouse services.
    ```bash
    docker-compose up --build -d
    ```
    On the first run, the server will download the `nebula-cert` tool and generate a Certificate Authority (`ca.key`, `ca.crt`), a host record database (`record.db`), and a configuration file (`config.yml`) inside the `lighthouse/enrollment-server/shared/` directory.

### 2. Base Station Setup
Next, set up the stationary Base Station.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/base-station
    ```
2.  **Create the environment file:**
    Create a file named `.env` inside the `base-station/enrollment-client/` directory. Use the **same IP and network key** as the Lighthouse.
    ```
    LIGHTHOUSE_PUBLIC_IP="<Your Server's Public IP>"
    NETWORK_KEY="<Your-Secret-Network-Key>"
    GROUP_NAME="base_station"
    ```
3.  **Connect the GPS:**
    Connect your GNSS module to the Base Station device via USB.

4.  **Start the services:**
    ```bash
    docker-compose up --build -d
    ```
    The enrollment client will contact the Lighthouse, receive its unique configuration, and place it in the `base-station/nebula/shared/` directory. The Nebula service will then use this to connect to the network.

### 3. Rover Setup
Finally, set up the mobile Rover.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/rover
    ```
2.  **Create the environment file:**
    Create a file named `.env` inside the `lighthouse/enrollment-client/` directory.
    ```
    LIGHTHOUSE_PUBLIC_IP="<Your Server's Public IP>"
    NETWORK_KEY="<Your-Secret-Network-Key>"
    GROUP_NAME="rover"
    ```
    You will also need to create a `.env` file in `rover/ntrip-client/` for the InfluxDB logger with secrets possibly from [here](https://cloud2.influxdata.com/):
    ```
    INFLUXDB_URL="<Your-InfluxDB-Server>"
    INFLUXDB_TOKEN="<Your-InfluxDB-Token>"
    ```

3.  **Connect the GPS:**
    Connect your GNSS module to the Rover device via USB.

4.  **Start the services:**
    ```bash
    docker-compose up --build -d
    ```

## Usage

Once all three components are running, the system will operate automatically:
1.  The **Base Station** and **Rover** will enroll with the **Lighthouse** and join the secure Nebula network.
2.  The **Base Station** will start broadcasting RTCM correction data from its fixed location.
3.  The **Rover's** NTRIP client will automatically discover the Base Station's IP address (by querying the Lighthouse's `/api/ntrip` endpoint) and start consuming the RTCM data.
4.  The Rover's GPS module will begin using the correction data to achieve a high-precision (RTK) fix.
5.  The Rover will log its position, fix status, and other metrics to your configured InfluxDB instance.

You can monitor the system by:
-   **Viewing the logs** of the Docker containers on each machine: `docker-compose logs -f <service_name>`
-   **Checking the enrolled hosts** by visiting `http://<Your Server's Public IP>/api/hosts` in a browser.
-   **Visualizing the data** in Grafana by creating dashboards that query your InfluxDB database.

## Useful Links
- **InfluxDB Cloud**: [https://www.influxdata.com/products/influxdb-cloud/](https://www.influxdata.com/products/influxdb-cloud/)
- **Nebula Project**: [https://github.com/slackhq/nebula](https://github.com/slackhq/nebula)
- **pygnssutils Documentation**: [https://github.com/semuconsulting/pygnssutils](https://github.com/semuconsulting/pygnssutils)
