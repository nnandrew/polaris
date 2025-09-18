"""
Defines the API routes for the Nebula Enrollment Server.

This module contains the Flask Blueprint for the main API endpoints, including
enrollment, host information, and NTRIP server discovery.
"""
import flask
import os
from app import nebula
import sqlite3

# The Nebula network is on the 192.168.100.X/24 subnet:
# X=0: Network identifier
# X=1: Lighthouse address
# X=2-254: Host addresses
# X=255: Broadcast address
    
main_bp = flask.Blueprint('main', __name__)

@main_bp.route('/api/enroll', methods=['GET'])
def enroll():
    """
    Handles a new node enrollment request.

    Authenticates the request using a 'LIGHTHOUSE_NETWORK_KEY' query parameter. If valid,
    it generates a new Nebula configuration for the specified 'group_name',
    sends the configuration file as an attachment, and then deletes the file
    from the server.

    Query Parameters:
        network_key (str): The secret key for authorizing the request.
        group_name (str): The Nebula security group for the new node.

    Returns:
        A Flask response object containing the config file or an error message.
    """
    # Authenticate Request
    network_key = flask.request.args.get('LIGHTHOUSE_NETWORK_KEY')
    if not network_key or network_key != flask.current_app.config.get("LIGHTHOUSE_NETWORK_KEY"):
        return "Unauthorized", 401
        
    # Generate Host Configuration
    group_name = flask.request.args.get('group_name')
    config_path = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_PUBLIC_IP'))
    response = flask.send_file(config_path, as_attachment=True)
    response.call_on_close(lambda: os.remove(config_path))
    
    return response

@main_bp.route('/api/ntrip', methods=['GET'])
def ntrip():
    """
    Provides the VPN IP address of the NTRIP base station.

    Queries the database to find the IP address of the host belonging to the
    'base_station' group.

    Returns:
        str: The VPN IP address of the base station, or an error if not found.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT vpn_ip FROM hosts WHERE group_name = 'base_station'")
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return "Base station not found", 404

@main_bp.route('/api/hosts', methods=['GET'])
def hosts():
    """
    Displays a list of all enrolled hosts.

    Fetches all host records from the database and renders them in an
    HTML template for debugging purposes.

    Returns:
        A rendered HTML page displaying the list of hosts.
    """
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, vpn_ip, group_name FROM hosts;")
    hosts = cursor.fetchall()
    conn.close()
    return flask.render_template('hosts.html', hosts=hosts)

@main_bp.route('/api/translate', methods=['GET'])
def translate():
    """
    Return VPN IP of requesting host.
    """
    # TODO: This probably needs to be translated to the Nebula IP
    return flask.request.remote_addr

