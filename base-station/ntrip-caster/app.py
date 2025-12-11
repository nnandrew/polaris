"""
NTRIP Caster Application.

This script initializes a GPS device, performs auto-calibration via PPP, and
starts the `gnssserver` process to broadcast GNSS data as an NTRIP caster.

The application performs the following steps:
1. Initializes a GPS reader to communicate with the GNSS device.
2. Reads the base station configuration from `BS_Config.txt` and sends it to the device.
3. Starts a `read_messages_thread` to log raw UBX data for PPP and send telemetry to InfluxDB.
4. Starts a `ConfigServer` (Flask app) for dynamic remote configuration.
5. Starts a `PPPProcessor` to automatically determine the fixed position.
6. Constructs and executes a `gnssserver` command to start the NTRIP caster.
"""

from queue import Queue
from threading import Event, Thread
from ppp_processor import PPPProcessor
import subprocess
import pty
import sys
import os

from pyubx2 import UBXReader, protocol, RTCM3_PROTOCOL, UBX_PROTOCOL
from pyubx2.ubxhelpers import gnss2str
from influxdb_client_3 import Point
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

def read_messages_thread(ubx_config, rtcm_fd, latest_pos, ppp_done, stop_event):
    """
    Reads UBX messages from the GPS device.
    
    This thread performs three main functions:
    1. Forwards RTCM3 messages to the pty for the NTRIP caster.
    2. Logs raw UBX messages to a file for the PPP Processor to use.
    3. Sends telemetry data (satellite counts, position) to InfluxDB.
    """
    
    print(f"{'read_messages_thread':<20}: Starting...")
    
    def get_repeated_field(parsed_data, field_name, index):
        return getattr(parsed_data, f"{field_name}_{index+1:02d}")

    if os.path.exists("./shared/station.ubx"):
        os.remove("./shared/station.ubx")

    ubr = UBXReader(ubx_config.ser)
    while not stop_event.is_set():
        raw_data, parsed_data = ubr.read()
        if raw_data:
            if protocol(raw_data) == RTCM3_PROTOCOL:
                os.write(rtcm_fd, raw_data)
            if protocol(raw_data) == UBX_PROTOCOL:
                # print(parsed_data.identity)
                if not ppp_done.is_set():
                    with open("./shared/station.ubx", "ab") as f:
                        f.write(raw_data)
                else:
                    os.remove("./shared/station.ubx")
                match parsed_data.identity:
                    case 'ACK-ACK':
                        ubx_config.set_ack()
                    case 'ACK-NAK':
                        ubx_config.set_nack()
                    case 'RXM-RAWX':
                        # Already logged to file
                        pass
                    case 'RXM-SFRBX':
                        # Already logged to file
                        pass
                    case 'NAV-PVT':
                        # Use for debugging purposes
                        point = Point("station_telemetry").field("latitude", parsed_data.lat) \
                                                          .field("longitude", parsed_data.lon) \
                                                          .field("height", parsed_data.height)
                        InfluxWriter.batch_write(point)
                        # Pass latest position to PPP processor
                        if latest_pos.full():
                            latest_pos.get_nowait()
                        latest_pos.put((parsed_data.lat, parsed_data.lon, parsed_data.height))
                    case 'NAV-SAT':
                        # Use for debugging purposes            
                        num_sats = 0
                        num_sats_visible = 0
                        num_sats_code_locked = 0
                        num_sats_carrier_locked = 0
                        for i in range(parsed_data.numSvs):
                            constellation = gnss2str(get_repeated_field(parsed_data, "gnssId", i))
                            qualityInd = get_repeated_field(parsed_data, "qualityInd", i)
                            if constellation != "SBAS":
                                if qualityInd >= 5:
                                    num_sats_carrier_locked += 1
                                if qualityInd >= 4:
                                    num_sats_code_locked += 1
                                if qualityInd >= 2:
                                    num_sats_visible += 1
                            num_sats += 1
                        point = Point("station_telemetry") \
                            .field("num_sats_tracked", int(num_sats)) \
                            .field("num_sats_visible", int(num_sats_visible)) \
                            .field("num_sats_code_locked", int(num_sats_code_locked)) \
                            .field("num_sats_carrier_locked", int(num_sats_carrier_locked))
                        InfluxWriter.batch_write(point)
                        # print(f"{'read_messages_thread':<20}:  Visible: {num_sats_visible}/{num_sats}, Code Locked: {num_sats_code_locked}/{num_sats_visible}, Carrier Locked: {num_sats_carrier_locked}/{num_sats_visible}")
    
    print(f"{'read_messages_thread':<20}: Stopping...")

def main():
    """
    Initializes the GPS, gets the IP address, and starts the gnssserver.
    """
    
    print("Starting Polaris NTRIP Caster...")
    
    # Initialize GPS Reader and serial connection
    gps = GPSReader()
    fds = []
    rtcm_fd, rtcm_slave_fd = pty.openpty()
    rtcm_port = os.ttyname(rtcm_slave_fd)
    print(f"Forwarding RTCM to: {rtcm_port}")
    fds.append(rtcm_fd)
    fds.append(rtcm_slave_fd)
    
    # Initialize UBX Config
    ubx_config = UBXConfig(gps.ser)
    latest_pos = Queue(maxsize=1)
    ppp_done = Event()
    stop_event = Event()
    read_thread = Thread(
        target=read_messages_thread, 
        args=(ubx_config, rtcm_fd, latest_pos, ppp_done, stop_event), 
        daemon=True
    )
    read_thread.start()
    
    # Send base station configuration
    config_msg = ubx_config.convert_u_center_config('BS_Config.txt')
    success, msg = ubx_config.send_config(config_msg)
    if success:
        print("\n\nBase station configured successfully.\n\n")
    else:
        print(f"\n\nFailed to configure base station: {msg}\n\n")
    
    # Start the config server thread
    ppp_stop_event = Event()
    ConfigServer(ubx_config, is_base_station=True, ppp_stop_event=ppp_stop_event).run()
    
    # Start PPP manager
    PPPProcessor(ubx_config, latest_pos, ppp_done, ppp_stop_event).run()
    
    # Start the gnssserver NTRIP caster process
    process = subprocess.Popen([
        "gnssserver",
        "--inport", rtcm_port,
        "--timeout", "10",
        "--hostip", "0.0.0.0",   # Bind to all interfaces
        "--outport", "2101",
        "--ntripmode", "1",      # NTRIP Caster mode
        "--protfilter", "4",     
        "--format", "2",         # Raw binary
        "--ntripuser", "polaris",
        "--ntrippassword", "none",
        "--verbosity", "2",      # Verbose output
    ])
    
    # Wait for the process to complete
    print("Base station running - press CTRL-C to terminate...")
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping gnssserver...")
        process.terminate()
        stop_event.set()
        ppp_stop_event.set()
        read_thread.join()
    finally:
        for fd in fds:
            os.close(fd)
        gps.close_serial()
        
if __name__ == "__main__":
    main()
