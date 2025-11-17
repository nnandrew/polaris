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
import logging  
import platform
import subprocess

import dotenv
import requests 

BACKOFF_TIME = 5

def ping(host):
    """
    Param host: str - The host to ping.
    Returns True if host (str) responds to a ping request.
    """

    count_param = '-n' if platform.system().lower()=='windows' else '-c'
    command = ['ping', count_param, '1', '-W', '1', host]
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
    LIGHTHOUSE_HOSTNAME = os.getenv("LIGHTHOUSE_HOSTNAME")
    LIGHTHOUSE_ADMIN_PASSWORD = os.getenv("LIGHTHOUSE_ADMIN_PASSWORD")
    LIGHTHOUSE_GROUP_NAME = os.getenv("LIGHTHOUSE_GROUP_NAME")
    DEVICE_NAME = platform.node()
    DEVICE_OS = platform.platform()
    API_ROOT = f"https://{LIGHTHOUSE_HOSTNAME}/api"
    HEADERS = {"X-API-KEY": LIGHTHOUSE_ADMIN_PASSWORD}
    GROUP_NAME = f"{LIGHTHOUSE_GROUP_NAME}_{DEVICE_NAME}_{DEVICE_OS}"
    logging.info("Environment Variables Loaded.")

    # Attempt to enroll with the Lighthouse until a configuration is received.
    while True:
        # Guard clause for network connectivity
        if not ping("8.8.8.8"):
            logger.warning("No network connection. Retrying in 5 seconds...")
            time.sleep(BACKOFF_TIME)
            continue
        
        # Guard clause for VPN connectivity
        vpn_connected = False
        # 10 attempts to punch through with VPN
        for i in range(10):
            logger.info(f"Pinging Lighthouse to check connectivity... (Attempt {i+1}/10)")
            if ping("192.168.100.1"): # Lighthouse VPN IP
                vpn_connected = True
                break

        # Only attempt enrollment if VPN cannot connect
        if not vpn_connected:
            try:
                enroll_response = requests.post(
                    url=f"{API_ROOT}/hosts/enroll", 
                    params={"group_name": GROUP_NAME}, 
                    headers=HEADERS
                )
                if enroll_response.status_code != 200:
                    raise Exception(f"Failed to enroll: {enroll_response.status_code}, {enroll_response.text}") 
                host_id = int(enroll_response.text)
                
                download_response = requests.get(
                    url=f"{API_ROOT}/hosts/{host_id}", 
                    headers=HEADERS
                )
                if download_response.status_code != 200:
                    raise Exception(f"Failed to download config: {download_response.status_code}, {download_response.text}")
                config_path = "./shared/config.yml"
                
                with open(config_path, 'wb') as file:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        file.write(chunk)
                logger.info(f"Config saved to {config_path}.")
            except requests.RequestException as e:
                logger.warning(f"Error making GET request: {e}. Retrying in {BACKOFF_TIME} seconds.")
            except Exception as e:
                logger.warning(f"{e}. Retrying in {BACKOFF_TIME} seconds.")
        else:
            logger.info(f"VPN connection is healthy! Checking again in {BACKOFF_TIME} seconds.")
        time.sleep(BACKOFF_TIME)
