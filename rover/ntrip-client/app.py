"""
Rover NTRIP Client Application.

This multithreaded application connects to an NTRIP caster to receive RTCM
correction data, applies it to a local GPS device, and logs the resulting
high-precision location data to an InfluxDB database.

The application consists of three main threads:
1. `rtcm_get_thread`: Connects to the NTRIP caster and fetches RTCM data.
2. `rtcm_process_thread`: Forwards the fetched RTCM data to the GPS device.
3. `read_messages_thread`: Reads UBX messages from the GPS and takes the appropriate action based on message.
    For example, `NAV-PVT` writes the location data to InfluxDB.

The script is configured via a `GPS_TYPE` variable and environment variables
for InfluxDB credentials. It is designed to be terminated with CTRL-C.
"""
import os
import dotenv
import requests
from queue import Queue
from time import sleep
from pygnssutils import GNSSNTRIPClient
from datetime import datetime, timezone
from threading import (
    Event,
    Thread,
    Lock
)
from influxdb_client_3 import (
    Point
)
from pyubx2 import (
    protocol,
    RTCM3_PROTOCOL
)
try:
    from common import gps_reader, ubx_config
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    import gps_reader
    import ubx_config

def influx_client_write(records):
    """
    Attempts to write records to InfluxDB using line protocol.
    
    Args:
        records: A single Point or a list of Points to write to InfluxDB.
    """
    dotenv.load_dotenv()
    url = f"https://{os.getenv('LIGHTHOUSE_HOSTNAME')}/influx/api/v3/write_lp?db=GPS&precision=second"
    headers = {
        "Authorization": f"Token {os.getenv('LIGHTHOUSE_ADMIN_PASSWORD')}",
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
            print(f"{'rtcm_process_thread':<20}: Error writing: {response.status_code} - {response.text}")
    except Exception as err:
        print(f"{'rtcm_process_thread':<20}: InfluxDB write error: {err}")

def rtcm_get_thread(gnss_rtcm_queue, stop_event):
    """
    Connects to an NTRIP caster and streams RTCM data into a queue.

    This function runs the `GNSSNTRIPClient` in a blocking manner. The client
    is configured to connect to the private RTK base station and place all

    incoming RTCM data into the provided queue.

    Args:
        gnss_rtcm_queue (Queue): The queue to which RTCM data will be added.
        stop_event (Event): A threading event to signal when to stop.
    """
    print(f"{'rtcm_get_thread':<20}: Starting...")
    gnc = GNSSNTRIPClient()
    gnc.run(
        # Public RTK 12km away, unreliable)
        # server="rtk2go.com",
        # mountpoint="AUS_LOFT_GNSS",
        # ntripuser="andrewvnguyen@utexas.edu",
        #Private RTK
        server="192.168.100.3", # Private RTK, TODO: get with /api/ntrip
        mountpoint="pygnssutils",
        ntripuser="test",
        ntrippassword="none",
        port=2101,
        https=0,
        datatype="RTCM",
        output=gnss_rtcm_queue,
        # DGPS Configuration (unused)
        ggainterval=-1,
        ggamode=1,  # fixed rover reference coordinates
        reflat=0.0,
        reflon=0.0,
        refalt=0.0,
        refsep=0.0,
    )
    while not stop_event.is_set():
        sleep(1)

def rtcm_process_thread(gnss_rtcm_queue, gps, stop_event, gps_type, lock):
    """
    Reads RTCM3 data from a queue and sends it to the GPS device.

    This function runs in a loop, checking the queue for new data. If valid
    RTCM3 data is found, it is written directly to the GPS device's serial port
    to enable RTK corrections.

    Args:
        gnss_rtcm_queue (Queue): The queue from which to get RTCM data.
        gps (gps_reader.GPSReader): The GPS reader instance with an open serial port.
        stop_event (Event): A threading event to signal when to stop.
        gps_type (str): The type of GPS device (e.g., "sparkfun").
        lock: To send data to the Serial
    """
    print(f"{'rtcm_process_thread':<20}: Starting...")
    msg_count = 0
    last_queue_size_print = 0
    
    # Batch metrics for more efficient InfluxDB writes
    metrics_batch = []
    while not stop_event.is_set():
        while not gnss_rtcm_queue.empty():
            # Use get with timeout to avoid busy waiting
            raw_data, _ = gnss_rtcm_queue.get(timeout=0.1)
            
            if protocol(raw_data) == RTCM3_PROTOCOL:
                with lock:  # Using context manager for cleaner lock handling
                    gps.ser.write(raw_data)
                
                msg_count += 1
                metrics_batch.append(Point("metrics")
                    .tag("device", gps_type)
                    .field("ntrip_client_rtcm_recieved_int", 1))
                
                # Print queue size periodically
                if msg_count - last_queue_size_print >= 10:
                    print(f"{'rtcm_process_thread':<20}: Queue size: {gnss_rtcm_queue.qsize()}")
                    last_queue_size_print = msg_count
                
                # Batch write to InfluxDB
                if len(metrics_batch) >= 10:
                    influx_client_write(metrics_batch)
    
            gnss_rtcm_queue.task_done()
            
        # Queue is empty, write any remaining metrics
        if metrics_batch:
            influx_client_write(metrics_batch)

def read_messages_thread(stop_event, ubx_reader, gps_type, lock):
    """
    Reads parsed UBX NAV-PVT data from the GPS and writes it to InfluxDB.

    This function continuously reads from the GPS device. When a `NAV-PVT`
    (Position, Velocity, Time) message is received, it extracts key metrics,
    formats them as a data point, and writes them to the InfluxDB "GPS"
    database using line protocol.

    Args:
        stop_event (threading.Event): Event to stop reading messages
        ubx_reader : The Serial wrapper to read UBX messages from serial.
        gps_type (str): The type of GPS device (e.g., "sparkfun").
        lock: To send data to the Serial
    """
    # pylint: disable=unused-variable, broad-except

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

                    # Use provided timestamp if available
                    if parsed_data.validTime and parsed_data.validDate:
                        dt = datetime(
                            year=parsed_data.year, month=parsed_data.month, day=parsed_data.day,
                            hour=parsed_data.hour, minute=parsed_data.min, second=parsed_data.second,
                            tzinfo=timezone.utc
                        )
                        point.time(int(dt.timestamp()))

                    influx_client_write(point)
                except Exception as e:
                    print(f"{'read_messages_thread':<20}: Error: {e}. Re-initializing...")
            elif parsed_data and parsed_data.identity == 'RXM-RTCM':
                print(f"{'read_messages_threadDEBUG':<20}: {parsed_data}")
            # elif parsed_data:
            #     print(f'IDK This data: {parsed_data}')
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

    Initializes the appropriate GPS reader based on the `GPS_TYPE` setting,
    creates and starts the necessary threads for data fetching, processing,

    and logging, and then waits for a `KeyboardInterrupt` to terminate.
    """
    print("Starting NTRIP Client...")

    thread_pool = []
    gps = None
    stop_event = Event()
    lock = Lock()

    # Configure GPS type
    gps = gps_reader.GPSReader()
    gps_type = gps.gps_type
    match gps_type:
        case "BUDGET":
            config_msg = gps.get_nav_pvt_config()
        case "PREMIUM":
            config_msg = gps.get_nav_pvt_config(raw=True)
        case "SPARKFUN":
            config_msg = ubx_config.convert_u_center_config('R_Config.txt')
            gnss_rtcm_queue = Queue()
            thread_pool.append(
                Thread(
                    target=rtcm_get_thread,
                    args=(gnss_rtcm_queue, stop_event),
                    daemon=True
                )
            )
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
    
    # Uncomment Below to include a stopwatch in the CLI that will show the
    # start and stop UTC time along with the total seconds.
    # thread_pool.append(
    #     Thread(
    #         target=stopwatch,
    #         args=(stop_event,),
    #         daemon=True
    #     )
    # )

    # Configure the receiver
    try:
        nar = ubx_config.send_config(config_msg, gps.ser)
        if not nar:
            print('ERROR: Failed to write config')
            return
    except Exception as e:
        print(f'ERROR: Unexpected Error when writing config: {e}')
        return

    # Start the threads
    for t in thread_pool:
        t.start()
    print(f"{'main_thread':<20}: Threads started, press CTRL-C to terminate...")
    
    # Main loop - wait for CTRL-C
    try:
        while not stop_event.is_set():
            sleep(1)
    except (KeyboardInterrupt, SystemExit):
        stop_event.set()
        print(f"\n{'main_thread':<20}: Termination signal received, shutting down threads...")

    # Wait for all threads to finish
    for t in thread_pool:
        t.join()
    print(f"{'main_thread':<20}: All threads have finished.")

    # Close the GPS serial connection
    gps.close_serial()
    print(f"{'main_thread':<20}: NTRIP Client terminated.")

if __name__ == "__main__":
    app()