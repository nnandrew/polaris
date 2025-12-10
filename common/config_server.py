from threading import Thread, Event
import sys
import os

from flask import Flask, request, jsonify

try:
    from common.ubx_config import UBXConfig
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    from ubx_config import UBXConfig

class ConfigServer:
    """
    A simple Flask server to handle UBX configuration requests.
    """

    def __init__(self, ubx_config: UBXConfig, is_base_station: bool = False, ppp_stop_event: Event = None):
        self.app = Flask(__name__)
        self.ubx_config = ubx_config
        self.app.add_url_rule("/config", "config", self._config, methods=["POST"])
        if is_base_station:
            self.app.add_url_rule("/fixed", "fixed", self._fixed, methods=["POST"])
            self.ppp_stop_event=ppp_stop_event

    def run(self):
        self.server_thread = Thread(target=self.app.run, kwargs={"host": "0.0.0.0", "port": 80}, daemon=True)
        self.server_thread.start()

    def _config(self) -> tuple[dict[str, str], int]:
        if not request.is_json:
            return jsonify({"error": "Invalid request: Content-Type must be application/json"}), 400
        data = request.get_json()
        config_data = data.get("config")
        if not config_data:
            return jsonify({"error": "Invalid request: 'config' key not found in request body"}), 400
        try:
            config_msg = self.ubx_config.convert_u_center_config_from_string(config_data)
            success, msg = self.ubx_config.send_config(config_msg)
            if success:
                return jsonify({"message": "Configuration applied successfully"}), 200
            else:
                return jsonify({"error": f"Failed to apply configuration: {msg}"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to apply configuration: {e}"}), 500
        
    def _fixed(self) -> tuple[dict[str, str], int]:
        if not request.is_json:
            return jsonify({"error": "Invalid request: Content-Type must be application/json"}), 400
        data = request.get_json()
        coords = data.get("coords")
        if not coords:
            return jsonify({"error": "Invalid request: 'coordinates' key not found in request body"}), 400
        try:
            lat = coords.get("lat")
            lon = coords.get("lon")
            height = coords.get("height")
            success, msg = self.ubx_config.send_fixed(lat, lon, height)
            if success:
                # Disable Calibration Routine
                self.ppp_stop_event.set()
                return jsonify({"message": "Fixed configuration applied successfully"}), 200
            else:
                return jsonify({"error": f"Failed to apply fixed configuration: {msg}"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to apply fixed configuration: {e}"}), 500
                