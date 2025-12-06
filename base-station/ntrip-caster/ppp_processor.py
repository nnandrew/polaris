from datetime import datetime, timedelta
from geopy.distance import geodesic
from ftplib import FTP
from tqdm import tqdm
import subprocess
import shutil
import json
import gzip
import time
import os
import re

import threading

class PPPProcessor(threading.Thread):
    
    def __init__(self, ubx_config, latest_pos, ppp_done, stop_event):
        self.ubx_config = ubx_config
        self.latest_pos = latest_pos
        self.ppp_done = ppp_done
        self.stop_event = stop_event
        self.rtklib_path = "./RTKLIB/bin"
        self.start_time = datetime.now()
        self.intervals = [
            5, 15*60, 30*60, 60*60, 2*3600, 4*3600, 6*3600,
            12*3600, 24*3600, 48*3600, 96*3600, 192*3600, 384*3600
        ]
        super().__init__()
        
    def run(self):
        
        # Check for existing calibration
        prev_sd = float('inf')
        if os.path.exists("./shared/calibration.json"):
            print("PPP Processor: Found existing calibration file.")
            with open("./shared/calibration.json", "rb") as f:
                calibration_data = json.load(f)
            cal_lat = calibration_data.get("latitude", 0.0)
            cal_lon = calibration_data.get("longitude", 0.0)
            cal_height = calibration_data.get("height", 0.0)
            cal_sd = calibration_data.get("sd", float('inf'))
            
            # Check if accuracy is within 3 meters after waiting for NAV-PVT
            time.sleep(5)
            navpvt_lat, navpvt_lon, navpvt_height = self.latest_pos.get()
            horizontal_error = geodesic((cal_lat, cal_lon), (navpvt_lat, navpvt_lon)).meters
            vertical_error = abs(cal_height - navpvt_height)
            
            # Use previous calibration if still valid
            if horizontal_error <= 2.0 and vertical_error <= 2.0:
                self.ubx_config.send_fixed(cal_lat, cal_lon, cal_height)
                prev_sd = cal_sd
                print(f"PPP Processor: Sent Fixed Position from Calibration: {cal_lat}, {cal_lon}, {cal_height}")
            else: 
                print("PPP Processor: Calibration position is no longer valid due to movement.")
        else:
            # Fall back to survey-in if no calibration file
            print("PPP Processor: No calibration file found. Starting survey-in.")
            self.ubx_config.send_survey()
            
        ubx_file = "./temp/station_snapshot.ubx"
        obs_file = "./temp/station_snapshot.obs"
        nav_file = "./temp/station_snapshot.nav"
        output_file = "./temp/ppp.pos"
        
        for interval in self.intervals:
            try:
                # Wait for the specified interval
                print(f"PPP Processor: Waiting for {interval/60:.1f} minutes before next PPP run...")
                target = self.start_time + timedelta(seconds=interval)
                while datetime.now() < target:
                    time.sleep(1)
                    if self.stop_event.is_set():
                        break
                 
                # Take snapshot of UBX data and run PPP   
                print("PPP Processor: Taking UBX snapshot and running PPP...")
                os.mkdirs("./temp", exist_ok=True)
                shutil.copyfile("./shared/station.ubx", ubx_file)
                self.convert_ubx_to_rinex(ubx_file, obs_file, nav_file)
                obs_datetime = self.parse_observation_start_time(obs_file)
                sp3_file, clk_file, solution_type = self.download_precise_products(obs_datetime)
                self.run_rnx2rtkp_ppp(obs_file, nav_file,sp3_file, clk_file, output_file)
                
                # Parse PPP result
                print("PPP Processor: Parsing PPP result...")
                if not os.path.exists(output_file):
                    print("PPP Processor: PPP output file not found. Skipping this iteration.")
                    continue
                with open(output_file, 'r') as f:
                    solution = f.readlines()[-1]
                parts = solution.split()
                if len(parts) < 19:
                    continue
                lat = int(parts[2]) + int(parts[3])/60 + float(parts[4])/3600
                if int(parts[5]) >=0:
                    lon = int(parts[5]) + int(parts[6])/60 + float(parts[7])/3600
                else:
                    lon = int(parts[5]) - int(parts[6])/60 - float(parts[7])/3600
                height = float(parts[8])
                sd = (float(parts[12]) + float(parts[13]) + float(parts[14])) / 3.0
                
                # Only update if accuracy improved
                if sd < prev_sd:
                    print(f"PPP Processor: Accuracy improved from {prev_sd:.2f} m to {sd:.2f} m. Updating fixed position.")
                    prev_sd = sd
                    self.ubx_config.send_fixed(lat, lon, height)
                    with open("./shared/calibration.json", "w") as f:
                        calibration_data = {
                            "latitude": lat,
                            "longitude": lon,
                            "height": height,
                            "sd": sd
                        }
                        json.dump(calibration_data, f)
                    print(f"PPP Processor: Updated Fixed Position: {lat}, {lon}, {height} (SD: {sd:.2f} m) using {solution_type} products")
                else:
                    print(f"PPP Processor: Accuracy did not improve (current SD: {sd:.2f} m). Keeping previous fixed position.")
            finally:
                shutil.rmtree("./temp")
        self.ppp_done.set()
            
    def convert_ubx_to_rinex(self, ubx_file, rinex_obs_file, rinex_nav_file):
        convbin_cmd = [
            os.path.join(self.rtklib_path, "convbin"),
            "-o", rinex_obs_file,
            "-n", rinex_nav_file,
            # "-trace", "3",
            ubx_file
        ]
        subprocess.Popen(convbin_cmd).wait()
        print(f"PPP Processor: Converted UBX to RINEX: {rinex_obs_file}, {rinex_nav_file}")
        
    def parse_observation_start_time(self, rinex_obs_file):
        with open(rinex_obs_file, 'r') as f:
            for line in f:
                if "TIME OF FIRST OBS" in line:
                    parts = line.split()
                    year, month, day, hour, minute = map(int, parts[:5])
                    second = float(parts[5])
                    return datetime(year, month, day, hour, minute, int(second))
        return None
    
    def download_precise_products(self, obs_datetime):
        
        # Compute GPS week from obs_datetime
        def datetime_to_gpsweek(dt):
            # GPS epoch: 1980-01-06
            from datetime import datetime
            gps_epoch = datetime(1980, 1, 6, 0, 0, 0)
            delta = dt - gps_epoch
            gps_week = delta.days // 7
            return gps_week

        # Convert obs_datetime to YYYYDOY
        def datetime_to_yyyy_doy(dt):
            year = dt.year
            doy = dt.timetuple().tm_yday
            return f"{year}{doy:03d}"

        # FTP download utility
        def download_file(ftp, file_name):
            file_path = f"./temp/{file_name}"
            # Download the file
            with open(file_path, 'wb') as f, tqdm(desc=f'Downloading {file_name}', unit='B', unit_scale=True) as bar:
                def callback(data):
                    f.write(data)
                    bar.update(len(data))
                ftp.retrbinary(f'RETR {file_name}', callback)

            # If the file is a .gz, extract it
            if file_path.endswith(".gz"):
                extracted_path = file_path[:-6] + file_path[-6:-3].lower()  # remove '.gz' and adjust extension
                with gzip.open(file_path, 'rb') as f_in:
                    with open(extracted_path, 'wb') as f_out, tqdm(desc=f'Extracting  {file_name}', unit='B', unit_scale=True) as bar:
                        chunk_size = 1024 * 1024  # 1 MB
                        while True:
                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            bar.update(len(chunk))
                os.remove(file_path)  # Remove the .gz file
                return extracted_path
            else:
                return file_path

        # Best to Worst Products
        solution_hierarchy = [
            "FIN",  # Final products
            "RAP",  # Rapid products
            "ULT",  # Ultra-rapid products
            "PREV"  # Previous day ultra-rapid products
        ]
        # Best to Worst Analysis Centers
        analysis_center_priority = [
            "IGS",   # International GNSS Service (IGS) – Global combination center, highest quality
            "JPL",   # Jet Propulsion Laboratory (USA) – High-quality, US-based, IGS core analysis center
            "USN",   # U.S. Naval Observatory (USA) – Reliable, US-based
            "NGS",   # NOAA/National Geodetic Survey (USA) – US government geodesy agency
            "SIO",   # Scripps Institution of Oceanography (USA) – High-quality scientific contributions
            "COD",   # Center for Orbit Determination in Europe (Switzerland) – IGS core center, globally respected
            "GRG",   # Space geodesy team of CNES (France) – IGS analysis center
            "ESA",   # European Space Agency (Germany) – high-quality, globally respected
            "GOP",   # Geodetic Observatory Pecny (Czech Republic) – reliable, but lower priority for US usage
            "WHU",   # Wuhan University (China) – good data but more latency for US users
            "JGX",   # Geospatial Information Authority of Japan/JAXA – reliable, farther away
            "EMR",   # Natural Resources Canada – good but less globally recognized for orbit analysis
            "GFZ",   # GFZ Helmholtz (Germany) – solid, but usually used as backup
            "MIT"    # Massachusetts Institute of Technology – contributes, but not a core analysis center
        ]
        center_priority_map = {center: i for i, center in enumerate(analysis_center_priority)}

        # Download best available products from FTP server
        gps_week = datetime_to_gpsweek(obs_datetime)
        ftp = FTP("garner.ucsd.edu")
        ftp.login()
        ftp.cwd(f"/pub/products/{gps_week}")
        files = ftp.nlst()
        
        # Find all matching SP3 and CLK files
        sp3_file = None
        clk_file = None
        date = datetime_to_yyyy_doy(obs_datetime)
        for solution_type in solution_hierarchy:
            
            # Handle previous day ultra-rapid case and week boundary
            if solution_type == "PREV":
                solution_type = "ULT"  # Previous day ultra-rapid uses ULT type
                prev_obs_datetime = obs_datetime - timedelta(days=1)
                date = datetime_to_yyyy_doy(prev_obs_datetime)
                gps_week_candidate = datetime_to_gpsweek(prev_obs_datetime)
                if gps_week_candidate != gps_week:
                    ftp.cwd(f"/pub/products/{gps_week_candidate}")
                    files = ftp.nlst()
            
            # Find all matching SP3 and CLK files
            sp3_pattern = re.compile(rf'(\w{{3}})0OPS{solution_type}_{date}(\d{{2}})00_.+.ORB.SP3.gz')
            clk_pattern = re.compile(rf'(\w{{3}})0OPS{solution_type}_{date}(\d{{2}})00_.+.CLK.CLK.gz')
            sp3_files = {}
            clk_files = {}
            for f in files:
                # Collect the latest hour files for each analysis center
                match = sp3_pattern.match(f)
                if match:
                    analysis_center = match.group(1)
                    hours = int(match.group(2))
                    if analysis_center not in sp3_files or hours > sp3_files[analysis_center][1]:
                        sp3_files[analysis_center] = (f, hours)
                    continue
                match = clk_pattern.match(f)
                if match:
                    analysis_center = match.group(1)
                    hours = int(match.group(2))
                    if analysis_center not in clk_files or hours > clk_files[analysis_center][1]:
                        clk_files[analysis_center] = (f, hours)

            # Group files by analysis center
            file_pairs = {}
            if sp3_files and clk_files:
                for analysis_center in sp3_files.keys():
                    if analysis_center in clk_files.keys():
                        file_pairs[analysis_center] = (sp3_files[analysis_center][0], clk_files[analysis_center][0])

            # Select the best file pair based on priority
            print( f"PPP Processor: Found {len(file_pairs)} {solution_type} product pairs for date {date}.")
            if file_pairs:       
                best_center = min(
                    file_pairs.keys(),
                    key=lambda c: center_priority_map.get(c, float('inf'))
                )
                sp3_file_name, clk_file_name = file_pairs[best_center]
                if os.path.exists(sp3_file_name[:-3]):
                    sp3_file = sp3_file_name[:-3]
                else:
                    sp3_file = download_file(ftp, sp3_file_name)
                if os.path.exists(clk_file_name[:-3]):
                    clk_file = clk_file_name[:-3]
                else:
                    clk_file = download_file(ftp, clk_file_name)
                solution_type = solution_type
                print(f"PPP Processor: Using {solution_type} products from {best_center}: {sp3_file}, {clk_file}")
                break
            
        ftp.quit()  
        return sp3_file, clk_file, solution_type
    
    def run_rnx2rtkp_ppp(self, rinex_obs_file, rinex_nav_file, sp3_file, clk_file, output_file):
        rnx2rtkp_cmd = [
            os.path.join(self.rtklib_path, "rnx2rtkp"),
            "-p",   "8",          # PPP-Static mode
            "-m",   "1",          # Elevation mask 
            # "-sys", "G,R",        # GNSS systems to use
            # "-f",   "2",          # Frequencies to use
            # "-v",   "3",          # Validation threshold for integer ambiguity
            # "-c",               # Combined solution
            # "-i",               # Instantaneous interger ambiguitiy resolution
            # "-h",               # Fix and hold integer ambiguity resolution
            "-x",   "2",          # Verbose trace level
            # "-e",               # Output ECEF
            "-g",                 # Output LLH
            # "-a",               # Output ENU   
            "-o", output_file,
            rinex_obs_file,
            rinex_nav_file,
            sp3_file,
            clk_file
        ]
        subprocess.Popen(rnx2rtkp_cmd, stdout=subprocess.PIPE, text=True, bufsize=1).wait()
        print(f"PPP Processor: PPP result written to {output_file}")

if __name__ == "__main__":
    """
    Converts UBX to RINEX, extracts observation start time, downloads precise products,
    and runs rnx2rtkp in PPP mode.
    """
    
    rtklib_path = "./RTKLIB/bin"  
    ubx_file = "station.ubx"
    rinex_obs_file = "station.obs"
    rinex_nav_file = "station.nav"
    output_file = "ppp.pos"
    
    ppp = PPPProcessor(rtklib_path)
    ppp.convert_ubx_to_rinex(ubx_file, rinex_obs_file, rinex_nav_file)
    obs_datetime = ppp.parse_observation_start_time(rinex_obs_file)
    sp3_file, clk_file, solution_type = ppp.download_precise_products(obs_datetime)
    ppp.run_rnx2rtkp_ppp(rinex_obs_file, rinex_nav_file, sp3_file, clk_file, output_file)
    with open(output_file, 'r') as f:
        print(f"PPP Processor: {f.readlines()[-1]}")
    