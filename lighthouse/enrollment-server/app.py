import subprocess
import os
import dotenv
import flask
import yaml

# 192.168.100.X/24 is the subnet for the Nebula network
# X=0 is the network identifier
# X=1 is the Lighthouse address
# X=2-254 are the host addresses 
# X=255 is the broadcast address

TEMPLATE_PATH = "./config-template.yaml"
CA_PATH = "./ca.crt"
    
host_id = 1;
app = flask.Flask(__name__)

@app.route('/enroll', methods=['GET'])
def enroll():
    
    # Authenticate Request
    network_key = flask.request.args.get('network_key')
    if network_key != NETWORK_KEY:
        return "Unauthorized", 401
        
    # Generate Host Configuration
    config_yaml = generate_nebula_config()
    config_path = f"./config_{host_id - 2}.yaml",
    with open(config_path, "w") as config_file:
        yaml.dump(config_yaml, config_file)  
    host_id += 1
    
    return flask.send_file(config_path, as_attachment=True), 200

def generate_nebula_config(isLighthouse=False):
    
    subprocess.run(["nebula-cert", "sign", "-name", f"{host_id}", "-ip", f"192.168.100.{host_id}/24"])

    # Load Configuration Template
    with open(TEMPLATE_PATH, "r") as template:
        config = yaml.safe_load(template)
        
    # Add Certificates and Keys to Configuration
    with open(CA_PATH, "r") as ca_file:
        config["pki"]["ca"] = f"|\n{ca_file.read()}"
        
    with open(f"./{host_id}.crt", "r") as crt_file:
        config["pki"]["crt"] = f"|\n{crt_file.read()}"
        
    with open(f"./{host_id}.key", "r") as key_file:
        config["pki"]["key"] = f"|\n{key_file.read()}"
        
    # Lighthouse Configuration
    if isLighthouse:
        config["lighthouse"]["am_lighthouse"] = True
        config["static_host_map"]["\"192.168.100.1\""] = LIGHTHOUSE_PUBLIC_IP
        config["lighthouse"]["hosts"] = ""
    
    return config 

if __name__ == '__main__':
    
    # Load Environment Variables
    dotenv.load_dotenv()
    NETWORK_KEY = os.getenv("NETWORK_KEY").split(",")
    LIGHTHOUSE_PUBLIC_IP = os.getenv("LIGHTHOUSE_PUBLIC_IP")
    
    # Generate CA Certificate
    subprocess.run(["nebula-cert", "ca", "-name", "\"Polaris\""])
    
    # Generate Lighthouse Configuration
    config = generate_nebula_config(isLighthouse=True)
    with open("/etc/nebula/config-lighthouse.yaml", "w") as config_file:
        yaml.dump(config, config_file)
    
    # Start Flask Server
    app.run(debug=True)