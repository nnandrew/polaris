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
    NETWORK_KEY = os.getenv("NETWORK_KEY")
    LIGHTHOUSE_PUBLIC_IP = os.getenv("LIGHTHOUSE_PUBLIC_IP")
    GROUP_NAME = os.getenv("GROUP_NAME")
    logging.info("Environment Variables Loaded.")
    
    # Attempt Enrollment
    url = f"http://{LIGHTHOUSE_PUBLIC_IP}/api/enroll"
    params = {
        "network_key": NETWORK_KEY,
        "group_name": GROUP_NAME
    }
    config_path = "./shared/config.yml"

    while True:
        if not os.path.exists(config_path):
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    with open(config_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)
                    logger.info("GET request successful.")
                else:
                    logger.warning(f"Request failed with status code {response.status_code}. Retrying in {BACKOFF_TIME} seconds.")
            except requests.RequestException as e:
                logger.warning(f"Error making GET request: {e}. Retrying in {BACKOFF_TIME} seconds.")
        else:
            logger.info(f"Config exists. Checking again in {BACKOFF_TIME} seconds.")
        time.sleep(BACKOFF_TIME)