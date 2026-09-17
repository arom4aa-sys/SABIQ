"""SABIQ Flask application factory.

Responsibilities (kept deliberately thin):
* create and configure the Flask app
* wire up blueprints, error handlers, CORS and a lightweight rate limiter
* serve the static frontend (HTML/CSS/JS) from the project root

Security hardening relative to the v1 prototype:
* ``debug=True`` is NOT enabled in production (controlled by config/app env)
* CORS is restricted to an explicit origin allow-list
* request bodies are capped and validated before hitting the engine
* Python tracebacks are never returned to clients
* static serving refuses backend/source files and unknown extensions
* a simple in-memory rate limit protects /simulate and /compare
"""

from __future__ import annotations

import logging
import os
import posixpath
import threading
import time

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from . import config
from .data.dataset import DatasetService, get_dataset
from .routes.ml import ml_bp
from .routes.simulation import simulation_bp

logger = logging.getLogger("sabiq")


# ---------------------------------------------------------------------------
# Lightweight in-memory rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple fixed-window rate limiter keyed by client IP."""

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._window = 60.0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            # Drop old hits; when the dict grows too large, prune stale keys.
            timestamps = [t for t in self._hits.get(key, []) if now - t < self._window]
            if len(self._hits) > 10_000:
                cutoff = now - self._window
                self._hits = {
                    k: [t for t in v if t > cutoff]
                    for k, v in self._hits.items()
                    if any(t > cutoff for t in v)
                }
            if len(timestamps) >= self.limit:
                self._hits[key] = timestamps
                return False
            timestamps.append(now)
            self._hits[key] = timestamps
            return True


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

# Only these extensions may be served to the browser. This keeps
# backend/*.py, tests, .git, etc. unreachable.
_ALLOWED_EXTENSIONS = {
    ".html",
    ".css",
    ".js",
    ".csv",
    ".txt",
    ".md",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".xlsx",
    ".pdf",
}


def _is_servable(filename: str) -> bool:
    normalized = posixpath.normpath(filename)
    if normalized.startswith(("backend", "tests", ".git")) or normalized.startswith("../"):
        return False
    if normalized == ".":
        return False
    ext = posixpath.splitext(normalized)[1].lower()
    return ext in _ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)

    app.config.update(
        TESTING=testing,
        DEBUG=config.DEBUG if not testing else False,
        MAX_CONTENT_LENGTH=config.MAX_JSON_BYTES,
        JSON_SORT_KEYS=False,
    )

    app.extensions["sabiq_dataset"] = get_dataset()

    # --- CORS (restricted) -----------------------------------------------
    CORS(
        app,
        resources={
            r"/simulate": {"origins": config.ALLOWED_ORIGINS},
            r"/compare": {"origins": config.ALLOWED_ORIGINS},
            r"/api/ml/*": {"origins": config.ALLOWED_ORIGINS},
        },
    )

    # --- Rate limiter -----------------------------------------------------
    rate_limit = (
        1_000_000 if testing else config.RATE_LIMIT_PER_MINUTE
    )  # effectively disabled in tests
    limiter = RateLimiter(rate_limit)
    app.extensions["sabiq_rate_limiter"] = limiter

    @app.before_request
    def _limit_requests() -> None:
        if request.endpoint in ("simulation.simulate", "simulation.compare"):
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            key = str(client_ip).split(",")[0].strip()
            if not limiter.allow(key):
                return _error("RATE_LIMITED", "Too many requests. Please try again shortly.", 429)

    # --- Blueprints -------------------------------------------------------
    app.register_blueprint(simulation_bp)
    app.register_blueprint(ml_bp)

    # --- Health -----------------------------------------------------------
    @app.get("/health")
    def health():
        dataset = app.extensions["sabiq_dataset"]
        from .ml.sector_model import get_sector_model

        model = get_sector_model()
        ml_ready = bool(
            config.ML_ENABLED and model is not None and model.is_fitted
        )
        return jsonify(
            {
                "success": True,
                "status": "ok",
                "datasetLoaded": dataset.is_available(),
                "mlReady": ml_ready,
                "mlMethod": model.quality()["method"] if ml_ready else None,
            }
        )

    # --- Frontend ---------------------------------------------------------
    @app.get("/")
    def home():
        return send_from_directory(config.BASE_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename):
        if not _is_servable(filename):
            return _error("NOT_FOUND", "Resource not found.", 404)
        return send_from_directory(config.BASE_DIR, filename)

    # --- API error handling ----------------------------------------------
    @app.errorhandler(400)
    def bad_request(_exc):
        return _error("BAD_REQUEST", "Request body could not be parsed.", 400)

    @app.errorhandler(404)
    def not_found(_exc):
        if request.path.startswith(("/simulate", "/compare", "/api")):
            return _error("NOT_FOUND", "Endpoint not found.", 404)
        html = "<h1>404</h1><p>The requested page could not be found.</p>"
        return html, 404

    @app.errorhandler(413)
    def too_large(_exc):
        return _error("PAYLOAD_TOO_LARGE", "Request body is too large.", 413)

    @app.errorhandler(429)
    def too_many(_exc):
        return _error("RATE_LIMITED", "Too many requests. Please try again shortly.", 429)

    @app.errorhandler(Exception)
    def unhandled(exc):  # noqa: ANN001
        # Never leak internals; log server-side only.
        logger.exception("Unhandled error: %s", exc)
        if request.path.startswith(("/simulate", "/compare", "/api")):
            return _error(
                "INTERNAL_ERROR",
                "An unexpected error occurred while processing the request.",
                500,
            )
        return _error("INTERNAL_ERROR", "An unexpected error occurred.", 500)

    return app


def _error(code: str, message: str, status: int):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status