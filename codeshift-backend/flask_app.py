"""CodeShift backend entry point."""

import os

from flask import Flask, jsonify
from flask_cors import CORS

from api.cross_language_routes import cross_language_bp
from api.version_upgrade_routes import version_upgrade_bp

# Requests carry a single source file; anything larger is almost certainly abuse.
MAX_CONTENT_LENGTH = 1 * 1024 * 1024

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}})

    app.register_blueprint(cross_language_bp, url_prefix="/api")
    app.register_blueprint(version_upgrade_bp, url_prefix="/api")

    @app.route("/")
    def health():
        return jsonify({
            "status": "running",
            "service": "CodeShift Migration Backend",
            "endpoints": ["/api/cross-language", "/api/version-upgrade"],
        })

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )