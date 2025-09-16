from pyubx2 import (
    UBXMessage, 
    UBXReader, 
    SET,
    protocol
)
from threading import Event, Thread
import serial
from serial.tools.list_ports import comports
import socket
import subprocess


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
            if vid and pid: # Only check if vid and pid were passed
                if port.vid == vid and port.pid == pid:
                    print('Found desired serial port')
                    return port
                else:
                    print('Port was not valid, so viewing next available')
            else: # assume first opened port was correct and exit loop
                break
        except Exception as e:
            print(e)


def main():
    comport = get_serial().name

    hostname = socket.gethostname()
    IPAddr = socket.gethostbyname(hostname)

    print(f'ip address: {IPAddr}')

    # Define the command and arguments
    cmd = [
        "gnssserver",
        "--inport", comport,
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