from serial.tools.list_ports import comports
from serial import Serial
from pyubx2 import (
    UBXMessage,
    SET,
    SET_LAYER_RAM,
    SET_LAYER_BBR,
    TXN_NONE,
)

# A dictionary mapping USB Product IDs (PIDs) to receiver information.
# This allows the GPSReader to automatically identify the connected device
# and configure the serial connection with the correct baud rate.
receiver_by_pid = {
    0x01A7: {"name": "BUDGET",   "model": "u-blox 7",       "vid": 0x1546, "baud":   9600},  
    0x23A3: {"name": "PREMIUM",  "model": "u-blox M10",     "vid": 0x067B, "baud":  38400},  
    0x01A9: {"name": "SPARKFUN", "model": "u-blox ZED-F9P", "vid": 0x1546, "baud":  38400}, 
    0x7523: {"name": "SPARKFUN", "model": "u-blox ZED-FP9", "vid": 0x1A86, "baud": 460800}, # Through Sparkfun CH340C USB-Serial
}

class GPSReader:
    """
    A generic GPS reader for u-blox devices.

    This class automatically detects and connects to a supported u-blox GPS
    receiver. It iterates through the available serial ports and checks the
    Vendor ID (VID) and Product ID (PID) to identify the device. Once a
    matching device is found, it opens a serial connection with the appropriate
    baud rate.
    """
    
    ser = None
    port = None
    baud = 9600
    gps_type = None

    def __init__(self):
        """
        Initializes the GPSReader and connects to the first available GPS 
        devicebased on the VID and PID.

        Raises:
            RuntimeError: If no suitable serial port is found.
        """
        # Check every available port for a matching VID and PID.
        vid_list = [info["vid"] for info in receiver_by_pid.values()]
        pid_list = receiver_by_pid.keys()
        for port in comports():
            try:
                # print(f'Vid: {port.vid}, pid: {port.pid}')
                if (port.vid in vid_list and port.pid in pid_list):
                    
                    self.port = port.device
                    self.baud = receiver_by_pid[port.pid]["baud"]
                    self.ser = Serial(self.port, self.baud, timeout=1)
                    self.gps_type = receiver_by_pid[port.pid]["name"]
                    print(f'Connected to {self.gps_type} GPS on port {self.port} at {self.baud} baud.')
                    return
            except Exception as e:
                print(f"Error opening port {port.device}: {e}")

        if self.ser is None:
            raise RuntimeError('No serial port found')

    def get_nav_pvt_config(self, uart=False) -> UBXMessage:
        """
        Returns a UBXMessage to configure the receiver to output NAV-PVT
        messages on the USB port.

        Args:
            uart (bool): If True, configures for UART1 output instead of USB.
        Returns:
            UBXMessage: A UBX-CFG-MSG message to enable NAV-PVT output.
        """
        if uart:
            return UBXMessage.config_set(
                layers=(SET_LAYER_RAM | SET_LAYER_BBR),
                transaction=TXN_NONE,
                cfgData=[("CFG_MSGOUT_UBX_NAV_PVT_UART1", 0x1)],
            )
        else:
            return UBXMessage(
                "CFG",
                "CFG-MSG",
                SET,
                msgClass=0x01,     # NAV
                msgID=0x07,        # PVT (Position Velocity Time Solution)
                rateUSB=1,         # Enable on USB
            )
        
    def close_serial(self):
        """
        Closes the serial connection if it is open.
        """
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        else:
            print(f'Serial port {self.ser} was not open.')
