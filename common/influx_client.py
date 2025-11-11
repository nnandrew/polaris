import os
import dotenv
import requests
from threading import Thread
from influxdb_client import Point

def write_worker(records):   
    """
    Worker function to write records to InfluxDB.

    Args:
        records (Point or list): A single Point or a list of Points to write
                                 to InfluxDB.
    """
    dotenv.load_dotenv()
    LIGHTHOUSE_ADMIN_PASSWORD = os.getenv("LIGHTHOUSE_ADMIN_PASSWORD")
    if not LIGHTHOUSE_ADMIN_PASSWORD.startswith("apiv3_"):
        LIGHTHOUSE_ADMIN_PASSWORD = "apiv3_" + LIGHTHOUSE_ADMIN_PASSWORD
    url = f"https://{os.getenv('LIGHTHOUSE_HOSTNAME')}/influx/api/v3/write_lp?db=GPS&precision=second"
    headers = {
        "Authorization": f"Token {LIGHTHOUSE_ADMIN_PASSWORD}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    try:
        if type(records) is list:
            payload = "\n".join([record.to_line_protocol() for record in records])
        elif type(records) is Point:
            payload = records.to_line_protocol()
        else:
            print(f"{'influx_writer':<20}: Invalid record type for InfluxDB write.")
            return
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code != 204:
            print(f"{'influx_writer':<20}: Influx write error: {response.status_code} - {response.text}")
            return
        print(f"{'influx_writer':<20}: InfluxDB write successful. {len(payload.encode(encoding='utf-8'))} bytes sent.")
    except Exception as err:
        print(f"{'influx_writer':<20}: InfluxDB write error: {err}")

def write(records):
    """
    Initiates a background thread to write records to InfluxDB.
    
    Args:
        records (Point or list): A single Point or a list of Points to write
                                 to InfluxDB.
    """
    Thread(target=write_worker, args=(records,), daemon=True).start()