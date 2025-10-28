"""
Nebula Configuration Generation Module.

This module provides functionality to dynamically generate Nebula configuration
files for nodes joining the mesh network. It uses the `nebula-cert` utility to
create certificates and keys, and persists host information in a SQLite database.
"""
import os
import subprocess
import sqlite3
import ruamel.yaml
from ruamel.yaml.scalarstring import LiteralScalarString, DoubleQuotedScalarString
from flask import current_app
import subprocess
import concurrent.futures

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True 
yaml.default_flow_style = True

def generate_nebula_config(group_name, public_ip, ip_octet=None):
    """
    Generates a Nebula configuration file for a new node.

    Steps:
    1.  Loads base config from `config-template.yaml`.
    2.  Assigns a VPN IP from 192.168.100.0/24.
    3.  Records host info in `record.db`.
    4.  Calls `nebula-cert` to sign a certificate.
    5.  Reads CA cert, host cert, and key from files.
    6.  Embeds cert/key content into config.
    7.  Deletes temporary cert/key files.
    8.  Sets static host map to lighthouse's public IP.
    9.  Adjusts settings for lighthouse or regular host.
    10. Writes config to a unique YAML file.

    Args:
        group_name (str): Nebula group name for the node.
        public_ip (str): Lighthouse node's public IP.
        ip_octet (int): Desired IP octet (2-254) for the node.

    Returns:
        str: Path to the generated config file.
    
    Raises:
        Exception: If network is full or IP is invalid/in use.
    """
    # Load Configuration Template
    with open("../config-template.yaml", "r") as config_file:
        config = yaml.load(config_file)
            
    # Host Mapping Persistence
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    if group_name == "lighthouse":
        host_id = 1
    else:
        cursor.execute("SELECT id FROM hosts ORDER BY id")
        used_ids = {row[0] for row in cursor.fetchall()}
        if ip_octet is None:
            # Find the smallest unused id in 1..254
            for candidate_id in range(2, 255):
                if candidate_id not in used_ids:
                    host_id = candidate_id
                    break
            else:
                raise Exception("Network full.")
        else:
            if ip_octet in used_ids:
                raise Exception(f"IP address 192.168.100.{ip_octet} is already in use.")
            if ip_octet < 2 or ip_octet > 254:
                raise Exception("IP octet must be between 2 and 254.")
            host_id = ip_octet
    
    vpn_ip = f"192.168.100.{host_id}"
    cursor.execute('''
        INSERT INTO hosts (id, vpn_ip, group_name)
        VALUES (?, ?, ?)
        ''', 
        (host_id, vpn_ip, group_name)
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
        
    # Lighthouse Configuration
    config["static_host_map"]["192.168.100.1"] = [DoubleQuotedScalarString(f"{public_ip}:4242")]
    if group_name == "lighthouse":
        config["lighthouse"]["am_lighthouse"] = True
        config["lighthouse"]["hosts"] = ""
        config_path = "/home/enrollment-server/shared/config.yml"
    else: 
        config_path = f"/home/enrollment-server/shared/config_{host_id}.yaml"
    
    # File Writing
    with open(config_path, "w") as config_file:
        yaml.dump(config, config_file)       
    current_app.logger.info(f"Certificate on {vpn_ip} generated for {group_name}.")

    return config_path

def get_base_station():
    """
    Retrieves the VPN IP address of the base station from the database.

    Returns:
        tuple: (vpn_ip,) of the base station, or None if not found.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT vpn_ip FROM hosts WHERE group_name = 'base_station'")
    result = cursor.fetchone()
    conn.close()
    return result

def ping_host(vpn_ip):
    """
    Pings a VPN IP address once and returns the ping time in ms.

    Args:
        vpn_ip (str): The VPN IP to ping.

    Returns:
        str: The ping status.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "5", vpn_ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if result.returncode == 0:
            # Parse ping output for rtt min/avg/max/mdev
            for line in result.stdout.splitlines():
                if "rtt" in line:
                    ping_status = f"{float(line.split("/")[-2]):4.0f} ms"
                    break
        else:
            ping_status = "   down"
    except Exception:
        ping_status = "  error"
    return ping_status

def get_hosts(ping=False):
    """
    Retrieves all hosts from the database and pings each host.

    Returns:
        list of tuples: (id, vpn_ip, group_name, ping_ms) for each host.
        ping_ms is -1 if unreachable.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, vpn_ip, group_name FROM hosts")
    results = cursor.fetchall()
    conn.close()

    hosts_with_status = []
    
    # Sequential pinging
    # for row in results:
    #     ping_ms = ping_host(row[1])
    #     hosts_with_status.append(row + (ping_ms,)) 
    
    # Concurrent pinging
    if ping:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            vpn_ips = [row[1] for row in results]
            ping_results = list(executor.map(ping_host, vpn_ips))
            for row, ping_status in zip(results, ping_results):
                hosts_with_status.append(row + (ping_status,))
    else:
        for row in results:
            hosts_with_status.append(row + ("    ...",))

    return hosts_with_status

def remove_host(host_id):
    """
    Removes a user from the database.

    Args:
        host_id (int): The host's ID.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
    conn.commit()
    conn.close()

def rename_group(host_id, new_group_name):
    """
    Renames the group for a given host.

    Args:
        host_id (int): The host's ID.
        new_group_name (str): The new group name.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE hosts SET group_name = ? WHERE id = ?", (new_group_name, host_id))
    conn.commit()
    conn.close()