"""
Mock GNSS data provider for testing and development.

This module provides hardcoded, simulated data that mimics the output of a
live GNSS receiver. It is intended for use in experimental features or when
a hardware receiver is not available.
"""
import serial

def getECEF():
    """
    Returns a hardcoded ECEF position for the rover.

    This serves as an initial guess for the rover's position.

    Returns:
        tuple: A tuple containing a fixed (x, y, z) ECEF coordinate.
    """
    return -742.276, 5462.306, 3197.494

def getSatelliteInfo():
    """
    Returns a hardcoded dictionary of satellite information.

    This provides simulated satellite data, including frequency, ECEF position,
    and pseudorange for a set of satellites. Most values are placeholders.

    Returns:
        dict: A dictionary of mock satellite data, keyed by PRN.
    """
    ROVER_SAT = {
        '002': {
            'freq': "L2",
            'ecef': (17104.3, -5228.5, 19811.5),
            'pseudorange': 23399263.4
        },
        '010': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '012': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '023': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '025': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '028': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '031': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        },
        '032': {
            'freq': "L2",
            'ecef': (0, 0, 0),
            'pseudorange': 20000000
        }
    }
    return ROVER_SAT