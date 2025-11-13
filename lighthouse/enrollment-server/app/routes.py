"""
Defines the API routes for the Nebula Enrollment Server.

This module contains the Flask Blueprint for the main API endpoints,
including enrollment and administration functionality.
"""
import flask
import os
from app import nebula
import sqlite3

# Nebula network is on the 192.168.100.X/24 subnet:
# X=0: Network identifier
# X=1: Lighthouse address
# X=2-254: Host addresses
# X=255: Broadcast address

main_bp = flask.Blueprint('main', __name__)

@main_bp.route('/api/enroll', methods=['GET', 'POST'])
def enroll():
    """
    Handles node enrollment requests via API (GET) and admin panel (POST).

    GET: Requires 'LIGHTHOUSE_ADMIN_PASSWORD' and 'group_name' as query parameters.
    POST: Requires admin session and 'group_name' as form data.

    Returns:
        Flask response containing the config file or an error message.
    """
    if flask.request.method == 'GET':
        # API enrollment
        network_key = flask.request.args.get('LIGHTHOUSE_ADMIN_PASSWORD')
        if not network_key or network_key != flask.current_app.config.get("LIGHTHOUSE_ADMIN_PASSWORD"):
            return "Unauthorized", 401
        
        group_name = flask.request.args.get('group_name')
        if not group_name:
            return "Missing group_name", 400
        
        if group_name.startswith("rover"):
            host_id = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_HOSTNAME'))
        elif group_name.startswith("base-station"):
            host_id = 2  # Fixed IP for base station
            
        if host_id is None:
            return "Enrollment failed", 400
        return flask.redirect(flask.url_for('main.download_nebula_config', host_id=host_id, LIGHTHOUSE_ADMIN_PASSWORD=network_key))
    else:
        # Manual enrollment via admin panel
        if not flask.session.get('logged_in'):
            return flask.redirect(flask.url_for('main.admin'))
        group_name = flask.request.form.get('group_name')
        if not group_name:
            return flask.redirect(flask.url_for('main.admin'))
        ip_octet = flask.request.form.get('ip_octet')
        if not ip_octet:
            return flask.redirect(flask.url_for('main.admin'))
        ip_octet = int(ip_octet)
        if ip_octet < 2 or ip_octet > 254:
            return flask.redirect(flask.url_for('main.admin'))
        nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_HOSTNAME'), ip_octet)
        return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/ntrip', methods=['GET'])
def ntrip():
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
    return "Base station not found", 404

@main_bp.route('/api/translate', methods=['GET'])
def translate():
    """
    Returns the VPN IP of the requesting host.

    Note: This currently returns the remote address as seen by Flask,
    which may not be the Nebula VPN IP.
    """
    # TODO: Translate to Nebula VPN IP if necessary
    return flask.request.remote_addr

@main_bp.route('/nebula/', methods=['GET'])
def admin():
    """
    Renders the admin panel. Requires login for host management.
    """
    if not flask.session.get('logged_in'):
        return flask.render_template('admin.html')
    hosts = nebula.get_hosts(ping=False)
    return flask.render_template('admin.html', hosts=hosts)

@main_bp.route('/nebula/login', methods=['POST'])
def login():
    """
    Handles admin login. Sets session if password matches network key.
    """
    password = flask.request.form.get('password')
    if password == flask.current_app.config.get("LIGHTHOUSE_ADMIN_PASSWORD"):
        flask.session['logged_in'] = True
    else:
        return flask.render_template('admin.html', error='Invalid password')
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/nebula/logout')
def logout():
    """
    Logs out the admin user and redirects to admin panel.
    """
    flask.session.pop('logged_in', None)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/hosts', methods=['GET'])
def get_hosts():
    if not flask.session.get('logged_in'):
        return flask.jsonify({'error': 'Not logged in'}), 401
    hosts = nebula.get_hosts(ping=True)
    return flask.jsonify(hosts)

@main_bp.route('/api/remove', methods=['POST'])
def remove():
    """
    Removes a host from the Nebula network. Requires admin session.
    """
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    host_id = flask.request.form.get('host_id')
    if host_id:
        nebula.remove_host(host_id)
        os.remove(f"/home/enrollment-server/shared/config_{host_id}.yaml")
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/rename', methods=['POST'])
def rename():
    """
    Renames a host's group in the Nebula network. Requires admin session.
    """
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    host_id = flask.request.form.get('host_id')
    new_group_name = flask.request.form.get('new_group_name')
    if host_id and new_group_name:
        nebula.rename_group(host_id, new_group_name)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/download_nebula_config', methods=['GET', 'POST'])
def download_nebula_config():
    """
    Downloads the Nebula config file for a specific host. Requires admin session or token.
    
    Args:
        host_id (int): The host ID from the database.
        
    Returns:
        Flask response containing the config file or an error message.
    """

    if flask.request.method == 'GET':
        network_key = flask.request.args.get('LIGHTHOUSE_ADMIN_PASSWORD')
        if not network_key or network_key != flask.current_app.config.get("LIGHTHOUSE_ADMIN_PASSWORD"):
            return "Unauthorized", 401
        host_id = flask.request.args.get('host_id')
    else:
        if not flask.session.get('logged_in'):
            return flask.redirect(flask.url_for('main.admin'))
        host_id = flask.request.form.get('host_id')

    try:
        # Verify the host exists in the database
        conn = sqlite3.connect('./record.db')
        cursor = conn.cursor()
        cursor.execute("SELECT group_name FROM hosts WHERE id = ?", (host_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            flask.current_app.logger.error(f"Host {host_id} not found in database")
            return "Host not found", 404
        
        group_name = result[0]
        
        # Handle lighthouse config (host_id = 1) which has a different filename
        if host_id == 1:
            config_path = "/home/enrollment-server/shared/config.yml"
            download_name = f"nebula_config_lighthouse.yml"
        else:
            config_path = f"/home/enrollment-server/shared/config_{host_id}.yaml"
            download_name = f"nebula_config_{group_name}_{host_id}.yaml"
        
        # Check if file exists
        if not os.path.exists(config_path):
            flask.current_app.logger.error(f"Config file not found: {config_path}")
            return f"Config file not found for {group_name} (ID: {host_id}). The config may not have been generated yet.", 404
        
        flask.current_app.logger.info(f"Downloading config for {group_name} (ID: {host_id})")
        return flask.send_file(
            config_path, 
            as_attachment=True, 
            download_name=download_name
        )
        
    except Exception as e:
        flask.current_app.logger.error(f"Config download failed for host {host_id}: {str(e)}")
        return f"Download failed: {str(e)}", 500
