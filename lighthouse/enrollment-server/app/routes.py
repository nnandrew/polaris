"""
Defines the API routes for the Nebula Enrollment Server.

This module contains the Flask Blueprint for the main API endpoints, including
enrollment and administration.
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

@main_bp.route('/api/enroll', methods=['GET', 'POST'])
def enroll():
    """
    Handles node enrollment requests via API (GET) and admin panel (POST).

    GET: Requires 'LIGHTHOUSE_NETWORK_KEY' and 'group_name' as query parameters.
    POST: Requires admin session and 'group_name' as form data.

    Returns:
        A Flask response object containing the config file or an error message.
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
    Return VPN IP of requesting host.
    """
    # TODO: This probably needs to be translated to the Nebula IP
    return flask.request.remote_addr

@main_bp.route('/admin/', methods=['GET'])
def admin():
    if not flask.session.get('logged_in'):
        return flask.render_template('admin.html')
    hosts = nebula.get_hosts()
    return flask.render_template('admin.html', hosts=hosts)

@main_bp.route('/admin/login', methods=['POST'])
def login():
    password = flask.request.form.get('password')
    if password == flask.current_app.config.get("LIGHTHOUSE_NETWORK_KEY"):
        flask.session['logged_in'] = True
    else:
        return flask.render_template('admin.html', error='Invalid password')
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/admin/logout')
def logout():
    flask.session.pop('logged_in', None)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/remove', methods=['POST'])
def remove_user():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    if user_id:
        nebula.remove_user(user_id)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/api/rename', methods=['POST'])
def rename_group():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    new_group_name = flask.request.form.get('new_group_name')
    if user_id and new_group_name:
        nebula.rename_group(user_id, new_group_name)
    return flask.redirect(flask.url_for('main.admin'))
