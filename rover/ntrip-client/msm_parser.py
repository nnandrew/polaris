from pyrtcm import parse_msm
from pyrtcm.rtcmtables import GPS_SIG_MAP, GLONASS_SIG_MAP, GALILEO_SIG_MAP, BEIDOU_SIG_MAP

def getFreq(CELLSIG, gnss):
    
    sig_map = GPS_SIG_MAP
    if gnss == "GLONASS":
        sig_map = GLONASS_SIG_MAP 
    elif gnss == "GALILEO":
        sig_map = GALILEO_SIG_MAP 
    elif gnss == "BEIDOU":
        sig_map = BEIDOU_SIG_MAP
        
    for freq, code in sig_map.values():
        if code == CELLSIG:
            return freq
        
    return None
       
def parse(parsed):
    metadata, msmsats, msmcells = parse_msm(parsed)
    msmsats = {
        sat['PRN']: {
            'DF397': sat['DF397'], 
            'DF398': sat['DF398']
        } for sat in msmsats
    }
    for cell in msmcells:
        prn = cell['CELLPRN']
        freq = getFreq(cell['CELLSIG'], metadata['gnss'])
        dfs = ['DF400', 'DF401', 'DF402', 'DF403', 'DF420']
        for df in dfs:
            f_dict = {freq: cell[df]}
            msmsats[prn][df] = msmsats[prn][df] | f_dict if df in msmsats[prn] else f_dict
            
    return metadata, msmsats
