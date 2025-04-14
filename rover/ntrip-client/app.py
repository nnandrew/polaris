
from influxdb_client_3 import InfluxDBClient3, Point
import os
import dotenv
import gps_reader

# Configure GPS
gps = gps_reader.Budget()
# gps = gps_reader.Premium()
# gps = gps_reader.Sparkfun()
ubr = gps.getReader()

# Configure InfluxDB
dotenv.load_dotenv()
token = os.getenv("INFLUXDB_TOKEN")
org = "GPSSensorData"
host = "https://us-east-1-1.aws.cloud2.influxdata.com"
client = InfluxDBClient3(host=host, token=token, org=org)

try:
    while True:
        raw_data, parsed_data = ubr.read()
            
        if parsed_data is not None and parsed_data.identity == "NAV-PVT":
            
            # Log parsed data to InfluxDB
            if parsed_data.fixType != 0:
                database="GPS"
                points = Point("metrics") \
                    .tag("device", "budget") \
                    .field("latitude", parsed_data.lat) \
                    .field("longitude", parsed_data.lon) \
                    .field("altitude_m", parsed_data.hMSL/1000) \
                    .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                    .field("ground_heading_deg", parsed_data.headMot/100000) \
                    .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                    .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                    .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                    .field("heading_accuracy_deg", parsed_data.headAcc/100000)
                client.write(database=database, record=points, write_precision="s")
                print(f"Latitude: {parsed_data.lat}")
                print(f"Longitude: {parsed_data.lon}")
            else:
                print("No fix available.")
            
            
except KeyboardInterrupt:
    print("Terminating...")
finally:
    gps.closeSerial()
    client.close()
