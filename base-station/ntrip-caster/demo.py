"""
A simple Flask web server for demonstration and network testing purposes.

This application serves a single page that displays a "Network connected!"
message along with randomly generated GPS coordinates. It's useful for
verifying network connectivity to the base station.
"""
import random
from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    """
    Serves the main HTML page.

    Generates random latitude and longitude to display on the page.

    Returns:
        str: A simple HTML page with random coordinates.
    """
    lat = random.uniform(-90, 90)
    lon = random.uniform(-180, 180)
    return f'''
    <!DOCTYPE html>
    <html>
        <body>
            <h1>Network connected!</h1>
            <h2>Totally Real Coordinates: Latitude = {lat:.6f}, Longitude = {lon:.6f}</h2>
            <pre>
                 '
            *          .   
                   *       ' 
              *                * 




   *   '*
           *
                *
                       *
               *
                     *
            </pre>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)