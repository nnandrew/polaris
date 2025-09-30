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

    GET: Requires 'LIGHTHOUSE_NETWORK_KEY' and 'group_name' as query parameters.
    POST: Requires admin session and 'group_name' as form data.

    Returns:
        Flask response containing the config file or an error message.
    """
    if flask.request.method == 'GET':
        # API enrollment
        network_key = flask.request.args.get('LIGHTHOUSE_NETWORK_KEY')
        if not network_key or network_key != flask.current_app.config.get("LIGHTHOUSE_NETWORK_KEY"):
            return "Unauthorized", 401
        group_name = flask.request.args.get('group_name')
        if not group_name:
            return "Missing group_name", 400
        ip_octet = None
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
            hosts = nebula.get_hosts()
            return flask.render_template('admin.html', hosts=hosts, error="Invalid IP octet. Must be between 2 and 254.")

    try:
        config_path = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_PUBLIC_IP'), ip_octet)
        response = flask.send_file(config_path, as_attachment=True)
        # Refresh the page after sending the file
        response.headers["Refresh"] = "0; url=" + flask.url_for('main.admin')
        response.call_on_close(lambda: os.remove(config_path))
        return response
    except Exception as e:
        flask.current_app.logger.error(f"Manual enrollment failed: {str(e)}")
        return f"Enrollment failed: {str(e)}", 500

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
    hosts = nebula.get_hosts()
    return flask.render_template('admin.html', hosts=hosts)

@main_bp.route('/nebula/login', methods=['POST'])
def login():
    """
    Handles admin login. Sets session if password matches network key.
    """
    password = flask.request.form.get('password')
    if password == flask.current_app.config.get("LIGHTHOUSE_NETWORK_KEY"):
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

@main_bp.route('/api/remove', methods=['POST'])
def remove_user():
    """
    Removes a user from the Nebula network. Requires admin session.
    """
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    if user_id:
        nebula.remove_user(user_id)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/rename', methods=['POST'])
def rename_group():
    """
    Renames a user's group in the Nebula network. Requires admin session.
    """
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    new_group_name = flask.request.form.get('new_group_name')
    if user_id and new_group_name:
        nebula.rename_group(user_id, new_group_name)
    return flask.redirect(flask.url_for('main.admin'))
