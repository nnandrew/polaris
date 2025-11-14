import os
import time
from threading import Thread, Lock

import dotenv
import requests
from influxdb_client_3 import Point

class InfluxWriter:

    batch_lock = Lock()
    batch_records = []
    batch_last_flush = 0
    
    @classmethod
    def sync_write(cls, records):   
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
        url = f"https://{os.getenv('LIGHTHOUSE_HOSTNAME')}/influx/api/v3/write_lp?db=GPS&precision=nanosecond"
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

    @classmethod
    def async_write(cls, records):
        """
        Initiates a background thread to write records to InfluxDB.
        
        Args:
            records (Point or list): A single Point or a list of Points to write
                                    to InfluxDB.
        """
        Thread(target=cls.sync_write, args=(records,), daemon=True).start()

    @classmethod
    def batch_write(cls, records):
        """
        Adds records to a shared batch and flushes every second.
        
        Args:
            records (list): A list of Points to add to the batch.
        """

        BATCH_FLUSH_TIME = 0.2

        if not isinstance(records, list):
            records = [records]

        with cls.batch_lock:
            cls.batch_records.extend(records)
            new_time = time.time()
            if cls.batch_last_flush == 0:
                cls.batch_last_flush = new_time
            elif new_time >= cls.batch_last_flush + BATCH_FLUSH_TIME:
                cls.batch_last_flush = new_time
                batch_to_write = cls.batch_records
                cls.batch_records = []
                cls.async_write(batch_to_write)