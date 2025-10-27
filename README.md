# Polaris: A High-Precision RTK GNSS System

Polaris is a complete system for Real-Time Kinematic (RTK) GNSS, designed to deliver low-latency, centimeter-level positioning accuracy. It establishes a secure and efficient network for a **Base Station**, a **Rover**, and a **Lighthouse** server to communicate, enabling the Rover to calculate its precise location by receiving correction data from the Base Station.

The system is built with security and performance in mind, using a Nebula mesh network for secure, low-latency data transfer and a simple, robust enrollment system for managing network nodes.

## System Architecture

Polaris consists of three primary components that work together over a secure mesh network.

### 1. Lighthouse (EC2 Server)
The Lighthouse is the central coordination server, typically run on a cloud instance with a public IP address. It is the anchor of the Nebula mesh network.

- **Enrollment Server**: A Flask-based web service that handles requests from new nodes (Base Stations or Rovers) to join the network. It authenticates nodes using a shared secret key, generates unique Nebula certificates and configuration files for them, and maintains a record of all nodes in the network.
- **Nebula Lighthouse**: This core Nebula service acts as the discovery point for all other nodes, allowing them to find each other and establish secure, direct connections.
- **InfluxDB**: The time-series database where the Rover logs its location data.
- **Grafana**: A data visualization tool that connects to InfluxDB.

### 2. Base Station (e.g. Qualcomm RB5, Raspberry Pi)
The Base Station is a stationary GNSS receiver with a known, fixed location. Its primary role is to generate and broadcast correction data.

- **GNSS Receiver**: A high-quality GNSS module (like the SparkFun u-blox ZED-F9P) that receives raw satellite signals.
- **NTRIP Caster**: A service (`gnssserver`) that takes the raw GNSS data, generates RTCM 3 correction messages, and broadcasts them over the network via an NTRIP (Networked Transport of RTCM via Internet Protocol) server.
- **Enrollment Client**: A script that runs on startup to enroll with the Lighthouse and retrieve the necessary Nebula configuration to join the mesh network.

### 3. Rover (e.g. Qualcomm RB5, Rasberry Pi)
The Rover is the mobile unit whose position is being tracked.

- **GPS Receiver**: A GNSS module, identical to the one on the Base Station.
- **NTRIP Client**: A multi-threaded Python application that connects to the Base Station's NTRIP caster, receives the RTCM correction stream, and applies it directly to the local GPS module.
- **InfluxDB Logger**: A thread within the NTRIP client that reads the corrected position data (`NAV-PVT` messages) from the GPS and logs it to an InfluxDB time-series database for monitoring and analysis.
- **Enrollment Client**: Same as the Base Station, this script allows the Rover to join the network.


## Requirements

### Hardware Prerequisites

-   **Lighthouse**: The Lighthouse should be deployed on a cloud server with a public, static IP address. A small virtual private server (VPS) with 1 CPU and 1 GB of RAM is sufficient for this component.
-   **Base Station and Rover**: The Base Station and Rover should be deployed on single-board computers (SBCs) with sufficient processing power and memory to run the Docker containers and Python applications. The Qualcomm RB5 or a similar device is a good choice.
-   **GNSS Receivers**: For high-precision RTK positioning, it is essential to use identical, high-quality GNSS receivers for both the Base Station and the Rover. The SparkFun ZED-F9P is a recommended option.

### Software Prerequisites

- **Docker and Docker Compose**: The entire Polaris system is containerized using Docker. You will need to have Docker and Docker Compose installed on your component machines.
- **Git**: The project is version-controlled with Git.

### Security Prerequisites

-   **Nebula Network**: The Nebula mesh network provides a secure, encrypted communication channel between the components. It is important to choose a strong, unique `LIGHTHOUSE_ADMIN_PASSWORD` to protect the enrollment process.
-   **Firewall**: Configure a firewall on the Lighthouse server to restrict access to only the necessary ports (80 for HTTP, 443 for HTTPS, and 4242 for Nebula).
-   **HTTPS**: The Nginx service in the Lighthouse is configured to use Let's Encrypt to automatically obtain and renew SSL certificates for HTTPS. It is highly recommended to use HTTPS to encrypt the communication between the enrollment clients and the Lighthouse.

## Setup Instructions

Follow these steps to set up each component of the Polaris system.

### 1. Lighthouse Setup
First, set up the central server.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/lighthouse
    ```

2.  **Create the environment file:**
    Create a file named `.env` inside the `lighthouse/` directory with the following content.
    ```bash
    LIGHTHOUSE_HOSTNAME = "<your-domain>"
    LIGHTHOUSE_ADMIN_USER = "<your-username>"
    LIGHTHOUSE_ADMIN_PASSWORD = "<your-password>"
    LIGHTHOUSE_TLS_EMAIL = "<your-email>"
    ```

3.  **Configure TLS:**
    `initletsencrypt.sh`.

4.  **Start the services:**
    Use Docker Compose to build and run the Lighthouse services.
    ```bash
    docker-compose up --build -d
    ```
    On the first run, the server will download the `nebula-cert` tool and generate a Certificate Authority (`ca.key`, `ca.crt`), a host record database (`record.db`), and a configuration file (`config.yml`) inside the `lighthouse/shared/` directory.

### 2. Base Station Setup
Next, set up the stationary Base Station.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/base-station
    ```
2.  **Create the environment file:**
    Create a file named `.env` inside the `base-station/` directory.
    ```bash
    LIGHTHOUSE_HOSTNAME = "<your-domain>"
    LIGHTHOUSE_ADMIN_PASSWORD = "<your-password>"
    GNSS_DEVICE_FILE = "<your-gnss-device>" # e.g. /dev/ttyACM0
    ```
3.  **Connect the GPS:**
    Connect your GNSS module to the Base Station device via USB.

4.  **Start the services:**
    ```bash
    docker-compose up --build -d
    ```
    The enrollment client will contact the Lighthouse, receive its unique configuration, and place it in the `base-station/shared/` directory. The Nebula service will then use this to connect to the network.

### 3. Rover Setup
Finally, set up the mobile Rover.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nnandrew/polaris.git
    cd polaris/rover
    ```
2.  **Create the environment file:**
    Create a file named `.env` inside the `rover/` directory.
    ```bash
    LIGHTHOUSE_HOSTNAME = "<your-domain>"
    LIGHTHOUSE_ADMIN_PASSWORD = "<your-password>"
    GNSS_DEVICE_FILE = "<your-gnss-device>" # e.g. /dev/ttyACM0
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
-   **Checking the enrolled hosts** by visiting `http://<Your Server's Public IP>/nebula` in a browser.
-   **Visualizing the data** in the Grafana Dashbaord at `https://<Your Server's Domain>/grafana` in the browser.

## Useful Links
- **Nebula Project**: [https://github.com/slackhq/nebula](https://github.com/slackhq/nebula)
- **pygnssutils Documentation**: [https://github.com/semuconsulting/pygnssutils](https://github.com/semuconsulting/pygnssutils)
