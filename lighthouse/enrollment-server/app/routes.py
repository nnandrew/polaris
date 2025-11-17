"""
Defines the API routes for the Nebula Enrollment Server.

This module contains the Flask Blueprint for the main API endpoints,
including enrollment and administration functionality.
"""
from app import nebula
import sqlite3
import os

import flask
import requests

# Nebula network is on the 192.168.100.X/24 subnet:
# X=0: Network identifier
# X=1: Lighthouse address
# X=2-254: Host addresses
# X=255: Broadcast address

main_bp = flask.Blueprint('main', __name__)

@main_bp.route('/api/hosts/enroll', methods=['POST'])
def enroll():
    """
    Handles new node enrollment requests via API (POST).

    Expects 'group_name' in the form data.

    Returns:
        Flask response containing the allocated host_id or an error message.
    """

    group_name = flask.request.form.get('group_name')
    if not group_name:
        return "Missing group_name", 400
    if group_name.startswith("rover"):
        host_id = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_HOSTNAME'))
    elif group_name.startswith("basestation"):
        host_id = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_HOSTNAME'))
    else:
        return "Unexpected group_name", 400
    return host_id, 200

@main_bp.route('/api/hosts/<int:host_id>', methods=['POST'])
def action(host_id):
    """
    Handles host management actions via API (POST).
    Expects 'action' and optionally 'group_name' in the form data.
    Args:
        host_id (int): The host ID from the database.
    Returns:
        Flask response indicating the result of the action.
    """

    action = flask.request.form.get('action')
    match action:
        case 'enroll':
            group_name = flask.request.form.get('group_name')
            if not group_name:
                return "Missing group_name", 400
            host_id = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_HOSTNAME'), host_id)
            return host_id, 200
        case 'rename':
            group_name = flask.request.form.get('group_name')
            if group_name:
                success = nebula.rename_group(host_id, group_name)
                if success:
                    return "Host renamed", 200
                else:
                    return "Host not found", 404
            else:
                return "Missing group_name", 400
        case 'remove':
            success = nebula.remove_host(host_id)
            if not success:
                return "Host not found", 404
            os.remove(f"/home/enrollment-server/shared/config_{host_id}.yaml")
            return "Host removed", 200
        case 'config':
            # Build the target URL
            config_msg = flask.request.form.get('config_msg')
            if not config_msg:
                return "Missing config_msg", 400
            try:
                response = requests.post(
                    url = f"http://192.168.100.{host_id}/config",
                    data={"config": f"Flash {config_msg}"}, 
                    headers={"Content-Type": "application/json"},
                    timeout=3
                )
                return response.text, response.status_code
            except requests.exceptions.RequestException as e:
                flask.current_app.logger.error(f"Failed to contact host {host_id}: {str(e)}")
                return f"Failed to contact host {host_id}: {str(e)}", 500
        case _:
            return "Unknown or missing action", 400
    
@main_bp.route('/api/hosts/<int:host_id>', methods=['GET'])
def download_nebula_config(host_id):
    """
    Downloads the Nebula config file for a specific host.
    
    Args:
        host_id (int): The host ID from the database.
        
    Returns:
        Flask response containing the config file or an error message.
    """

    try:
        # Verify the host exists in the database
        conn = sqlite3.connect('./record.db')
        cursor = conn.cursor()
        cursor.execute("SELECT group_name FROM hosts WHERE id = ?", (host_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return "Host not found", 404
        
        group_name = result[0]
        
        # Handle lighthouse config (host_id = 1) which has a different filename
        if host_id == 1:
            config_path = "/home/enrollment-server/shared/config.yml"
        else:
            config_path = f"/home/enrollment-server/shared/config_{host_id}.yaml"
        download_name = f"nebula_config_{group_name}_{host_id}.yaml"
        
        # Check if file exists
        if not os.path.exists(config_path):
            flask.current_app.logger.error(f"Config file not found: {config_path}")
            return f"Config file not found for {group_name} (ID: {host_id})", 404
        
        flask.current_app.logger.info(f"Downloading config for {group_name} (ID: {host_id})")
        return flask.send_file(
            config_path, 
            as_attachment=True, 
            download_name=download_name
        )
        
    except Exception as e:
        flask.current_app.logger.error(f"Config download failed for host {host_id}: {str(e)}")
        return f"Download failed: {str(e)}", 500

    
@main_bp.route('/api/hosts/basestation', methods=['GET'])
def basestation():
    """
    Provides the VPN IP address of the NTRIP base station.

    Queries the database to find the IP address of the host belonging to the
    'base_station' group.

    Returns:
        str: The VPN IP address of the base station, or an error if not found.
    """
    result = nebula.get_base_station()
    if result:
        return result[0]
    else:
        return "Base station not found", 404
