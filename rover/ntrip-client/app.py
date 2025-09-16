import os
import sys
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
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
import gps_reader

"""
Mount Point AUS_LOFT_GNSS 
    Distance: 7km
    Messages: https://www.use-snip.com/kb/knowledge-base/rtcm-3-message-list/
        RTCM 1074 GPS MSM4
        RTCM 1084 GLONASS MSM4
        RTCM 1094 Galileo MSM4
        RTCM 1124 BeiDou MSM4
MSM4 Components: https://www.tersus-gnss.com/tech_blog/new-additions-in-rtcm3-and-What-is-msm
    Full GPS Pseudoranges, Phaseranges, Carrier-to-Noise Ratio
"""

def rtcm_get_thread(gnss_rtcm_queue, stop_event):
    print(f"{'rtcm_get_thread':<20}: Starting...")
    gnc = GNSSNTRIPClient()
    gnc.run(
        # Public RTK
        # server="rtk2go.com",
        # mountpoint="AUS_LOFT_GNSS",
        # ntripuser="andrewvnguyen@utexas.edu",
        # Private RTK
        server="192.168.1.78",
        mountpoint="pygnssutils",
        ntripuser="test",
        # Static Stuff
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
        # print(f"{'rtcm_get_thread':<20}: Alive...")
        
def rtcm_process_thread(gnss_rtcm_queue, gps, stop_event):
    """
    THREADED
    Reads RTCM3 data from message queue and sends it to receiver.
    """
    print(f"{'rtcm_process_thread':<20}: Starting...")
    while not stop_event.is_set():
        if not gnss_rtcm_queue.empty():
            try:
                raw_data, parsed = gnss_rtcm_queue.get()
                if protocol(raw_data) == RTCM3_PROTOCOL:
                    gps.ser.write(raw_data)
                    print(f"{'rtcm_process_thread':<20}: Sent to GPS!")
            except Exception as err:
                print(f"{'rtcm_process_thread':<20}: {err}")
            gnss_rtcm_queue.task_done()
            sleep(1)
        # print(f"{'rtcm_process_thread':<20}: Alive...")
        
                
def influx_write_thread(GPS_TYPE, gps, stop_event):
    print(f"{'influx_write_thread':<20}: Starting...")
    dotenv.load_dotenv()
    token = os.getenv("INFLUXDB_TOKEN") if os.getenv("INFLUXDB_TOKEN") else 'XgXNV68VYCQHUUQrklj2FUkZ3cdKhd1xG9PxjDb3nZh36tqNkp3p10DKKdiHGYWb1ENqy27yz_q-WrR9_asA_w=='
    org = "GPSSensorData"
    host = "https://us-east-1-1.aws.cloud2.influxdata.com"
    client = InfluxDBClient3(host=host, token=token, org=org)
    client.write(database="GPS", record=Point('testing').field('message', 'Hello from RB5'), write_precision='s')
    ubr = gps.get_reader()

    try:
        while not stop_event.is_set():
            raw, parsed = ubr.read()

            if parsed is None:
                print(f"{'influx_write_thread':<20}: No data received")
            elif parsed.identity == 'NAV-PVT':
                # Log datapoint with GPS Type
                points = Point("metrics") \
                    .tag("device", GPS_TYPE)
                # Log positional data if a fix is available
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
                      .field("differential_solution_int", int(parsed.diffSoln))
                # Log true time if available
                dt = datetime(
                    year=parsed.year,
                    month=parsed.month,
                    day=parsed.day,
                    hour=parsed.hour,
                    minute=parsed.min,
                    second=parsed.second,
                    tzinfo=timezone.utc  # UBX timestamps are UTC
                )
                if parsed.validTime and parsed.validDate:
                    points.time(int(dt.timestamp() * 1e9))
                client.write(database="GPS", record=points, write_precision="s")                
                # Debug Prints
                print(f'{'influx_write_thread':<20}: {fixType_map.get(int(parsed.fixType))}')
                print(f'{'influx_write_thread':<20}: {gpsFixOk_map.get(int(parsed.gnssFixOk))}')
                print(f'{'influx_write_thread':<20}: {diffSoln_map.get(int(parsed.diffSoln))}')
                print(f'{'influx_write_thread':<20}: ValidTime: {parsed.validTime}')
                print(f'{'influx_write_thread':<20}: ValidDate: {parsed.validDate}')
                print(f"{'influx_write_thread':<20}: {dt.isoformat()}")
                
    except KeyboardInterrupt:
        print("Terminating...")
    finally:
        gps.close_serial()
        client.close()               
                
def app():
    
    print("Starting NTRIP Client...")
    
    thread_pool = []
    gps = None
    stop_event = Event()
    
    # Configure GPS
    # GPS_TYPE = "budget"
    # GPS_TYPE = "premium"
    GPS_TYPE = "sparkfun"
      
    match GPS_TYPE:
        case "budget":
            gps = gps_reader.Budget()
        case "premium":
            gps = gps_reader.Premium()
        case "sparkfun":
            gps = gps_reader.SparkFun()
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
                    args=(gnss_rtcm_queue, gps, stop_event),
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
    # start the threads
    for t in thread_pool:
        t.start()

    print(f"{'main_thread':<20}: NTRIP client and processor threads started - press CTRL-C to terminate...")
    
    # Idle Parent Thread
    try:
        while True:
            # Interrupt interval
            sleep(10)
            # print(f"{'main_thread':<20}: Alive...")
            
    except KeyboardInterrupt:
        # stop the threads
        stop_event.set()
        print(f"{'main_thread':<20}: NTRIP client terminated by user, waiting for data processing to complete...")

    # wait for final queued tasks to complete
    for t in thread_pool:
        t.join()

    print(f"{'main_thread':<20}: Data processing complete.")

if __name__ == "__main__":
    print(f"{'main_thread':<20}: Starting NTRIP Client...")
    app()
    
print(f"{'main_thread':<20}: NTRIP Client terminated.")