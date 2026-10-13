"""Application factory for El Rincón Didáctico."""
import os

from flask import Flask


def create_app():
    app = Flask(__name__)

    # Production secrets are supplied by Alwaysdata environment variables.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload limit

    if not app.config["SECRET_KEY"] and os.environ.get("FLASK_DEBUG") != "1":
        app.logger.warning(
            "SECRET_KEY is not configured. Set it in Alwaysdata before enabling sessions/admin."
        )

    from app.routes import main
    app.register_blueprint(main)

    return app
