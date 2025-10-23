from serial import Serial
from serial.tools.list_ports import comports
from pyubx2 import (
    UBXMessage,
    UBXReader,
    SET_LAYER_RAM,
    TXN_NONE,
)

receiver_by_pid = {
    0x01A7: {"name": "BUDGET",   "model": "u-blox 7",       "vid": 0x1546, "baud":   9600},  
    0x23A3: {"name": "PREMIUM",  "model": "u-blox M10",     "vid": 0x067B, "baud":   9600},  
    0x01A9: {"name": "SPARKFUN", "model": "u-blox ZED-F9P", "vid": 0x1546, "baud":  38400}, 
    0x7523: {"name": "SPARKFUN", "model": "u-blox ZED-FP9", "vid": 0x1A86, "baud": 460800}, # Through Sparkfun CH340C USB-Serial
}

class GPSReader:
    """A generic GPS reader for u-blox devices."""
    
    ser = None
    port = None
    gps_type = None

    def __init__(self):
        """
        Raises:
            RuntimeError: If no suitable serial port is found.
        """
        # Check every available port
        vid_list = [info["vid"] for info in receiver_by_pid.values()]
        pid_list = receiver_by_pid.keys()
        for port in comports():
            try:
                # If vid and pid are provided, check for a match
                print(f'Vid: {port.vid}, pid: {port.pid}')
                if (port.vid in vid_list and port.pid in pid_list):
                    self.port = port.device
                    self.ser = Serial(self.port, receiver_by_pid[port.pid]["baud"], timeout=1)
                    self.gps_type = receiver_by_pid[port.pid]["name"]
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
            
    def get_nav_pvt_config(self, raw=False):
        """
        Returns:
            UBXMessage: A UBXMessage to configure the receiver to output
                        NAV-PVT and RAWX messages on USB.
        """
        cfgData = [
            ("CFG_MSGOUT_UBX_NAV_PVT_USB", 0x1),
        ]
        if raw:
            cfgData.extend([
                ("CFG_MSGOUT_UBX_RXM_RAWX_USB", 0x1),
                ("CFG_MSGOUT_UBX_RXM_SFRBX_USB", 0x1),        
            ])
        return UBXMessage.config_set(
            layers=(SET_LAYER_RAM),
            transaction=TXN_NONE,
            cfgData=cfgData
        )
        
    def close_serial(self):
        """
        Closes the serial connection if it is open.
        """
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        else:
            print(f'Serial port {self.ser} was not open.')
