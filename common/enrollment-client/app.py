"""
Nebula Enrollment Client.

This script acts as a client to enroll with the Lighthouse server and receive a
Nebula network configuration file (`config.yml`). It runs in a continuous loop,
periodically checking if the configuration file exists. If not, it sends a GET
request to the enrollment server's API to obtain one.

The client requires the following environment variables to be set:
- `LIGHTHOUSE_ADMIN_PASSWORD`: A secret key to authenticate with the enrollment server.
- `LIGHTHOUSE_HOSTNAME`: The public hostname or IP address of the Lighthouse server.
- `LIGHTHOUSE_GROUP_NAME`: The Nebula security group this client should belong to.

The script will place the received `config.yml` in the `./shared/` directory,
where it can be used by the Nebula service.
"""
import os
import time
import dotenv
import logging  
import requests 
import subprocess
import platform

BACKOFF_TIME = 5

def ping(host):
    """
    Param host: str - The host to ping.
    Returns True if host (str) responds to a ping request.
    """

    param = '-n' if platform.system().lower()=='windows' else '-c'
    command = ['ping', param, '1', host]
    return subprocess.call(command) == 0

if __name__ == '__main__':
    
    # Logger Configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    # Load Environment Variables
    dotenv.load_dotenv()
    LIGHTHOUSE_ADMIN_PASSWORD = os.getenv("LIGHTHOUSE_ADMIN_PASSWORD")
    LIGHTHOUSE_HOSTNAME = os.getenv("LIGHTHOUSE_HOSTNAME")
    LIGHTHOUSE_GROUP_NAME = os.getenv("LIGHTHOUSE_GROUP_NAME")
    logging.info("Environment Variables Loaded.")
    
    # Attempt to enroll with the Lighthouse until a configuration is received.
    url = f"https://{LIGHTHOUSE_HOSTNAME}/api/enroll"
    params = {
        "LIGHTHOUSE_ADMIN_PASSWORD": LIGHTHOUSE_ADMIN_PASSWORD,
        "group_name": LIGHTHOUSE_GROUP_NAME
    }
    config_path = "./shared/config.yml"
    
    while True:
        # Guard clause for network connectivity
        if not ping("8.8.8.8"):
            logger.warning("No network connection. Retrying in 5 seconds...")
            time.sleep(BACKOFF_TIME)
            continue
        
        # Guard clause for VPN connectivity
        vpn_connected = False
        for i in range(10):
            if ping("192.168.100.1"): # Lighthouse VPN IP
                vpn_connected = True
                break
            time.sleep(1)

        # Only attempt enrollment if VPN cannot connect
        if not vpn_connected:
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    with open(config_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)
                    logger.info(f"Config saved to {config_path}.")
                else:
                    logger.warning(f"Request failed with status code {response.status_code}. Retrying in {BACKOFF_TIME} seconds.")
            except requests.RequestException as e:
                logger.warning(f"Error making GET request: {e}. Retrying in {BACKOFF_TIME} seconds.")
        else:
            logger.info(f"VPN connection is healthy! Checking again in {BACKOFF_TIME} seconds.")
        time.sleep(BACKOFF_TIME)
