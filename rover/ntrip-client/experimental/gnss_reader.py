import serial

def getECEF():
    return -742.276, 5462.306, 3197.494

def getSatelliteInfo():
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