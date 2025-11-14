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

from datetime import datetime, timedelta, timezone
from threading import Event, Thread
import time
import sys
import os

import pytz
import dotenv
import requests
from pyubx2 import UBXReader
from influxdb_client_3 import Point
from pygnssutils import GNSSNTRIPClient
from pygnssutils.gnssntripclient import GGAFIXED

try:
    from common.ubx_config import UBXConfig
    from common.gps_reader import GPSReader
    from common.influx_client import InfluxWriter
    from common.config_server import ConfigServer
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    from ubx_config import UBXConfig
    from gps_reader import GPSReader
    from influx_client import InfluxWriter
    from config_server import ConfigServer

def read_messages_thread(gps, ubx_config, save_event, stop_event):
    """
    Reads parsed UBX NAV-PVT data from the GPS and writes it to InfluxDB.

    This function continuously reads from the GPS device. When a `NAV-PVT`
    (Position, Velocity, Time) message is received, it extracts key metrics,
    formats them as a data point, and writes them to the InfluxDB "GPS"
    database using line protocol.

    Args:
        gps (GPSReader): The GPS reader object.
        ubx_config (UBXConfig): The UBX configuration object.
        save_event (Event): An event to control whether data should be written to InfluxDB.
        stop_event (Event): A threading event to signal when to stop.
    """

    print(f"{'read_messages_thread':<20}: Starting...")
    ubr = UBXReader(gps.ser)
    last_rxm_rtcm_time = 0
    while not stop_event.is_set():
        _, parsed_data = ubr.read()
        if parsed_data:
            match parsed_data.identity:
                case 'ACK-ACK':
                    ubx_config.set_ack()
                case 'ACK-NAK':
                    ubx_config.set_nack()
                case 'NAV-PVT':
                    try:
                        point = Point("metrics").tag("device", gps.gps_type)
                        # Only write position data if fix is valid
                        if parsed_data.gnssFixOk:
                            # Only save lat/lon if allowed
                            if save_event.is_set():
                                point.field("latitude", parsed_data.lat) \
                                    .field("longitude", parsed_data.lon)
                            point.field("altitude_m", parsed_data.hMSL/1000) \
                                .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                                .field("ground_heading_deg", parsed_data.headMot) \
                                .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                                .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                                .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                                .field("heading_accuracy_deg", parsed_data.headAcc)
                            # print(f"{'read_messages_thread':<20}: Latitude: {parsed_data.lat}")
                            # print(f"{'read_messages_thread':<20}: Longitude: {parsed_data.lon}")
                        
                        # Common fields
                        point.field("fix_type_int", int(parsed_data.fixType)) \
                            .field("fix_ok_int", int(parsed_data.gnssFixOk)) \
                            .field('carrier_phase_range_int', int(parsed_data.carrSoln)) \
                            .field('last_correction_age_int', int(parsed_data.lastCorrectionAge))

                        # Use the provided timestamp if available, otherwise use current time
                        if parsed_data.validTime and parsed_data.validDate:
                            nano = parsed_data.nano
                            seconds_to_subtract = 0
                            if nano < 0:
                                seconds_to_subtract = 1
                                nano += int(1e9)
                            dt = datetime(
                                year=parsed_data.year, month=parsed_data.month, day=parsed_data.day,
                                hour=parsed_data.hour, minute=parsed_data.min, second=parsed_data.second,
                                microsecond=int(nano/1e3), tzinfo=timezone.utc
                            )
                            dt = dt - timedelta(seconds=seconds_to_subtract)
                            point.time(int(dt.timestamp()*1e9))
                            # print(f"{'read_messages_thread':<20}: GPS Timestamp: {dt.isoformat()}")
                        else:
                            point.time(int(time.time()*1e9))
                        InfluxWriter.batch_write(point)
                    except Exception as e:
                        print(f"{'read_messages_thread':<20}: Ignoring error: {e}")
                case 'RXM-RTCM':
                    # print(f"{'read_messages_thread:':<20}: DEBUG: {parsed_data}")
                    RXM_RTCM_LOG_INTERVAL = 10  # seconds
                    if time.time() >= last_rxm_rtcm_time + RXM_RTCM_LOG_INTERVAL:
                        last_rxm_rtcm_time = time.time()
                        point = Point("metrics") \
                                .tag("device", gps.gps_type) \
                                .field("ntrip_client_rtcm_received_int", 1) \
                                .time(int(time.time()*1e9))
                        InfluxWriter.batch_write(point)
            # print(f"{'read_messages_thread:':<20}: DEBUG: {parsed_data}")
    print(f"{'read_messages_thread':<20}: Exiting.")

def input_thread(save_event, stop_event):
    """
    Thread to handle user input for timing and controlling data saving.

    Args:
        save_event (Event): An event to control whether data should be written to InfluxDB.
        stop_event (Event): A threading event to signal when to stop.
    """
    
    print(f"{'input_thread':<20}: Starting...")
    def get_current_utc_time():
        current_time = datetime.now(pytz.timezone("US/Central"))
        return current_time
    
    while not stop_event.is_set():
        usr_input= input(f"{'input_thread':<20}: Press 's' to start/stop stopwatch, Enter to pause/resume Influx writing\n")
        if usr_input == 's':
            start_utc = get_current_utc_time()
            input('Stopwatch started, press Enter to stop...\n')
            finish_utc = get_current_utc_time()
            diff = finish_utc - start_utc
            print(f'Start time: {start_utc}')
            print(f'Finish time: {finish_utc}')
            print(f'Diff: {diff.total_seconds()}')
        elif usr_input == '':
            save_event.clear()
            input('Press Enter to resume writing to influx...\n')
            save_event.set()
    print(f"{'input_thread':<20}: Exiting.")

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
    
    print("Starting Polaris NTRIP Client...")
    
    # Initialize variables
    thread_pool = []
    stop_event = Event()
    save_event = Event()
    save_event.set()

    # Configure the GPS reader based on the detected hardware type
    gps = GPSReader()
    gnc = None
    
    # Determine GPS type and set up configuration accordingly
    match gps.gps_type:
        case "BUDGET":
            config_msg = gps.get_nav_pvt_config()
        case "PREMIUM":
            config_msg = gps.get_nav_pvt_config(uart=True)
        case "SPARKFUN":
            config_msg = UBXConfig.convert_u_center_config('R_Config.txt')
            if len(sys.argv) > 1:
                if sys.argv[1] == "personal":
                    dotenv.load_dotenv()
                    server = requests.get(f"https://{os.getenv('LIGHTHOUSE_HOSTNAME')}/api/ntrip").text.strip()
                    mountpoint = "pygnssutils"
                    ntripuser = "polaris"
                elif sys.argv[1] == "public":
                    server = "rtk2go.com"
                    mountpoint = "AUS_LOFT_GNSS"
                    ntripuser = "andrewvnguyen@utexas.edu"
                gnc = GNSSNTRIPClient()
                print(f"{'rtcm_get_thread':<20}: Using RTK caster at {server}")
    
    # Add thread for user input handling
    thread_pool.append(
        Thread(
            target=input_thread,
            args=(save_event, stop_event),
            daemon=True
        )
    )
    
    # Start GPS message reading thread
    ubx_config = UBXConfig(gps.ser)
    read_thread = Thread(
        target=read_messages_thread,
        args=(gps, ubx_config, save_event, stop_event),
    )
    read_thread.start()
    thread_pool.append(read_thread)

    # Configure the receiver with the appropriate settings
    success, msg = ubx_config.send_config(config_msg)
    if success:
        print("\n\nBase station configured successfully.\n\n")
    else:
        print(f"\n\nFailed to configure base station: {msg}\n\n")

    # Start remaining threads/processes
    for t in thread_pool:
        if not t.is_alive():
            t.start()
    if gnc:
        gnc.run(
            server=server,
            mountpoint=mountpoint,
            ntripuser=ntripuser,
            ntrippassword="none",
            output=gps.ser,
            stop_event=stop_event,
            ggamode=GGAFIXED
        )
    ConfigServer(ubx_config).run()
    
    # Main loop to keep the application running until interrupted
    print(f"{'main_thread':<20}: Threads started, press CTRL-C to terminate...")
    try:
        for t in thread_pool:
            t.join()
    except KeyboardInterrupt:
        print(f"\n{'main_thread':<20}: Termination signal received, shutting down threads...")
        stop_event.set()
        for t in thread_pool:
            t.join(timeout=1)
    finally:
        gps.close_serial()
        print(f"{'main_thread':<20}: NTRIP Client terminated.")

if __name__ == "__main__":
    app()
