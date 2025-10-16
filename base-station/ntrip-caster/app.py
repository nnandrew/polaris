"""
NTRIP Caster Application.

This script initializes a GPS device, determines the local IP address, and
starts the `gnssserver` process to broadcast GNSS data as an NTRIP caster.
"""
import subprocess
try:
    from common import gps_reader, ip_getter, u_center_config
except ImportError:
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    import gps_reader
    import ip_getter
    import u_center_config

def main():
    """
    Initializes the GPS, gets the IP address, and starts the gnssserver.
    """
    try:
        gps = gps_reader.SparkFun()
    except RuntimeError:
        gps = gps_reader.SparkFunUART1()
    config_msg = u_center_config.convert_u_center_config('../BS_Config_Fixed.txt')
    u_center_config.send_config(config_msg, gps.ser)
    com = gps.port
    gps.close_serial()
    # Binds to all available interfaces
    ip_addr = "0.0.0.0"
    print(f"Using IP address: {ip_addr}")

    # Define the command and arguments to start the NTRIP caster
    cmd = [
        "gnssserver",
        "--inport", com,
        "--hostip", ip_addr,
        "--outport", "2101",
        "--ntripmode", "1",      # NTRIP Caster mode
        "--protfilter", "4",     
        "--format", "2",         # Raw binary
        "--ntripuser", "test",
        "--ntrippassword", "none",
        "--verbosity", "2",      # Verbose output
    ]

    # Start the gnssserver process
    process = subprocess.Popen(cmd)

    print("gnssserver started (PID:", process.pid, ")")
    print("Base station running - press CTRL-C to terminate...")
    
    try:
        # Wait for the process to complete. 
        # This will block until the process is terminated.
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping gnssserver...")
        process.terminate()


if __name__ == "__main__":
    main()