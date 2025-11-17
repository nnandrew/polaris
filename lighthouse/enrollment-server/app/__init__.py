"""
Flask application factory for the Nebula Enrollment Server.

This module is responsible for creating and configuring the Flask application,
as well as performing essential one-time setup tasks for the Lighthouse.
"""

from influxdb_client_3 import Point
from threading import Thread
from .routes import main_bp 
from app import nebula
import subprocess
import requests
import tarfile
import sqlite3
import flask
import time
import sys
import os
try:
    from .common.influx_client import InfluxWriter
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../../common")
    from influx_client import InfluxWriter

def monitor_hosts():
    """
    Monitors all hosts by pinging them every 5 seconds and logging their status.
    """
    
    while True:
        hosts = nebula.get_hosts(ping=True)
        records = []
        for host in hosts:
            records.append(
                Point("network_telemetry").tag("id", int(host[0])) \
                                          .tag("vpn_ip", str(host[1])) \
                                          .tag("group_name", str(host[2])) \
                                          .field("ping", float(host[3])) \
                                          .time(int(time.time()*1e9))
            )
        InfluxWriter.async_write(records)

def create_app():
    """
    Creates and configures a Flask application instance and performs initial setup.

    This factory function handles the following setup procedures:
    1.  Initializes the Flask app and loads configuration from environment variables.
    2.  Registers the main API blueprint.
    3.  Changes the working directory to `./shared`.
    4.  Downloads and extracts the 'nebula-cert' utility if it's not present.
    5.  Generates a Nebula Certificate Authority (CA) key and certificate if they
        do not already exist.
    6.  Initializes a SQLite database (`record.db`) to track enrolled hosts.
    7.  Generates the initial Nebula configuration file (`config.yml`) for the
        Lighthouse node itself if it doesn't exist.

    Returns:
        flask.Flask: The configured Flask application instance.
    """
    # Configure Flask App
    app = flask.Flask(__name__)
    app.config["SECRET_KEY"] = os.urandom(24)
    app.config["LIGHTHOUSE_ADMIN_PASSWORD"] = os.getenv("LIGHTHOUSE_ADMIN_PASSWORD")
    app.config["LIGHTHOUSE_HOSTNAME"] = os.getenv("LIGHTHOUSE_HOSTNAME")
    print(f"Lighthouse Hostname: {app.config.get('LIGHTHOUSE_HOSTNAME')}")
    print(f"Lighthouse Admin Password: {app.config.get('LIGHTHOUSE_ADMIN_PASSWORD')}")
    app.register_blueprint(main_bp)

    # Download Nebula Certificate Generator if necessary
    os.chdir("./shared")
    if not os.path.exists("./nebula-cert"):
    
        url = "https://github.com/slackhq/nebula/releases/download/v1.9.5/nebula-linux-amd64.tar.gz"
        response = requests.get(url)
        with open('./nebula-linux-amd64.tar.gz', 'wb') as file:
            file.write(response.content)

        with tarfile.open('./nebula-linux-amd64.tar.gz', 'r:gz') as tar:
            tar.extractall('.')
        
        os.remove('./nebula-linux-amd64.tar.gz')
        os.remove('./nebula')
        print("Nebula Certificate Generator Downloaded.")

    # Generate CA Key if necessary
    if not os.path.exists("./ca.key"):     
        subprocess.run(["./nebula-cert", "ca", "-name", "\"Polaris\""])
        print("CA Key and Certificate Generated.")   
        
    # Initialize SQLite database if necessary
    if not os.path.exists("./record.db"):
        conn = sqlite3.connect("./record.db")
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vpn_ip TEXT NOT NULL,
            group_name TEXT NOT NULL
        )
        ''')
        conn.commit()
        conn.close()   
        
    # Generate Lighthouse Configuration if necessary
    if not os.path.exists("./config.yml"):
        config_path = nebula.generate_nebula_config(group_name="lighthouse", public_ip=app.config.get('LIGHTHOUSE_PUBLIC_IP'))
        print(f"Lighthouse Configuration Generated at {config_path}.")   
        
    # Start Nebula Host Monitor Thread
    Thread(target=monitor_hosts).start()

    return app