
from influxdb_client_3 import InfluxDBClient3, Point
import os
import dotenv
import gps_reader

# Configure GPS
# gps = gps_reader.Budget()
# gps = gps_reader.Premium()
gps = gps_reader.SparkFun()
ubr = gps.get_reader()

# Configure InfluxDB
dotenv.load_dotenv()
token = os.getenv("INFLUXDB_TOKEN") if os.getenv("INFLUXDB_TOKEN") else 'XgXNV68VYCQHUUQrklj2FUkZ3cdKhd1xG9PxjDb3nZh36tqNkp3p10DKKdiHGYWb1ENqy27yz_q-WrR9_asA_w=='
org = "GPSSensorData"
host = "https://us-east-1-1.aws.cloud2.influxdata.com"
client = InfluxDBClient3(host=host, token=token, org=org)

# Verify we can write to the client first
client.write(database="GPS", record=Point('testing').field('message', 'Hello from RB5'), write_precision='s')

try:
    while True:
        raw_data, parsed_data = ubr.read()

        if parsed_data is None:
            print("No data received")
            continue
        elif parsed_data.identity == 'NAV-PVT':
            print('Received NAV-PVT')
            # Log parsed data to InfluxDB
            if parsed_data.fixType != 0:
                database="GPS"
                points = Point("metrics") \
                    .tag("device", "budget") \
                    .field("latitude", parsed_data.lat) \
                    .field("longitude", parsed_data.lon) \
                    .field("altitude_m", parsed_data.hMSL/1000) \
                    .field("ground_speed_ms", parsed_data.gSpeed / 1000) \
                    .field("ground_heading_deg", parsed_data.headMot) \
                    .field("horizontal_accuracy_m", parsed_data.hAcc/1000) \
                    .field("vertical_accuracy_m", parsed_data.vAcc/1000) \
                    .field("speed_accuracy_ms", parsed_data.sAcc/1000) \
                    .field("heading_accuracy_deg", parsed_data.headAcc)
                client.write(database=database, record=points, write_precision="s")
                print(f"Latitude: {parsed_data.lat}")
                print(f"Longitude: {parsed_data.lon}")
            else:
                print(f'Parsed data does not have fix type set: {parsed_data.fixType}')
        else:
            print(f'Ignoring data with identity: {parsed_data.identity}')
            
except KeyboardInterrupt:
    print("Terminating...")
finally:
    gps.close_serial()
    client.close()
