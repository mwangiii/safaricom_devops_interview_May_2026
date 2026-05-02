from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from prometheus_flask_exporter import PrometheusMetrics
import os

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()


def get_database_url():
    required = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]

    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise Exception(f"Missing environment variables: {missing}")

    return (
        f"postgresql://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )


def create_app():
    app = Flask(__name__)

    # ---------------- CONFIG ----------------
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["JWT_SECRET_KEY"] = os.getenv(
        "JWT_SECRET_KEY",
        "dev-secret-change-in-production"
    )
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]

    # ---------------- INIT EXTENSIONS ----------------
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # ---------------- JWT ERROR HANDLERS ----------------
    @jwt.unauthorized_loader
    def missing_token_callback(err):
        return jsonify({"message": "Missing token"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err):
        return jsonify({"message": "Invalid token"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"message": "Token expired"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"message": "Token revoked"}), 401

    # ---------------- ROUTES ----------------
    from app.routes import register_routes
    register_routes(app)

    # ---------------- METRICS ----------------
    PrometheusMetrics(app)

    print("✅ App initialized successfully")

    # ---------------- DB TABLES ----------------
    with app.app_context():
        db.create_all()

    return app
