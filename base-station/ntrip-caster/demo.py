import random
from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
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