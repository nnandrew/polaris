"""
ECEF (Earth-Centered, Earth-Fixed) Position Solver.

This module provides functions to calculate a receiver's position in the ECEF
coordinate system using the least-squares estimation method. It takes an
initial position guess and satellite data (pseudoranges and positions) to
iteratively find a more accurate solution. It can optionally apply RTCM
corrections to the pseudoranges.

This is an experimental solver and may contain unused variables related to
phase range calculations.
"""
import numpy as np

# --- Constants ---
c = 299792458
"""float: The speed of light in meters per second."""
f_L1 = 1575.42 * 10**6
"""float: The carrier frequency for the L1 signal in Hz."""
f_L2 = 1227.60 * 10**6
"""float: The carrier frequency for the L2 signal in Hz."""
f_L5 = 1176.45 * 10**6
"""float: The carrier frequency for the L5 signal in Hz."""


def least_squares_estimation(x_0, y_0, z_0, P_corr, x_sats, y_sats, z_sats):
    """
    Performs a single iteration of the least-squares estimation algorithm.

    This function calculates the correction values (dx, dy, dz, and clock bias)
    to refine an initial position estimate based on the observed pseudoranges
    and satellite positions.

    Args:
        x_0 (float): Initial guess for the receiver's X-coordinate (ECEF).
        y_0 (float): Initial guess for the receiver's Y-coordinate (ECEF).
        z_0 (float): Initial guess for the receiver's Z-coordinate (ECEF).
        P_corr (np.ndarray): Array of corrected pseudoranges for each satellite.
        x_sats (np.ndarray): Array of X-coordinates for each satellite (ECEF).
        y_sats (np.ndarray): Array of Y-coordinates for each satellite (ECEF).
        z_sats (np.ndarray): Array of Z-coordinates for each satellite (ECEF).

    Returns:
        tuple: A tuple containing the updated receiver position and clock bias
               (x_r, y_r, z_r, delta_t_r).
    """
    num_sats = len(x_sats)
    
    # Geometric ranges based on initial guess
    rho_0 = np.sqrt((x_0 - x_sats)**2 + (y_0 - y_sats)**2 + (z_0 - z_sats)**2)
    
    # Observation residuals (corrected pseudoranges - geometric ranges)
    delta_P = P_corr - rho_0
    
    # Design matrix H
    H = np.zeros((num_sats, 4))  # 4 unknowns: dx, dy, dz, delta_t_r
    H[:, 0] = (x_sats - x_0) / rho_0
    H[:, 1] = (y_sats - y_0) / rho_0
    H[:, 2] = (z_sats - z_0) / rho_0
    H[:, 3] = c
    
    # Least squares solution: X = (H^T H)^(-1) H^T delta_P
    try:
        H_T_H_inv = np.linalg.inv(np.dot(H.T, H))
        H_T_delta_P = np.dot(H.T, delta_P)
        X = H_T_H_inv.dot(H_T_delta_P)
    except np.linalg.LinAlgError:
        # If the matrix is singular, cannot compute a solution
        return x_0, y_0, z_0, 0
    
    # Update the receiver's position and clock bias
    dx, dy, dz, delta_t_r = X
    x_r = x_0 + dx
    y_r = y_0 + dy
    z_r = z_0 + dz
    
    return x_r, y_r, z_r, delta_t_r

def solve(rover_ecef, rover_sats, rtcm_metadata=None, rtcm_sats=None):
    """
    Calculates the rover's ECEF position based on satellite data.

    This function prepares the satellite data, applies RTCM corrections if
    available, and then calls the least-squares estimation function to
    compute the rover's position.

    Args:
        rover_ecef (tuple): Initial guess for the rover's position (x, y, z).
        rover_sats (dict): A dictionary of satellite data from the rover, keyed
                           by PRN. Each entry should contain 'ecef', 'pseudorange',
                           and 'freq'.
        rtcm_metadata (dict, optional): Metadata from RTCM messages. Defaults to None.
        rtcm_sats (dict, optional): A dictionary of satellite correction data
                                    from RTCM messages, keyed by PRN. Defaults to None.

    Returns:
        tuple: The calculated ECEF position and clock bias (x, y, z, dt).
    """
    # Receiver Initial Values
    x_0, y_0, z_0 = rover_ecef
    
    prns = list(rover_sats.keys())
    num_usable_sats = len(prns)
    
    x_sats = np.empty(num_usable_sats)
    y_sats = np.empty(num_usable_sats)
    z_sats = np.empty(num_usable_sats)
    P_corr = np.empty(num_usable_sats)
    
    for i, prn in enumerate(prns):
        x_sats[i], y_sats[i], z_sats[i] = rover_sats[prn]["ecef"]
        
        # Apply RTCM Correction if available
        P_delta = 0
        freq = rover_sats[prn]["freq"]
        if rtcm_sats and prn in rtcm_sats and "DF400" in rtcm_sats[prn] and freq in rtcm_sats[prn]["DF400"]:
            P_delta = c * 0.001 * rtcm_sats[prn]["DF400"][freq]
            
        P_corr[i] = rover_sats[prn]["pseudorange"] + P_delta
    
    # Calculate Solution
    return least_squares_estimation(x_0, y_0, z_0, P_corr, x_sats, y_sats, z_sats)