from serial import Serial
from serial.tools.list_ports import comports
from pyubx2 import UBXMessage, UBXReader, SET

class Generic:
    
    ser = None
    port = None
    
    def get_reader(self, baud, msgs, vid=None, pid=None) -> UBXReader:

        # Configure serial connection
        ports = comports()
        # Check every available port
        for port in ports:
            print(f'Trying to open this port for serial: {port}')
            print(f'''
                `Port details: {port.description}, {port.device}, {port.name}, {port.usb_description()},
                {port.vid}, {port.pid}, 
            '''.strip())
            try:
                self.port = port.device
                print(self.port)
                self.ser = Serial(self.port, baud, timeout=1)
                print(f'This is the name of the opened serial port: {self.ser.name}')
                # A Serial point was found, and opened, but was it the right one?
                if vid and pid: # Only check if vid and pid were passed
                    if port.vid == vid and port.pid == pid:
                        print('Found desired serial port')
                        break
                    else:
                        print('Port was not valid, so viewing next available')
                else: # assume first opened port was correct and exit loop
                    break
            except Exception as e:
                print(e)

        if self.ser is None:
            raise RuntimeError('No serial port found')

        # Configure USB GPS
        for msg in msgs:
            self.ser.write(msg.serialize())
        return UBXReader(self.ser)

    def close_serial(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        else:
            print(f'Serial port ${self.ser} not closed')

class Budget(Generic):
    def get_reader(self) -> UBXReader:
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
        return Generic.get_reader(self, BAUD_RATE, msgs)

class Premium(Generic):
    def get_reader(self) -> UBXReader:
        BAUD_RATE = 38400
        msgs = [
            UBXMessage(
                "CFG",
                "CFG-MSG",
                SET,
                msgClass=0x01,     # NAV
                msgID=0x07,        # PVT (Position Velocity Time Solution) 
                rateUART1=1,       # Enable on USB 
            ),
        ]
        return Generic.get_reader(self, BAUD_RATE, msgs)
        
class SparkFun(Generic):
    def get_reader(self) -> UBXReader:
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
        return Generic.get_reader(self, BAUD_RATE, msgs, vid, pid)