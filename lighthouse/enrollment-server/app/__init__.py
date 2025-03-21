import flask
from .routes import main_bp 
import dotenv
import requests
import subprocess
import os
import tarfile
import nebula
import sqlite3

def create_app():

    # Download Nebula Certificate Generator if necessary
    if not os.path.exists("./shared/nebula-cert"):
    
        url = "https://github.com/slackhq/nebula/releases/download/v1.9.5/nebula-linux-amd64.tar.gz"
        response = requests.get(url)
        with open('./shared/nebula-linux-amd64.tar.gz', 'wb') as file:
            file.write(response.content)

        with tarfile.open('./shared/nebula-linux-amd64.tar.gz', 'r:gz') as tar:
            tar.extractall('./shared')
        
        os.remove('./shared/nebula-linux-amd64.tar.gz')
        os.remove('./shared/nebula')
        print("Nebula Certificate Generator Downloaded.")

    # Generate CA Key if necessary
    if not os.path.exists("./shared/ca.key"):     
        os.chdir("./shared")
        subprocess.run(["./nebula-cert", "ca", "-name", "\"Polaris\""])
        os.chdir("..")
        print("CA Key and Certificate Generated.")   
        
    # Generate Lighthouse Configuration if necessary
    if not os.path.exists("./shared/config.yml"):
        config_path = nebula.generate_nebula_config(group_name="lighthouse")
        print(f"Lighthouse Configuration Generated at {config_path}.")   

    # Initialize SQLite database
    conn = sqlite3.connect("./shared/record.db")
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vpn_ip TEXT NOT NULL,
        group_name TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

    # Configure Flask App
    app = flask.Flask(__name__)
    dotenv.load_dotenv()
    app.config["NETWORK_KEY"] = os.getenv("NETWORK_KEY")
    app.config["LIGHTHOUSE_PUBLIC_IP"] = os.getenv("LIGHTHOUSE_PUBLIC_IP")
    app.register_blueprint(main_bp)
    return app