import os
import dotenv
import gps_reader
from queue import Queue
from time import sleep
from pygnssutils import GNSSNTRIPClient
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
        server="100.70.35.29",
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
                raw_data, parsed_data = gnss_rtcm_queue.get()
                if protocol(raw_data) == RTCM3_PROTOCOL:
                    gps.ser.write(raw_data)
                    print(f"{'rtcm_process_thread':<20}: Sent to GPS!")
                    # rtcm_metadata, rtcm_sats = msm_parser.parse(parsed)
                    # pprint(rtcm_metadata)
                    # pprint(rtcm_sats)
                    # rover_ecef = gnss_reader.getECEF()
                    # rover_sats = gnss_reader.getSatelliteInfo()
                    # # pprint(rover_sats)
                    # calculated_ecef = ecef_solver.solve(rover_ecef, rover_sats, rtcm_metadata, rtcm_sats)
                    # pprint(rover_ecef)
                    # pprint(calculated_ecef)
            except Exception as err:
                print(f"{'rtcm_process_thread':<20}: {err}")
            gnss_rtcm_queue.task_done()
            sleep(1)
        # print(f"{'rtcm_process_thread':<20}: Alive...")
        
                
def influx_write_thread(gps, stop_event):
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
            raw_data, parsed_data = ubr.read()

            if parsed_data is None:
                print(f"{'influx_write_thread':<20}: No data received")
            elif parsed_data.identity == 'NAV-PVT':
                # Log parsed data to InfluxDB
                if parsed_data.fixType != 0:
                    database="GPS"
                    points = Point("metrics") \
                        .tag("device", "budget") \
                        .field("latitude", parsed_data.lat) \
                        .field("longitude", parsed_data.lon) \
                        .field("altitude_m", parsed_data.hMSL/1000) \
                        .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                        .field("ground_heading_deg", parsed_data.headMot) \
                        .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                        .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                        .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                        .field("heading_accuracy_deg", parsed_data.headAcc)
                    client.write(database=database, record=points, write_precision="s")
                    fix_map = {
                        0: "No fix",
                        1: "Dead reckoning only", 
                        2: "2D fix",
                        3: "3D fix",
                        4: "GNSS + dead reckoning combined",
                        5: "Time only fix"
                    }
                    diff_map = {
                        0: "No differential corrections",
                        1: "Differential corrections applied"
                    }
                    print(f"{'influx_write_thread':<20}: {fix_map.get(int(parsed_data.fixType))}")
                    print(f"{'influx_write_thread':<20}: {diff_map.get(parsed_data.diffSoln)}")
                    print(f"{'influx_write_thread':<20}: Latitude: {parsed_data.lat}")
                    print(f"{'influx_write_thread':<20}: Longitude: {parsed_data.lon}")
                # else:
                    # print(f'Parsed data does not have fix type set: {parsed_data.fixType}')
            # else:
            #     print(f'Ignoring data with identity: {parsed_data.identity}')
            # print(f"{'influx_write_thread':<20}: Alive...")
                
    except KeyboardInterrupt:
        print("Terminating...")
    finally:
        gps.close_serial()
        client.close()               
                
def app():
    
    print("Starting NTRIP Client...")
    
    # initialize structures
    gnss_rtcm_queue = Queue()
    stop_event = Event()
    
    # Configure GPS
    # gps = gps_reader.Budget()
    # gps = gps_reader.Premium()
    gps = gps_reader.SparkFun()

    # define the threads which will run in the background until terminated by user
    nt = Thread(
        target=rtcm_get_thread,
        args=(gnss_rtcm_queue, stop_event),
        daemon=True
    )
    pt = Thread(
        target=rtcm_process_thread,
        args=(gnss_rtcm_queue, gps, stop_event),
        daemon=True
    )
    it = Thread(
        target=influx_write_thread,
        args=(gps, stop_event),
        daemon=True
    )
    
    # # start the threads
    nt.start()
    pt.start()
    it.start()

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
    nt.join()
    pt.join()
    it.join()

    print(f"{'main_thread':<20}: Data processing complete.")

if __name__ == "__main__":
    print(f"{'main_thread':<20}: Starting NTRIP Client...")
    app()
    
print(f"{'main_thread':<20}: NTRIP Client terminated.")