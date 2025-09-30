"""
Nebula Configuration Generation Module.

This module provides the functionality to dynamically generate Nebula configuration
files for new nodes wishing to join the mesh network. It interacts with the
`nebula-cert` utility to create certificates and keys, and it persists host
information in a SQLite database.
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
    Generates a complete Nebula configuration file for a new node.

    This function performs the following steps:
    1.  Loads a base configuration from `config-template.yaml`.
    2.  Assigns a new VPN IP address from the 192.168.100.0/24 subnet.
    3.  Records the new host's IP and group name in the `record.db` database.
    4.  Calls `nebula-cert` to sign a new certificate for the host.
    5.  Reads the CA certificate, host certificate, and host key from files.
    6.  Embeds the certificate and key content directly into the configuration.
    7.  Deletes the temporary host certificate and key files.
    8.  Sets the static host map to point to the lighthouse's public IP.
    9.  Adjusts settings based on whether the node is a lighthouse or a regular host.
    10. Writes the final configuration to a unique YAML file.

    Args:
        group_name (str): The name of the Nebula security group for the new node.
        public_ip (str): The public IP address of the lighthouse node.
        ip_octet (int): The desired IP octet (2-254) for the new node.

    Returns:
        str: The file path to the newly generated configuration file.
    
    Raises:
        Exception: If the network runs out of available IP addresses (max 254).
        Exception: If the specified IP address is already in use or invalid.
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
        tuple: A tuple containing the VPN IP address of the base station, or None if not found.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT vpn_ip FROM hosts WHERE group_name = 'base_station'")
    result = cursor.fetchone()
    conn.close()
    return result

def ping_host(vpn_ip):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", vpn_ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        is_alive = result.returncode == 0
        ping_ms = None
        if is_alive:
            # Parse ping output for time=XX ms
            for line in result.stdout.splitlines():
                if "time=" in line:
                    try:
                        ping_ms = float(line.split("time=")[-1].split()[0])
                    except Exception:
                        ping_ms = None
                    break
        return is_alive, ping_ms
    except Exception:
        return False, None

def get_hosts():
    """
    Retrieves all hosts from the database and pings each host to get its status and ping time.

    Returns:
        list of tuples: Each tuple contains (id, vpn_ip, group_name, ping_ms) of a host.
        If the host is unreachable, ping_ms will be -1.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, vpn_ip, group_name FROM hosts")
    results = cursor.fetchall()
    conn.close()

    hosts_with_status = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        vpn_ips = [row[1] for row in results]
        ping_results = list(executor.map(ping_host, vpn_ips))
        for row, (is_alive, ping_ms) in zip(results, ping_results):
            if not is_alive or ping_ms is None:
                ping_ms = -1
            hosts_with_status.append(row + (ping_ms,))

    results = hosts_with_status
    return results

def remove_user(user_id):
    """
    Removes a user from the database.

    Args:
        user_id (int): The ID of the user to remove.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hosts WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def rename_group(user_id, new_group_name):
    """
    Renames the group for a given user.

    Args:
        user_id (int): The ID of the user.
        new_group_name (str): The new group name.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE hosts SET group_name = ? WHERE id = ?", (new_group_name, user_id))
    conn.commit()
    conn.close()