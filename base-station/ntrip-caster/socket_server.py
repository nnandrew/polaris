from queue import Queue, Empty
from threading import Event
from time import sleep
from pygnssutils import GNSSSocketServer
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


def run_station():
    hostname = socket.gethostname()
    IPAddr = socket.gethostbyname(hostname)
    
    port = get_serial()
    ser = serial.Serial(port.name, 115200, timeout=1)

    # while True:
    #     data = ser.read(200)
    #     if data:
    #         print(f"Read {len(data)} bytes: {data[:20]}...")

    # create server
    server = GNSSSocketServer(
        # app=
        stream=ser,
        ipprot='IPv4',
        hostip=IPAddr,
        outport=2101,
        maxclients=5,
        ntripmode=1,
        ntripversion="2.0",
        ntripuser="test@utexas.edu",
        ntrippassword="none"
        )

    # run it
    server.run()
    print(f"server created")


def log_messages(log_queue: Queue, stop_event: Event):
    print("Logging thread started")
    with open("log.rtcm", "a+") as f:
        while not stop_event.is_set():
            try:
                raw, parsed = log_queue.get(timeout=1)
                print(f"Got message of {len(raw)} bytes")
                f.write(raw)
                log_queue.task_done()
            except Empty:
                continue
    print(f"not in loop")


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
    # initialize structure
    log_queue = Queue()
    stop_event = Event()

    # define threads (terminated by user)
    logt = Thread(
        target=log_messages,
        args=(log_queue, stop_event),
        daemon=True
    )

    run_station()
    
    # start thread
    logt.start()



    # start
    print("Base station running - press CTRL-C to terminate...")
    
    try:
        while True:
            sleep(3)
    except KeyboardInterrupt:
        # stop thread
        stop_event.set()
        print("Base station terminated by user.")
        
    logt.join()
    print(f"Base station processes complete.")

if __name__ == "__main__":
    main()