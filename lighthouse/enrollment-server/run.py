"""
Application runner for the Nebula Enrollment Server.

This script is the main entry point to start the Flask web server. It creates
the application instance using the factory function from the `app` package
and runs it.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=80)