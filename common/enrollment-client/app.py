"""
Nebula Enrollment Client.

This script acts as a client to enroll with the Lighthouse server and receive a
Nebula network configuration file (`config.yml`). It runs in a continuous loop,
periodically checking if the configuration file exists. If not, it sends a GET
request to the enrollment server's API.

The client requires the following environment variables to be set:
- `LIGHTHOUSE_NETWORK_KEY`: A secret key to authenticate with the enrollment server.
- `LIGHTHOUSE_PUBLIC_IP`: The public IP address of the Lighthouse server.
- `LIGHTHOUSE_GROUP_NAME`: The Nebula security group this client should belong to.

The script will place the received `config.yml` in the `./shared/` directory.
"""
import os
import time
import dotenv
import logging  
import requests 

BACKOFF_TIME = 5

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
    LIGHTHOUSE_NETWORK_KEY = os.getenv("LIGHTHOUSE_NETWORK_KEY")
    LIGHTHOUSE_PUBLIC_IP = os.getenv("LIGHTHOUSE_PUBLIC_IP")
    LIGHTHOUSE_GROUP_NAME = os.getenv("LIGHTHOUSE_GROUP_NAME")
    logging.info("Environment Variables Loaded.")
    
    # Attempt Enrollment
    url = f"http://{LIGHTHOUSE_PUBLIC_IP}/api/enroll"
    params = {
        "network_key": LIGHTHOUSE_NETWORK_KEY,
        "group_name": LIGHTHOUSE_GROUP_NAME
    }
    config_path = "./shared/config.yml"
    
    if os.path.exists(config_path):
        logger.info(f"Config exists. Checking again in {BACKOFF_TIME} seconds.")

    while True:
        if not os.path.exists(config_path):
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    with open(config_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)
                    logger.info("GET request successful. Nebula config received.")
                else:
                    logger.warning(f"Request failed with status code {response.status_code}. Retrying in {BACKOFF_TIME} seconds.")
            except requests.RequestException as e:
                logger.warning(f"Error making GET request: {e}. Retrying in {BACKOFF_TIME} seconds.")
        time.sleep(BACKOFF_TIME)