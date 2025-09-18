"""
RTCM MSM (Multiple Signal Message) Parser.

This module provides functions to parse and restructure data from RTCM
Multiple Signal Messages, which contain detailed satellite observation data.
It uses the `pyrtcm` library for the initial parsing and then reorganizes
the data into a more accessible format, grouping it by satellite PRN and
signal frequency.
"""
from pyrtcm import parse_msm
from pyrtcm.rtcmtables import GPS_SIG_MAP, GLONASS_SIG_MAP, GALILEO_SIG_MAP, BEIDOU_SIG_MAP

def getFreq(cellsig, gnss):
    """
    Looks up the frequency band name (e.g., "L1", "L2") for a given signal ID.

    Args:
        cellsig (str): The signal ID code (e.g., "02L").
        gnss (str): The GNSS constellation name (e.g., "GPS", "GLONASS").

    Returns:
        str or None: The corresponding frequency band name, or None if not found.
    """
    sig_map = {
        "GPS": GPS_SIG_MAP,
        "GLONASS": GLONASS_SIG_MAP,
        "GALILEO": GALILEO_SIG_MAP,
        "BEIDOU": BEIDOU_SIG_MAP,
    }.get(gnss, GPS_SIG_MAP)
        
    for freq, code in sig_map.values():
        if code == cellsig:
            return freq
        
    return None
       
def parse(parsed):
    """
    Parses a raw MSM message and restructures the data.

    This function takes a parsed RTCM message object from `pyrtcm` and
    transforms the flat satellite and cell data into a nested dictionary,
    keyed by satellite PRN. The cell data (containing pseudorange, phase, etc.)
    is further organized by frequency band.

    Args:
        parsed: A parsed RTCM message object from `pyrtcm.RTCMReader.read()`.

    Returns:
        tuple: A tuple containing:
            - dict: The MSM metadata.
            - dict: The restructured satellite data, keyed by PRN.
    """
    metadata, msmsats, msmcells = parse_msm(parsed)
    # Re-structure sats into a dictionary keyed by PRN
    msmsats_dict = {
        sat['PRN']: {
            'DF397': sat['DF397'], 
            'DF398': sat['DF398']
        } for sat in msmsats
    }
    
    # Merge cell data into the satellite dictionary
    for cell in msmcells:
        prn = cell['CELLPRN']
        if prn not in msmsats_dict:
            continue
        
        freq = getFreq(cell['CELLSIG'], metadata['gnss'])
        if not freq:
            continue
            
        # Data fields containing signal-specific info
        dfs = ['DF400', 'DF401', 'DF402', 'DF403', 'DF420']
        for df in dfs:
            if cell[df] is not None:
                f_dict = {freq: cell[df]}
                # Ensure the data field key exists before trying to merge
                if df not in msmsats_dict[prn]:
                    msmsats_dict[prn][df] = {}
                msmsats_dict[prn][df].update(f_dict)
            
    return metadata, msmsats_dict
