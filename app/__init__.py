import os
from flask import Flask
from dotenv import load_dotenv

from .extensions import socketio
from .auth import load_current_user

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-fallback-key")
    app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "dev-only-jwt-secret")

    app.before_request(load_current_user)

    socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

    from .routes.auth_routes import auth_bp
    from .routes.citizen_routes import citizen_bp
    from .routes.coordinator_routes import coordinator_bp
    from .routes.api_routes import api_bp
    from .routes.main_routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(citizen_bp)
    app.register_blueprint(coordinator_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
