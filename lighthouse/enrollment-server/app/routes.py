import flask
import os
from app import nebula
import sqlite3

# 192.168.100.X/24 is the subnet for the Nebula network
# X=0 is the network identifier
# X=1 is the Lighthouse address
# X=2-254 are the host addresses 
# X=255 is the broadcast address
    
main_bp = flask.Blueprint('main', __name__)  # Create a blueprint

@main_bp.route('/api/enroll', methods=['GET'])
def enroll():
    
    # Authenticate Request
    network_key = flask.request.args.get('network_key')
    if not network_key or network_key != flask.current_app.config.get("NETWORK_KEY"):
        return "Unauthorized", 401
        
    # Generate Host Configuration
    group_name = flask.request.args.get('group_name')
    config_path = nebula.generate_nebula_config(group_name, flask.current_app.config.get('LIGHTHOUSE_PUBLIC_IP'))
    response = flask.send_file(config_path, as_attachment=True)
    response.call_on_close(os.remove(config_path))
    
    return response

@main_bp.route('/api/base-station-ip', methods=['GET'])
def baseStationIP():
    
    # Authenticate Request
    network_key = flask.request.args.get('network_key')
    if not network_key or network_key != flask.current_app.config.get("NETWORK_KEY"):
        return "Unauthorized", 401
    
    # Return Stored Base Station IP
    conn = sqlite3.connect('./record.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosts WHERE group_name = base_station")
    return cursor.fetchone()[0]
