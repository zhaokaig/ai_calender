from flask import Flask

from .config import Config
from .database import init_app as init_database
from .routes import auth_bp, health_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    init_database(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)

    return app
