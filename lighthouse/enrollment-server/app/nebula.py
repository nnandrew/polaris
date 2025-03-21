import os
import subprocess
import sqlite3
import ruamel.yaml
from ruamel.yaml.scalarstring import LiteralScalarString, DoubleQuotedScalarString
from flask import current_app

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True 
yaml.default_flow_style = True

def generate_nebula_config(group_name, LIGHTHOUSE_PUBLIC_IP):
    
    # Load Configuration Template
    with open("../config-template.yaml", "r") as config_file:
        config = yaml.load(config_file)
            
    # Host Mapping Persistence
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    if group_name == "lighthouse":
        host_id = 1
    else:
        cursor.execute("SELECT MAX(id) FROM hosts")
        host_id = int(cursor.fetchone()[0]) + 1
        if host_id > 254:
            raise Exception("Network full.")
    
    vpn_ip = f"192.168.100.{host_id}"
    cursor.execute('''
        INSERT INTO hosts (vpn_ip, group_name)
        VALUES (?, ?)
        ''', 
        (vpn_ip, group_name)
    )
    conn.commit()
    conn.close()
        
    # Generate Key and Certificate
    subprocess.run(["./nebula-cert", "sign", "-name", f"{host_id}", "-ip", f"{vpn_ip}/24"])

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
        
    # Lighthouse Configuration and File Writing
    config["static_host_map"]["192.168.100.1"] = [DoubleQuotedScalarString(f"{LIGHTHOUSE_PUBLIC_IP}:4242")]
    if group_name == "lighthouse":
        config["lighthouse"]["am_lighthouse"] = True
        config["lighthouse"]["hosts"] = ""
        config_path = "/home/enrollment-server/shared/config.yml"
        with open(config_path, "w") as config_file:
            yaml.dump(config, config_file)
    else: 
        config_path = f"/home/enrollment-server/shared/config_{host_id}.yaml"
        with open(config_path, "w") as config_file:
            yaml.dump(config, config_file)  
    
    current_app.logger.info(f"Certificate on {vpn_ip} generated for {group_name}.")

    return config_path
