import subprocess
import os
import dotenv
import requests
import tarfile
import flask
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString, DoubleQuotedScalarString

# 192.168.100.X/24 is the subnet for the Nebula network
# X=0 is the network identifier
# X=1 is the Lighthouse address
# X=2-254 are the host addresses 
# X=255 is the broadcast address
    
host_id = 1
app = flask.Flask(__name__)
yaml = YAML()
yaml.preserve_quotes = True 
yaml.default_flow_style = True

@app.route('/enroll', methods=['GET'])
def enroll():
    
    # Authenticate Request
    network_key = flask.request.args.get('network_key')
    if not network_key or network_key != NETWORK_KEY:
        return "Unauthorized", 401
        
    # Generate Host Configuration
    global host_id
    config_yaml = generate_nebula_config()
    config_path = f"./shared/config_{host_id}.yaml"
    with open(config_path, "w") as config_file:
        yaml.dump(config_yaml, config_file)  
    host_id += 1
    
    return flask.send_file(config_path, as_attachment=True), 200

def generate_nebula_config(isLighthouse=False):
    
    
    # Load Configuration Template
    with open("./config-template.yaml", "r") as config_file:
        config = yaml.load(config_file)
        
    # Generate Key and Certificate
    os.chdir("./shared")
    subprocess.run(["./nebula-cert", "sign", "-name", f"{host_id}", "-ip", f"192.168.100.{host_id}/24"])

    # Add Certificates and Keys to Configuration
    with open("./ca.crt", "r") as ca_file:
        config["pki"]["ca"] = LiteralScalarString(ca_file.read())
        
    with open(f"./{host_id}.crt", "r") as crt_file:
        config["pki"]["cert"] = LiteralScalarString(crt_file.read())
        
    with open(f"./{host_id}.key", "r") as key_file:
        config["pki"]["key"] = LiteralScalarString(key_file.read())
        
    # Cleanup
    os.remove(f"./{host_id}.crt")
    os.remove(f"./{host_id}.key")
    os.chdir("..")
        
    # Lighthouse Configuration
    config["static_host_map"]["192.168.100.1"] = [DoubleQuotedScalarString(f"{LIGHTHOUSE_PUBLIC_IP}:4242")]
    if isLighthouse:
        config["lighthouse"]["am_lighthouse"] = True
        config["lighthouse"]["hosts"] = ""
    
    return config 

if __name__ == '__main__':
    
    # Load Environment Variables
    dotenv.load_dotenv()
    NETWORK_KEY = os.getenv("NETWORK_KEY")
    LIGHTHOUSE_PUBLIC_IP = os.getenv("LIGHTHOUSE_PUBLIC_IP")

    # Download Nebula Certificate Generator if necessary
    if not os.path.exists("./shared/nebula-cert"):
    
        url = "https://github.com/slackhq/nebula/releases/download/v1.9.5/nebula-linux-amd64.tar.gz"
        response = requests.get(url)
        with open('./shared/nebula-linux-amd64.tar.gz', 'wb') as file:
            file.write(response.content)

        with tarfile.open('./shared/nebula-linux-amd64.tar.gz', 'r:gz') as tar:
            tar.extractall('./shared')
        
        os.remove('./shared/nebula-linux-amd64.tar.gz')
        os.remove('./shared/nebula')
        print("Nebula Certificate Generator Downloaded.")

    # Generate CA Key if necessary
    if not os.path.exists("./shared/ca.key"):     
        os.chdir("./shared")
        subprocess.run(["./nebula-cert", "ca", "-name", "\"Polaris\""])
        os.chdir("..")
        print("CA Key and Certificate Generated.")   
        
    # Generate Lighthouse Configuration if necessary
    if not os.path.exists("./shared/config.yml"):
        config = generate_nebula_config(isLighthouse=True)
        with open("./shared/config.yml", "w") as config_file:
            yaml.dump(config, config_file)
        host_id += 1
        print("Lighthouse Configuration Generated.")   
        
    # Start Flask Server
    app.run(host='0.0.0.0', port=80)