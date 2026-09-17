"""Development entry point for SABIQ.

Usage:
    python run.py

For production use a WSGI server instead, e.g.:
    gunicorn run:app --bind 0.0.0.0:8000
"""

import os

from backend.app import create_app
from backend import config

app = create_app()


if __name__ == "__main__":
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )