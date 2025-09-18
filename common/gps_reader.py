from serial import Serial
from serial.tools.list_ports import comports
from pyubx2 import UBXMessage, UBXReader, SET

class Generic:
    """A generic GPS reader for u-blox devices."""
    
    ser = None
    port = None
    
    def get_reader(self, baud, msgs, vid=None, pid=None) -> UBXReader:
        """Finds, configures, and returns a UBXReader for a connected u-blox device.

        This method scans available serial ports, identifies the correct one (optionally
        by vendor and product ID), configures it with the provided settings, and
        returns a UBXReader object for data consumption.

        Args:
            baud (int): The baud rate for the serial connection.
            msgs (list): A list of UBXMessage objects to configure the device.
            vid (int, optional): The vendor ID of the USB device. Defaults to None.
            pid (int, optional): The product ID of the USB device. Defaults to None.

        Returns:
            UBXReader: A UBXReader instance for the configured serial port.

        Raises:
            RuntimeError: If no suitable serial port is found.
        """
        # Configure serial connection
        ports = comports()
        # Check every available port
        for port in ports:
            try:
                # If vid and pid are provided, check for a match
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

        # Configure USB GPS
        for msg in msgs:
            self.ser.write(msg.serialize())
        return UBXReader(self.ser)

    def close_serial(self):
        """Closes the serial connection if it is open."""
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        else:
            print(f'Serial port {self.ser} was not open.')

class Budget(Generic):
    """A GPS reader specifically for the u-blox 7 module."""
    def get_reader(self) -> UBXReader:
        """Configures and returns a UBXReader for a budget device.

        Returns:
            UBXReader: A UBXReader instance for the budget GPS device.
        """
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
        return super().get_reader(BAUD_RATE, msgs)

class Premium(Generic):
    """A GPS reader specifically for the u-blox M10 module."""
    def get_reader(self) -> UBXReader:
        """Configures and returns a UBXReader for a premium device.

        Returns:
            UBXReader: A UBXReader instance for the premium GPS device.
        """
        BAUD_RATE = 38400
        msgs = [
            UBXMessage(
                "CFG",
                "CFG-MSG",
                SET,
                msgClass=0x01,     # NAV
                msgID=0x07,        # PVT (Position Velocity Time Solution) 
                rateUART1=1,       # Enable on USB?
            ),
        ]
        return super().get_reader(BAUD_RATE, msgs)
        
class SparkFun(Generic):
    """A GPS reader specifically for the u-blox ZED-FP9 module."""
    def get_reader(self) -> UBXReader:
        """Configures and returns a UBXReader for a SparkFun device.

        This method identifies the SparkFun device by its specific vendor and
        product ID.

        Returns:
            UBXReader: A UBXReader instance for the SparkFun GPS device.
        """
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
        return super().get_reader(BAUD_RATE, msgs, vid, pid)