from pyubx2 import (
    UBXMessage,
    SET_LAYER_RAM,
    SET_LAYER_FLASH,
    SET_LAYER_BBR,
    TXN_NONE,
    ATTTYPE,
    atttyp,
    UBX_CONFIG_DATABASE,
    UBX_PROTOCOL,
    UBXReader,
)
from threading import Event, Lock, Thread
from time import sleep
import serial

def read_messages(stream, lock, stop_event, ubx_reader, success_event):
    """
    Reads, parses and prints out incoming UBX messages
    """
    # pylint: disable=unused-variable, broad-except
    while not stop_event.is_set():
        if stream.in_waiting and (not success_event.is_set()):
            try:
                lock.acquire()
                _, parsed_data = ubx_reader.read()
                lock.release()
                if parsed_data and parsed_data.identity == 'ACK-ACK':
                    print(f'YIPPY: {parsed_data}')
                    success_event.set()
                    # break
                if parsed_data and parsed_data.identity == 'ACK-NAK':
                    print(f'ERROR: {parsed_data}')
            except Exception as err:
                print(f"\n\nSomething went wrong {err}\n\n")
                continue


def start_thread(stream, lock, stop_event, ubx_reader, success_event):
    """
    Start read thread
    """

    thr = Thread(
        target=read_messages, args=(stream, lock, stop_event, ubx_reader, success_event), daemon=True
    )
    thr.start()
    return thr


def send_message(stream, lock, message):
    """
    Send message to device
    """

    lock.acquire()
    stream.write(message.serialize())
    lock.release()

def send_config(ubx_msg, port):
    """
    A helper function to send a UBX-CFG message

    It will send the message to the passed port, and verity a UBX-ACK-ACK message is received.

    Args:
        ubx_msg (Object): The UBX-CFG message to be sent.
        port: The serial port to send the message to.
    """

    # create UBXReader instance, reading only UBX messages
    ubr = UBXReader(port, protfilter=UBX_PROTOCOL)

    print("\nStarting read thread...\n")
    stop_event = Event()
    stop_event.clear()
    serial_lock = Lock()
    success_event = Event()
    success_event.clear()
    read_thread = start_thread(port, serial_lock, stop_event, ubr, success_event)

    # send the msg
    print("\nSending Config Message...\n")
    send_message(port, serial_lock, ubx_msg)

    # Validate the msg was acknowledged
    print("\nConfig Message was sent. Waiting for acknowledgement...\n")
    sleep(1) # At most an ACK message will be sent 1 second after
    did_it_work = False
    if success_event.is_set():
        print('Yippy')
        did_it_work = True
    else:
        print('Sad')
        raise RuntimeError('Did not receive acknowledgement in time')

    print("\nStopping reader thread...\n")
    stop_event.set()
    read_thread.join()
    print("\nProcessing Complete")

    return did_it_work


def signed_16(value):
    value = int(value, base=16)
    return -(value & 0x8000000000000000) | (value & 0x7fffffffffffffff)


def convert_u_center_config(config_file) -> object:
    """
    Function to convert U-Center Config (.txt) files to a pyubx2.UBXMessage.

    Doing so allows for the file to be sent to an u-blocks receiver.
    """
    cfg_data = []

    # Converting U-Center Config File to Bit representation using pyubx2.UBXMessage
    with (open(config_file, 'r') as file):
        for line in file:
            striped_line = line.strip()
            if striped_line.startswith('#'):
                continue
            split_line = striped_line.split()
            if split_line:
                layer = split_line[0]
                # Only process Flash layer for now
                if layer == 'Flash':
                    ubx_id = split_line[1].replace('-', '_') # ID's must use _
                    (key, ubx_attribute_type) = UBX_CONFIG_DATABASE[ubx_id] # Get the attribute string name
                    attribute_type = ATTTYPE[atttyp(ubx_attribute_type)] # Get the class of attribute
                    if attribute_type is bytes:
                        temp_msg = (ubx_id, int(split_line[2], 0).to_bytes()) # Must convert to bytes if ID requires it
                    elif ubx_id == 'CFG_TMODE_LON':
                        temp_msg = (ubx_id, signed_16(split_line[2])) # Negative numbers in hex work weird
                    else:
                        temp_msg = (ubx_id, int(split_line[2], 0))
                    cfg_data.append(temp_msg)

    msg = UBXMessage.config_set(
        layers=(SET_LAYER_RAM | SET_LAYER_FLASH | SET_LAYER_BBR),
        transaction=TXN_NONE,
        cfgData=cfg_data,
    )
    print(msg)
    return msg

if __name__ == '__main__':
    # Some Default Testing
    serial = serial.Serial('COM3', 9600)
    config = '../base-station/ntrip-caster/BS_Config.txt'
    msg = convert_u_center_config(config)
    send_config(msg, serial)
    serial.close()