"""Backward-compatible entry point.

Kept so the previous commands still work unchanged:

    python app.py
    gunicorn app:app

The full implementation lives in the ``backend`` package.
"""

import os

from backend import config
from backend.app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )