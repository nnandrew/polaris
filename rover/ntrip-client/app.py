"""
Rover NTRIP Client Application.

This multithreaded application connects to an NTRIP caster to receive RTCM
correction data, applies it to a local GPS device, and logs the resulting
high-precision location data to an InfluxDB database.

The application consists of three main threads:
1. `rtcm_get_thread`: Connects to the NTRIP caster and fetches RTCM data into a
   shared queue.
2. `rtcm_process_thread`: Reads RTCM data from the queue and forwards it to the
   GPS device's serial port.
3. `read_messages_thread`: Reads UBX (NAV-PVT) messages from the GPS, formats
   them as data points, and writes them to InfluxDB.

The script is configured via a `GPS_TYPE` variable and environment variables
for InfluxDB credentials. It is designed to be terminated gracefully with CTRL-C.
"""
import argparse
import os
import sys
import queue
import dotenv
import requests
from time import sleep
from pygnssutils import GNSSNTRIPClient
from pygnssutils.gnssntripclient import GGAFIXED
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import (
    Event,
    Thread,
    Lock
)
from influxdb_client_3 import Point
from pyubx2 import (
    protocol,
    RTCM3_PROTOCOL
)
try:
    from common import gps_reader, ubx_config
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    import gps_reader
    import ubx_config

def influx_client_write_worker(records):   
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
            print(f"{'rtcm_process_thread':<20}: Invalid record type for InfluxDB write.")
            return
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code != 204:
            print(f"{'rtcm_process_thread':<20}: Influx write error: {response.status_code} - {response.text}")
            return
        print(f"{'rtcm_process_thread':<20}: InfluxDB write successful. {len(payload.encode(encoding='utf-8'))} bytes sent.")
    except Exception as err:
        print(f"{'rtcm_process_thread':<20}: InfluxDB write error: {err}")

def influx_client_write(records):
    """
    Initiates a background thread to write records to InfluxDB.
    
    Args:
        records (Point or list): A single Point or a list of Points to write
                                 to InfluxDB.
    """
    Thread(target=influx_client_write_worker, args=(records,), daemon=True).start()

def rtcm_process_thread(gnss_rtcm_queue, gps, stop_event, gps_type, lock):
    """
    Reads RTCM3 data from a queue and sends it to the GPS device.

    This function runs in a loop, checking the queue for new data. If valid
    RTCM3 data is found, it is written directly to the GPS device's serial port
    to enable RTK corrections. It also logs metrics to InfluxDB in batches.

    Args:
        gnss_rtcm_queue (Queue): The queue from which to get RTCM data.
        gps (gps_reader.GPSReader): The GPS reader instance with an open serial port.
        stop_event (Event): A threading event to signal when to stop.
        gps_type (str): The type of GPS device (e.g., "sparkfun").
        lock (Lock): A mutex to ensure thread-safe access to the serial port.
    """
    print(f"{'rtcm_process_thread':<20}: Starting...")
    msg_count = 0
    while not stop_event.is_set():
        try:
            raw_data, _ = gnss_rtcm_queue.get(timeout=0.1)
            try:
                if protocol(raw_data) == RTCM3_PROTOCOL:
                    with lock:
                        gps.ser.write(raw_data)
                    msg_count += 1

                    # Log received RTCM message metric every 4 messages
                    if msg_count >= 4:
                        msg_count = 0
                        point = Point("metrics") \
                            .tag("device", gps_type) \
                            .field("ntrip_client_rtcm_received_int", 1) \
                            .time(int(datetime.now(timezone.utc).timestamp()))
                        influx_client_write(point)
                        print(f"{'rtcm_process_thread':<20}: Queue size: {gnss_rtcm_queue.qsize()}")

            finally:
                gnss_rtcm_queue.task_done()
        except queue.Empty:
            # No data available in queue
            continue
        except Exception as e:
            print(f"{'rtcm_process_thread':<20}: Error: {e}")
            continue
    print(f"{'rtcm_process_thread':<20}: Exiting.")

def read_messages_thread(stop_event, ubx_reader, gps_type, lock):
    """
    Reads parsed UBX NAV-PVT data from the GPS and writes it to InfluxDB.

    This function continuously reads from the GPS device. When a `NAV-PVT`
    (Position, Velocity, Time) message is received, it extracts key metrics,
    formats them as a data point, and writes them to the InfluxDB "GPS"
    database using line protocol.

    Args:
        stop_event (Event): A threading event to signal when to stop.
        ubx_reader (UBXReader): The UBXReader instance for reading from the serial port.
        gps_type (str): The type of GPS device (e.g., "sparkfun").
        lock (Lock): A mutex to ensure thread-safe access to the serial port.
    """

    print(f"{'read_messages_thread':<20}: Starting...")

    while not stop_event.is_set():
        try:
            lock.acquire()
            _, parsed_data = ubx_reader.read()
            lock.release()
            if parsed_data and parsed_data.identity == 'NAV-PVT':
                try:
                    point = Point("metrics").tag("device", gps_type)

                    if parsed_data.gnssFixOk:
                        point.field("latitude", parsed_data.lat) \
                            .field("longitude", parsed_data.lon) \
                            .field("altitude_m", parsed_data.hMSL/1000) \
                            .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                            .field("ground_heading_deg", parsed_data.headMot) \
                            .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                            .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                            .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                            .field("heading_accuracy_deg", parsed_data.headAcc)
                        print(f"{'read_messages_thread':<20}: Latitude: {parsed_data.lat}")
                        print(f"{'read_messages_thread':<20}: Longitude: {parsed_data.lon}")
                    
                    point.field("fix_type_int", int(parsed_data.fixType)) \
                        .field("fix_ok_int", int(parsed_data.gnssFixOk)) \
                        .field('carrier_phase_range_int', int(parsed_data.carrSoln))

                    # Use the provided timestamp if available, otherwise InfluxDB
                    # will use the current time.
                    if parsed_data.validTime and parsed_data.validDate:
                        dt = datetime(
                            year=parsed_data.year, month=parsed_data.month, day=parsed_data.day,
                            hour=parsed_data.hour, minute=parsed_data.min, second=parsed_data.second,
                            tzinfo=timezone.utc
                        )
                        point.time(int(dt.timestamp()))
                        print(f"{'read_messages_thread':<20}: Timestamp: {dt.isoformat()}")

                    influx_client_write(point)
                except Exception as e:
                    print(f"{'read_messages_thread':<20}: Error: {e}. Re-initializing...")
            elif parsed_data and parsed_data.identity == 'RXM-RTCM':
                print(f"{'read_messages_thread:':<20}: DEBUG: {parsed_data}")
                pass
            elif parsed_data:
                # print(f'IDK This data: {parsed_data}')
                pass
        except Exception as e:
            print(f"\n{'read_messages_thread':<20}: Something went wrong {e}\n")
            continue

def get_current_utc_time():
    current_time = datetime.now(timezone.utc)
    print(current_time)
    return current_time

def stopwatch(stop_event):
    while not stop_event.is_set():
        input("Press Enter to start the stopwatch...\n")
        start_utc = get_current_utc_time()
        input('Press Enter to stop the stopwatch...\n')
        finish_utc = get_current_utc_time()
        diff = finish_utc - start_utc
        print(diff.total_seconds())

def app():
    """
    Main application function to set up and run the NTRIP client threads.

    This function performs the following steps:
    1. Initializes the GPS reader based on the detected hardware.
    2. Creates and starts the necessary threads for fetching RTCM data,
       processing it, and logging GPS data to InfluxDB.
    3. Waits for a `KeyboardInterrupt` (CTRL-C) to terminate the application.
    4. Sets a `stop_event` to signal all threads to shut down gracefully.
    5. Joins all threads to ensure they have finished before exiting.
    6. Closes the serial connection to the GPS device.
    """
    print("Starting NTRIP Client...")

    thread_pool = []
    gps = None
    stop_event = Event()
    lock = Lock()

    # Configure the GPS reader based on the detected hardware type.
    gps = gps_reader.GPSReader()
    gps_type = gps.gps_type
    match gps_type:
        case "BUDGET":
            config_msg = gps.get_nav_pvt_config()
        case "PREMIUM":
            config_msg = gps.get_nav_pvt_config(uart=True)
        case "SPARKFUN":
            config_msg = ubx_config.convert_u_center_config('R_Config.txt')
            if len(sys.argv) > 1:
                if sys.argv[1] == "personal":
                    dotenv.load_dotenv()
                    server = requests.get(f"https://{os.getenv('LIGHTHOUSE_HOSTNAME')}/api/ntrip").text.strip()
                    mountpoint = "pygnssutils"
                    ntripuser = "polaris"
                    print(f"{'rtcm_get_thread':<20}: Using personal RTK caster at {server}")
                elif sys.argv[1] == "public":
                    server = "rtk2go.com"
                    mountpoint = "AUS_LOFT_GNSS"
                    ntripuser = "andrewvnguyen@utexas.edu"
                    print(f"{'rtcm_get_thread':<20}: Using public RTK caster at {server}")
                gnss_rtcm_queue = queue.Queue()
                gnc = GNSSNTRIPClient()
                thread_pool.append(
                    Thread(
                        target=rtcm_process_thread,
                        args=(gnss_rtcm_queue, gps, stop_event, gps_type, lock),
                        daemon=True
                    )
                )
            
    thread_pool.append(
        Thread(
            target=read_messages_thread,
            args=(stop_event, gps.get_reader(), gps_type, lock),
        )
    )
    
    # Uncomment the following to include a stopwatch in the CLI.
    # thread_pool.append(
    #     Thread(
    #         target=stopwatch,
    #         args=(stop_event,),
    #         daemon=True
    #     )
    # )

    # Configure the receiver with the appropriate settings.
    try:
        nar = ubx_config.send_config(config_msg, gps.ser)
        if not nar:
            print('ERROR: Failed to write config')
            return
    except Exception as e:
        print(f'ERROR: Unexpected Error when writing config: {e}')
        return

    # Start all the threads.
    for t in thread_pool:
        t.start()
    if gnc:
        gnc.run(
            server=server,
            mountpoint=mountpoint,
            ntripuser=ntripuser,
            ntrippassword="none",
            output=gnss_rtcm_queue,
            stop_event=stop_event,
            ggamode=GGAFIXED
        )
    print(f"{'main_thread':<20}: Threads started, press CTRL-C to terminate...")
    
    # Main loop - wait for a termination signal (CTRL-C).
    try:
        while not stop_event.is_set():
            sleep(1)
    except (KeyboardInterrupt, SystemExit):
        stop_event.set()
        print(f"\n{'main_thread':<20}: Termination signal received, shutting down threads...")

    # Wait for all threads to finish their execution.
    for t in thread_pool:
        t.join()
    print(f"{'main_thread':<20}: All threads have finished.")

    # Clean up by closing the GPS serial connection.
    gps.close_serial()
    print(f"{'main_thread':<20}: NTRIP Client terminated.")

if __name__ == "__main__":
    app()
