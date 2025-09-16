import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
import gps_reader
import ip_getter

def main():
    gps = gps_reader.SparkFun()
    gps.get_reader()
    com = gps.port
    IPAddr = ip_getter.get_local_ip()
    IPAddr = "0.0.0.0"
    print(f"Using IP address: {IPAddr}")

    # Define the command and arguments
    cmd = [
        "gnssserver",
        "--inport", com,
        "--hostip", IPAddr,
        "--outport", "2101",
        "--ntripmode", "1",
        "--protfilter", "4",
        "--format", "2",
        "--ntripuser", "test",
        "--ntrippassword", "none",
        "--verbosity", "2",
    ]

    # Start the process and stream output
    process = subprocess.Popen(
        cmd
        # ,
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
        # text=True  # decode bytes to str
    )

    print("gnssserver started (PID:", process.pid, ")")

    # Stream logs in real time
    # try:
    #     for line in process.stdout:
    #         print(line, end="")  # already includes newline
    # except KeyboardInterrupt:
    #     print("\nStopping gnssserver...")
    #     process.terminate()
    process.wait()

    # start
    print("Base station running - press CTRL-C to terminate...")


if __name__ == "__main__":
    main()