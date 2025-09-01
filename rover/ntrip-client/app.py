from queue import Queue
from threading import Event, Thread
from time import sleep
from pygnssutils import GNSSNTRIPClient
from pprint import pprint
import ecef_solver
import gnss_reader
import msm_parser
import gps_reader
from pyubx2 import (
    UBXMessage, 
    UBXReader, 
    SET,
    protocol,
    NMEA_PROTOCOL,
    UBX_PROTOCOL,
    RTCM3_PROTOCOL
)
from pyrtcm import RTCM_MSGIDS
from serial import Serial
import os
from serial.tools.list_ports import comports

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

def ntrip_thread(out_queue: Queue, stop_event: Event):

    gnc = GNSSNTRIPClient()
    gnc.run(
        # Required Configuration
        server="rtk2go.com",
        port=2101,
        https=0,
        mountpoint="AUS_LOFT_GNSS",
        datatype="RTCM",
        ntripuser="andrewvnguyen@utexas.edu",
        ntrippassword="none",
        output=out_queue,
        # DGPS Configuration (unused)
        ggainterval=-1,
        ggamode=1,  # fixed rover reference coordinates
        reflat=0.0,
        reflon=0.0,
        refalt=0.0,
        refsep=0.0,
    )
    while not stop_event.is_set():
        sleep(3)
        
def data_thread(out_queue: Queue, stop_event: Event):

    while not stop_event.is_set():
        while not out_queue.empty():
            raw, parsed = out_queue.get()
            # if parsed.ismsm:
            if parsed.identity == "1074":
                rtcm_metadata, rtcm_sats = msm_parser.parse(parsed)
                pprint(rtcm_metadata)
                pprint(rtcm_sats)
                rover_ecef = gnss_reader.getECEF()
                rover_sats = gnss_reader.getSatelliteInfo()
                # pprint(rover_sats)
                calculated_ecef = ecef_solver.solve(rover_ecef, rover_sats, rtcm_metadata, rtcm_sats)
                pprint(rover_ecef)
                pprint(calculated_ecef)
            out_queue.task_done()
        sleep(1)
        
def get_serial():

    BAUD_RATE = 38400
    msgs = [
        UBXMessage(
            "CFG",
            "CFG-MSG",
            SET,
            msgClass=0x01,     # NAV
            msgID=0x07,        # PVT (Position Velocity Time Solution) 
            rateUSB=1,         # Enable on USB 
        ),
    ]
    # Got the values from listing all ports and printing their pid and vid
    vid = 5446
    pid = 425

    # Configure serial connection
    ports = comports()
    ser = None

    # Check every available port
    for port in ports:
        print(f'Trying to open this port for serial: {port}')
        print(f'''
Port details: {port.description}, {port.device}, {port.name}, {port.usb_description()},
{port.vid}, {port.pid}, 
''')
        try:
            serial_port = port.device
            print(serial_port)
            ser = Serial(serial_port, BAUD_RATE, timeout=1)
            print(f'This is the name of the opened serial port: {ser.name}')
            # A Serial point was found, and opened, but was it the right one?
            if vid and pid: # Only check if vid and pid were passed
                if port.vid == vid and port.pid == pid:
                    print('Found desired serial port')
                    return ser
                else:
                    print('Port was not valid, so viewing next available')
            else: # assume first opened port was correct and exit loop
                break
        except Exception as e:
            print(e)

    if ser is None:
        raise RuntimeError('No serial port found')
    else:
        self.ser = ser

def send_gnss(stream, stopevent, inqueue):
    """
    THREADED
    Reads RTCM3 data from message queue and sends it to receiver.
    """

    while not stopevent.is_set():
        try:
            raw_data, parsed_data = inqueue.get()
            if protocol(raw_data) == RTCM3_PROTOCOL:
                print(
                    f"NTRIP>> {parsed_data.identity} {RTCM_MSGIDS[parsed_data.identity]}"
                )
                stream.write(raw_data)
                print("Sent Data to SparkFun")
        except Exception as err:
            print(f"Something went wrong in send thread {err}")
            break

def gnss_read(ubr, stopevent):
    while not stopevent.is_set():
        raw_data, parsed_data = ubr.read()

        if parsed_data is None:
            print("No data received")
        elif parsed_data.identity == 'NAV-PVT':
            print('Received NAV-PVT')
            # Log parsed data to InfluxDB
            if parsed_data.fixType != 0:
                # database="GPS"
                # points = Point("metrics") \
                #     .tag("device", "budget") \
                #     .field("latitude", parsed_data.lat) \
                #     .field("longitude", parsed_data.lon) \
                #     .field("altitude_m", parsed_data.hMSL/1000) \
                #     .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                #     .field("ground_heading_deg", parsed_data.headMot) \
                #     .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                #     .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                #     .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                #     .field("heading_accuracy_deg", parsed_data.headAcc)
                # client.write(database=database, record=points, write_precision="s")
                print(f"Latitude: {parsed_data.lat}")
                print(f"Longitude: {parsed_data.lon}")
            else:
                print(f'Parsed data does not have fix type set: {parsed_data.fixType}')
        # else:
        #     print(f'Ignoring data with identity: {parsed_data.identity}')

def main():
    
    # initialize structures
    out_queue = Queue()
    stop_event = Event()

    gps = gps_reader.SparkFun()
    ser = get_serial()
    ubr = UBXReader(ser)

    # define the threads which will run in the background until terminated by user
    dt = Thread(
        target=data_thread,
        args=(out_queue, stop_event),
        daemon=True
    )
    nt = Thread(
        target=ntrip_thread,
        args=(out_queue, stop_event),
        daemon=True
    )
    send_thread = Thread(
        target=send_gnss,
        args=(ser, stop_event, out_queue),
        daemon=True
    )
    
    read_thread = Thread(
        target=gnss_read,
        args=(ubr, stop_event),
        daemon=True
    )

    # start the threads
    dt.start()
    nt.start()
    send_thread.start()
    read_thread.start()

    print("NTRIP client and processor threads started - press CTRL-C to terminate...")
    
    # Idle Parent Thread
    try:
        while True:
            sleep(3)
    except KeyboardInterrupt:
        # stop the threads
        stop_event.set()
        print("NTRIP client terminated by user, waiting for data processing to complete...")

    # wait for final queued tasks to complete
    nt.join()
    dt.join()
    send_thread.join()
    read_thread.join()

    print(f"Data processing complete.")

if __name__ == "__main__":
    main()