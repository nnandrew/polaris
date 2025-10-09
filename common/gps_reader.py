from serial import Serial
from serial.tools.list_ports import comports
from pyubx2 import UBXMessage, UBXReader, SET

class Generic:
    """A generic GPS reader for u-blox devices."""
    
    ser = None
    port = None

    def __init__(self, vid=None, pid=None, baud=None):
        self.init_reader(baud, vid, pid)

    def init_reader(self, baud, vid=None, pid=None):
        """
            This method scans available serial ports, identifies the correct one (optionally
            by vendor and product ID).

            Args:
                baud (int): The baud rate for the serial connection.
                vid (int, optional): The vendor ID of the USB device. Defaults to None.
                pid (int, optional): The product ID of the USB device. Defaults to None.

            Raises:
                RuntimeError: If no suitable serial port is found.
        """
        # Configure serial connection
        ports = comports()
        # Check every available port
        for port in ports:
            try:
                # If vid and pid are provided, check for a match
                print(f'Vid: {port.vid}, pid: {port.pid}')
                if (vid and pid) and (port.vid != vid or port.pid != pid):
                    continue
                self.port = port.device
                self.ser = Serial(self.port, baud, timeout=1)
                # If we reach here, a port has been successfully opened.
                break
            except Exception as e:
                print(f"Error opening port {port.device}: {e}")

        if self.ser is None:
            raise RuntimeError('No serial port found')


    def get_reader(self) -> UBXReader:
        """
        Returns:
            UBXReader: A UBXReader instance for the configured serial port.
        """
        return UBXReader(self.ser)

    def close_serial(self):
        """Closes the serial connection if it is open."""
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        else:
            print(f'Serial port {self.ser} was not open.')

class Budget(Generic):
    """A GPS reader specifically for the u-blox 7 module."""
    def __init__(self):
        """Finds and opens a serial port for a premium device.

        This method identifies the premium device by its specific vendor and
        product ID.
        """
        BAUD_RATE = 38400
        vid = 0x1546
        pid = 0x01A7
        super().__init__(
            vid=vid,
            pid=pid,
            baud=BAUD_RATE
        )

    def get_config_msg(self):
        """
        Returns the UBX-CFG for the device
        """
        return UBXMessage(
                "CFG",
                "CFG-MSG",
                SET,
                msgClass=0x01,     # NAV
                msgID=0x07,        # PVT (Position Velocity Time Solution)
                rateUSB=1,         # Enable on USB
            )

class Premium(Generic):
    """A GPS reader specifically for the u-blox M10 module."""

    def __init__(self):
        """Finds and opens a serial port for a premium device.

        This method identifies the premium device by its specific vendor and
        product ID.
        """
        BAUD_RATE = 38400
        vid = 0x067B
        pid = 0x23A3
        super().__init__(
            vid=vid,
            pid=pid,
            baud=BAUD_RATE
        )


    def get_config_msg(self):
        """
        Returns the UBX-CFG for the device
        """
        return UBXMessage(
                "CFG",
                "CFG-MSG",
                SET,
                msgClass=0x01,     # NAV
                msgID=0x07,        # PVT (Position Velocity Time Solution)
                rateUART1=1,       # Enable on USB?
            )
        
class SparkFun(Generic):
    """A GPS reader specifically for the u-blox ZED-FP9 module."""

    def __init__(self):
        """Finds and opens a serial port for a SparkFun device.

        This method identifies the SparkFun device by its specific vendor and
        product ID.
        """
        BAUD_RATE = 38400
        vid = 5446
        pid = 425
        super().__init__(
            vid=vid,
            pid=pid,
            baud=BAUD_RATE
        )