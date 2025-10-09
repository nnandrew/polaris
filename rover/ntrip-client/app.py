"""
Rover NTRIP Client Application.

This multi-threaded application connects to an NTRIP caster to receive RTCM
correction data, applies it to a local GPS device, and logs the resulting
high-precision location data to an InfluxDB database.

The application consists of three main threads:
1. `rtcm_get_thread`: Connects to the NTRIP caster and fetches RTCM data.
2. `rtcm_process_thread`: Forwards the fetched RTCM data to the GPS device.
3. `influx_write_thread`: Reads `NAV-PVT` messages from the GPS, and writes
   the location data to InfluxDB.

The script is configured via a `GPS_TYPE` variable and environment variables
for InfluxDB credentials. It is designed to be terminated with CTRL-C.
"""
import os
import dotenv
from queue import Queue
from time import sleep
from pygnssutils import GNSSNTRIPClient
from datetime import datetime, timezone
from threading import (
    Event, 
    Thread
)
from influxdb_client_3 import (
    InfluxDBClient3, 
    Point
)
from pyubx2 import (
    protocol,
    RTCM3_PROTOCOL
)
from maps import (
    fixType_map,
    gpsFixOk_map,
    diffSoln_map
)
try:
    from common import gps_reader, ip_getter, u_center_config
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    import gps_reader
    import ip_getter
    import u_center_config

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
        sleep(10)
        
def rtcm_process_thread(gnss_rtcm_queue, gps, stop_event, gps_type):
    """
    Reads RTCM3 data from a queue and sends it to the GPS device.

    This function runs in a loop, checking the queue for new data. If valid
    RTCM3 data is found, it is written directly to the GPS device's serial port
    to enable RTK corrections.

    Args:
        gnss_rtcm_queue (Queue): The queue from which to get RTCM data.
        gps (gps_reader.Generic): The GPS reader instance with an open serial port.
        stop_event (Event): A threading event to signal when to stop.
    """
    print(f"{'rtcm_process_thread':<20}: Starting...")
    dotenv.load_dotenv()
    token = os.getenv("INFLUXDB_TOKEN")
    org = "GPSSensorData"
    host = "https://us-east-1-1.aws.cloud2.influxdata.com"
    client = InfluxDBClient3(host=host, token=token, org=org)
    while not stop_event.is_set():
        if not gnss_rtcm_queue.empty():
            try:
                raw_data, _ = gnss_rtcm_queue.get()
                if protocol(raw_data) == RTCM3_PROTOCOL:
                    gps.ser.write(raw_data)
                    print(f"{'rtcm_process_thread':<20}: Sent to GPS!")
                    points = Point("metrics").tag("device", gps_type)
                    points.field("ntrip_client_rtcm_recieved", True)
                    client.write(database="GPS", record=points, write_precision="s")                
                else:
                    print(f"{'rtcm_process_thread':<20}: Discarding non-RTCM3 data.")
            except Exception as err:
                print(f"{'rtcm_process_thread':<20}: {err}")
            gnss_rtcm_queue.task_done()
        sleep(1) # Prevent busy-waiting

                
def influx_write_thread(gps_type, gps, stop_event):
    """
    Reads parsed UBX NAV-PVT data from the GPS and writes it to InfluxDB.

    This function continuously reads from the GPS device. When a `NAV-PVT`
    (Position, Velocity, Time) message is received, it extracts key metrics,
    formats them as a data point, and writes them to the InfluxDB "GPS"
    database.

    Args:
        gps_type (str): The type of GPS device (e.g., "sparkfun").
        gps (gps_reader.Generic): The GPS reader instance.
        stop_event (Event): A threading event to signal when to stop.
    """
    print(f"{'influx_write_thread':<20}: Starting...")
    dotenv.load_dotenv()
    token = os.getenv("INFLUXDB_TOKEN")
    org = "GPSSensorData"
    host = "https://us-east-1-1.aws.cloud2.influxdata.com"
    client = InfluxDBClient3(host=host, token=token, org=org)
    ubr = gps.get_reader()

    while not stop_event.is_set():
        try:
            _, parsed = ubr.read()

            if parsed and parsed.identity == 'NAV-PVT':
                points = Point("metrics").tag("device", gps_type)
                
                if parsed.gnssFixOk:
                    points.field("latitude", parsed.lat) \
                          .field("longitude", parsed.lon) \
                          .field("altitude_m", parsed.hMSL/1000) \
                          .field("ground_speed_ms", parsed.gSpeed / 1000) \
                          .field("ground_heading_deg", parsed.headMot) \
                          .field("horizontal_accuracy_m", parsed.hAcc/1000) \
                          .field("vertical_accuracy_m", parsed.vAcc/1000) \
                          .field("speed_accuracy_ms", parsed.sAcc/1000) \
                          .field("heading_accuracy_deg", parsed.headAcc)
                    print(f"{'influx_write_thread':<20}: Latitude: {parsed.lat}")
                    print(f"{'influx_write_thread':<20}: Longitude: {parsed.lon}")
                # Log fix type and status
                points.field("fix_type_int", int(parsed.fixType)) \
                        .field("fix_ok_int", int(parsed.gnssFixOk)) \
                        .field('carrier_phase_range_int', int(parsed.carrSoln))

                if parsed.validTime and parsed.validDate:
                    dt = datetime(
                        year=parsed.year, month=parsed.month, day=parsed.day,
                        hour=parsed.hour, minute=parsed.min, second=parsed.second,
                        tzinfo=timezone.utc
                    )
                    points.time(int(dt.timestamp() * 1e9))

                client.write(database="GPS", record=points, write_precision="s")
                print(f"{'influx_write_thread':<20}: Wrote valid NAV-PVT data to InfluxDB.")
                print(f'Carrier phase: {parsed.carrSoln}')
                
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            print(f"{'influx_write_thread':<20}: Error: {e}. Re-initializing...")
            # Attempt to re-initialize connections on error
            client = InfluxDBClient3(host=host, token=token, org=org)
            ubr = gps.get_reader()
            
    gps.close_serial()
    client.close()

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
    
    # Configure GPS type
    GPS_TYPE = "sparkfun"
    config_msg = None
    match GPS_TYPE:
        case "budget":
            gps = gps_reader.Budget()
            config_msg = gps.get_config_msg()
        case "premium":
            gps = gps_reader.Premium()
            config_msg = gps.get_config_msg()
        case "sparkfun":
            gps = gps_reader.SparkFun()
            config_msg = u_center_config.convert_u_center_config('../R_Config.txt')
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
                    args=(gnss_rtcm_queue, gps, stop_event, GPS_TYPE),
                    daemon=True
                )
            )
    
    thread_pool.append(
        Thread(
            target=influx_write_thread,
            args=(GPS_TYPE, gps, stop_event),
            daemon=True
        )
    )
    # Uncomment Below to include a stopwatch in the CLI that will show the
    # start and stop UTC time along with the total seconds.
    thread_pool.append(
        Thread(
            target=stopwatch,
            args=(stop_event,),
            daemon=True
        )
    )

    # Configure the receiver
    try:
        nar= u_center_config.send_config(config_msg, gps.ser)
        if not nar:
            print('ERROR writing config')
            return
    except Exception as e:
        print(f'Unexpected Error when writing config: {e}')
        return

    # Start the threads
    for t in thread_pool:
        t.start()

    print(f"{'main_thread':<20}: Threads started, press CTRL-C to terminate...")
    
    try:
        while not stop_event.is_set():
            sleep(1)
            
    except (KeyboardInterrupt, SystemExit):
        stop_event.set()
        print(f"\n{'main_thread':<20}: Termination signal received, shutting down threads...")

    for t in thread_pool:
        t.join()

    print(f"{'main_thread':<20}: All threads have finished.")

if __name__ == "__main__":
    app()
    print(f"{'main_thread':<20}: NTRIP Client terminated.")