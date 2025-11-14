"""
NTRIP Caster Application.

This script initializes a GPS device, determines the local IP address, and
starts the `gnssserver` process to broadcast GNSS data as an NTRIP caster.

The script performs the following steps:
1. Initializes a GPS reader to communicate with the GNSS device.
2. Reads the base station configuration from `BS_Config.txt` and sends it to the device.
3. Binds to all available network interfaces (0.0.0.0).
4. Constructs and executes a `gnssserver` command to start the NTRIP caster.
"""

from threading import Event, Thread
import subprocess
import pty
import sys
import os

from pyubx2 import UBXReader, protocol, RTCM3_PROTOCOL, UBX_PROTOCOL, NMEA_PROTOCOL
try:
    from common.ubx_config import UBXConfig
    from common.gps_reader import GPSReader
    from common.config_server import ConfigServer
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    from ubx_config import UBXConfig
    from gps_reader import GPSReader
    from config_server import ConfigServer

def read_messages_thread(ser, rtcm_fd, ack_event, nack_event, stop_event):
    print(f"{'read_messages_thread':<20}: Starting...")
    ubr = UBXReader(ser)
    while not stop_event.is_set():
        raw_data, parsed_data = ubr.read()
        if raw_data:
            if protocol(raw_data) == RTCM3_PROTOCOL:
                os.write(rtcm_fd, raw_data)
            if protocol(raw_data) == UBX_PROTOCOL:
                print(parsed_data.identity)
                match parsed_data.identity:
                    case 'ACK-ACK':
                        ack_event.set()
                    case 'ACK-NAK':
                        nack_event.set()
                    case 'NAV-PVT':
                        # Use for debugging purposes
                        pass
   
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
    print(rtcm_port)
    fds.append(rtcm_fd)
    fds.append(rtcm_slave_fd)
    ack_event = Event()
    nack_event = Event()
    stop_event = Event()
    read_thread = Thread(target=read_messages_thread, args=(gps.ser, rtcm_fd, ack_event, nack_event, stop_event), daemon=True)
    read_thread.start()
    
    # Send base station configuration
    ubx_config = UBXConfig(gps.ser)
    config_msg = ubx_config.convert_u_center_config('BS_Config.txt')
    success, msg = ubx_config.send_config(config_msg)
    if success:
        print("\n\nBase station configured successfully.\n\n")
    else:
        print(f"\n\nFailed to configure base station: {msg}\n\n")
    
    # Start the config server thread
    ConfigServer(ubx_config).run()
    
    # Define the command and arguments to start the NTRIP caster
    cmd = [
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
    ]

    # Start the gnssserver process
    process = subprocess.Popen(cmd)
    
    # Wait for the process to complete
    print("Base station running - press CTRL-C to terminate...")
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping gnssserver...")
        process.terminate()
        stop_event.set()
        read_thread.join()
    finally:
        for fd in fds:
            os.close(fd)
        gps.close_serial()
        
if __name__ == "__main__":
    main()
