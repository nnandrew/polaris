import os
import time
import dotenv   
import requests 

BACKOFF_TIME = 5

if __name__ == '__main__':
    
    # Load Environment Variables
    dotenv.load_dotenv()
    NETWORK_KEY = os.getenv("NETWORK_KEY").split(",")
    LIGHTHOUSE_PUBLIC_IP = os.getenv("LIGHTHOUSE_PUBLIC_IP")
    
    # Attempt Enrollment
    url = f"http://{LIGHTHOUSE_PUBLIC_IP}/enroll?network_key={NETWORK_KEY}"
    config_path = "/home/enrollment-client/shared/config.yaml"

    while True:
        if not os.path.exists(config_path):
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    with open(config_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)
                    print("GET request successful.")
                else:
                    print(f"Request failed with status code {response.status_code}. Retrying in {BACKOFF_TIME} seconds.")

            except requests.RequestException as e:
                print(f"Error making GET request: {e}. Retrying in {BACKOFF_TIME} seconds.")
        time.sleep(BACKOFF_TIME)