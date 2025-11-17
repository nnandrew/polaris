from threading import Thread
import sys
import os

from flask import Flask, request, jsonify
import requests
import dotenv

try:
    from common.ubx_config import UBXConfig
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../common")
    from ubx_config import UBXConfig

class ConfigServer:
    """
    A simple Flask server to handle UBX configuration requests.
    """

    def __init__(self, ubx_config: UBXConfig):
        self.app = Flask(__name__)
        self.ubx_config = ubx_config
        self.app.add_url_rule("/config", "config", self._config, methods=["POST"])
        # self.token = self._get_receiver_config_token()
        # self.app.before_request(self._check_token)

    def run(self):
        self.server_thread = Thread(target=self.app.run, kwargs={"host": "0.0.0.0", "port": 80}, daemon=True)
        self.server_thread.start()

    # def _get_receiver_config_token(self) -> str | None:
    #     dotenv.load_dotenv()
    #     lighthouse_host = os.getenv("LIGHTHOUSE_HOSTNAME")
    #     if not lighthouse_host:
    #         raise ValueError("LIGHTHOUSE_HOSTNAME environment variable not set")
    #     try:
    #         response = requests.get(f"https://{lighthouse_host}/api/receiver_config_token")
    #         response.raise_for_status()
    #         return response.text
    #     except requests.exceptions.RequestException as e:
    #         print(f"Error getting token: {e}")
    #         return None

    # def _check_token(self) -> tuple[dict[str, str], int]:
        # if request.endpoint == "config":
        #     if request.headers.get("Authorization") != f"Bearer {self.token}":
        #         return jsonify({"error": "Unauthorized"}), 401

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
        