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

@main_bp.route('/admin/add_user', methods=['POST'])
def add_user():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    group_name = flask.request.form.get('group_name')
    if group_name:
        nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_PUBLIC_IP'))
    return flask.redirect(flask.url_for('main.admin'))


@main_bp.route('/admin/remove_user', methods=['POST'])
def remove_user():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    if user_id:
        nebula.remove_user(user_id)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/admin/rename_group', methods=['POST'])
def rename_group():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    user_id = flask.request.form.get('user_id')
    new_group_name = flask.request.form.get('new_group_name')
    if user_id and new_group_name:
        nebula.rename_group(user_id, new_group_name)
    return flask.redirect(flask.url_for('main.admin'))

@main_bp.route('/admin/manual_enroll', methods=['POST'])
def manual_enroll():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('main.admin'))
    group_name = flask.request.form.get('group_name')
    if group_name:
        config_path = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_PUBLIC_IP'))
        response = flask.send_file(config_path, as_attachment=True)
        response.call_on_close(lambda: os.remove(config_path))
        return response
    return flask.redirect(flask.url_for('main.admin'))
