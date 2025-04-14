from serial import Serial
from serial.tools.list_ports import comports
from pyubx2 import UBXMessage, UBXReader, SET

class Generic:
    
    ser = None
    
    def getReader(self, baud, msgs):

        # Configure serial connection
        ports = comports()
        serial_port = ports[0].device
        ser = Serial(serial_port, baud, timeout=1)

        # Configure USB GPS
        for msg in msgs:
            ser.write(msg.serialize())
        return UBXReader(ser)

    def closeSerial(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

class Budget(Generic):
    def getReader(self):  
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
        return Generic.getReader(self, BAUD_RATE, msgs)
        
class Premium(Generic):
    def getReader(self):  
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
        return Generic.getReader(self, BAUD_RATE, msgs)
        
class Sparkfun(Generic):    
    def getReader(self):  
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
        return Generic.getReader(self, BAUD_RATE, msgs)