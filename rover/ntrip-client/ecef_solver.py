import numpy as np

# Computed Geometric Range in meters between the ARP of station S and satellite
s = 0  

# Phase Range Measurement in meters for station S, L1 and L2
phi = 0  

# Integer Ambiguity part scaled to meters, L1 and L2
N = 0

# Receiver clock term for the respective frequency of Phase Range Measurement, L1 and L2
t = 0  

# Antenna Offset and Phase Center Variation Correction for the respective frequency, L1 and L2
A = 0  

# Speed of light and Carrier frequencies
c = 299792458
f_L1 = 1575.42 * 10**6
f_L2 = 1227.60 * 10**6
f_L5 = 1176.45 * 10**6

# Compute corrections
L1C = s - phi + (N * f_L1 / c) - t + A


def least_squares_estimation(x_0, y_0, z_0, P_corr, x_sats, y_sats, z_sats):
    
    num_sats = len(x_sats)
    
    # Geometric ranges based on initial guess
    rho_0 = np.array([np.sqrt((x_0 - x_sats[i])**2 + (y_0 - y_sats[i])**2 + (z_0 - z_sats[i])**2) for i in range(num_sats)])
    
    # Observation residuals (corrected pseudoranges - geometric ranges)
    delta_P = P_corr - rho_0
    
    # Design matrix H
    H = np.zeros((num_sats, 4))  # 4 unknowns: dx, dy, dz, delta_t_r
    for i in range(num_sats):
        H[i, 0] = (x_sats[i] - x_0) / rho_0[i]
        H[i, 1] = (y_sats[i] - y_0) / rho_0[i]
        H[i, 2] = (z_sats[i] - z_0) / rho_0[i]
        H[i, 3] = c
    
    # Least squares solution
    # X = (H^T H)^(-1) H^T delta_P
    H_T_H = np.dot(H.T, H)
    H_T_delta_P = np.dot(H.T, delta_P)
    X = np.linalg.inv(H_T_H).dot(H_T_delta_P)
    
    # Update the receiver's position and clock bias
    dx, dy, dz, delta_t_r = X
    x_r = x_0 + dx
    y_r = y_0 + dy
    z_r = z_0 + dz
    
    return x_r, y_r, z_r, delta_t_r

def solve(rover_ecef, rover_sats, rtcm_metadata=None, rtcm_sats=None):
    
    # Receiver Initial Values
    x_0, y_0, z_0 = rover_ecef          # Initial guess for rover position
    
    num_usable_sats = len(rover_sats.keys())
    x_sats = np.empty(num_usable_sats)    # Satellite X positions
    y_sats = np.empty(num_usable_sats)    # Satellite Y positions
    z_sats = np.empty(num_usable_sats)    # Satellite Z positions
    P_corr = np.empty(num_usable_sats)    # Corrected pseudoranges
    
    for i in range(num_usable_sats):
        prn = list(rover_sats.keys())[i]
        x_sats[i], y_sats[i], z_sats[i] = rover_sats[prn]["ecef"]
        # RTCM Correction
        freq = rover_sats[prn]["freq"]
        P_delta = 0
        if rtcm_sats and prn in rtcm_sats and freq in rtcm_sats[prn]["DF400"]:
            P_delta = c * 0.001 * rtcm_sats[prn]["DF400"][freq]
        P_corr[i] = rover_sats[prn]["pseudorange"] + P_delta
    
    # Calculate Solution
    return least_squares_estimation(x_0, y_0, z_0, P_corr, x_sats, y_sats, z_sats)