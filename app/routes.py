from flask import jsonify, request
from app import db
from app.models import User, Organisation, UserOrganisation
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
import uuid


def register_routes(app):

    @app.route("/")
    def home_page():
        return "<h1>Safaricom Auth API</h1>"

    def add_error_to_list(errors_list, field, message):
        errors_list.append({
            "field": field,
            "message": message
        })

    # ─────────────────────────────────────────────────────────────
    # REGISTER
    # ─────────────────────────────────────────────────────────────
    @app.route("/auth/register", methods=['POST'])
    def register_user():
        data = request.get_json() or {}
        errors_list = []

        first_name = data.get('firstName')
        last_name = data.get('lastName')
        email = data.get('email')
        password = data.get('password')

        if not first_name:
            add_error_to_list(errors_list, "firstName", "First name is required")
        if not last_name:
            add_error_to_list(errors_list, "lastName", "Last name is required")
        if not email:
            add_error_to_list(errors_list, "email", "Email is required")
        if not password:
            add_error_to_list(errors_list, "password", "Password is required")

        # Only check DB if email exists
        if email and User.query.filter_by(email=email).first():
            add_error_to_list(errors_list, "email", "Email Address already in use")

        if errors_list:
            return jsonify({
                "status": "Bad request",
                "message": "Registration unsuccessful",
                "errors": errors_list
            }), 400

        hashed_password = generate_password_hash(password)

        new_user = User(
            userid=str(uuid.uuid4()),
            firstname=first_name,
            lastname=last_name,
            email=email,
            password=hashed_password,
            phone=data.get('phone')
        )

        org_name = f"{new_user.firstname}'s organisation"

        try:
            with db.session.begin_nested():
                db.session.add(new_user)
                db.session.flush()

                new_org = Organisation(
                    orgid=str(uuid.uuid4()),
                    name=org_name,
                    description=f"{org_name} description"
                )
                db.session.add(new_org)

                user_org = UserOrganisation(
                    userid=new_user.userid,
                    orgid=new_org.orgid
                )
                db.session.add(user_org)

            db.session.commit()

            jwt_token = create_access_token(identity=str(new_user.userid))

            return jsonify({
                "status": "success",
                "message": "Registration successful",
                "data": {
                    "accessToken": jwt_token,
                    "user": {
                        "userId": new_user.userid,
                        "firstName": new_user.firstname,
                        "lastName": new_user.lastname,
                        "email": new_user.email,
                        "phone": new_user.phone,
                    }
                }
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": "Registration unsuccessful",
                "error": str(e)
            }), 500

    # ─────────────────────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────────────────────
    @app.route("/auth/login", methods=['POST'])
    def login_user():
        data = request.get_json() or {}

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"message": "Email and password are required"}), 400

        existing_user = User.query.filter_by(email=email).first()

        if not existing_user:
            return jsonify({"message": "User not found"}), 404

        if not check_password_hash(existing_user.password, password):
            return jsonify({"message": "Incorrect password"}), 401

        jwt_token = create_access_token(identity=str(existing_user.userid))

        return jsonify({
            "status": "success",
            "message": "Login successful",
            "data": {
                "accessToken": jwt_token,
                "user": {
                    "userId": existing_user.userid,
                    "firstName": existing_user.firstname,
                    "lastName": existing_user.lastname,
                    "email": existing_user.email,
                    "phone": existing_user.phone
                }
            }
        }), 200

    # ─────────────────────────────────────────────────────────────
    # USERS
    # ─────────────────────────────────────────────────────────────
    @app.route("/api/users/<id>", methods=['GET'])
    def get_users_by_id(id):
        user = User.query.get(id)

        if not user:
            return jsonify({"message": "User not found"}), 404

        return jsonify({
            "status": "success",
            "message": "User found",
            "data": {
                "userid": user.userid,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email,
                "phone": user.phone
            }
        }), 200

    # ─────────────────────────────────────────────────────────────
    # ORGANISATIONS
    # ─────────────────────────────────────────────────────────────
    @app.route("/api/organisations", methods=['GET'])
    @jwt_required()
    def get_organizations():
        userid = get_jwt_identity()

        user_organizations = db.session.query(Organisation).join(UserOrganisation).filter(
            UserOrganisation.userid == userid
        ).all()

        organizations = [{
            "orgId": org.orgid,
            "name": org.name,
            "description": org.description or ""
        } for org in user_organizations]

        return jsonify({
            "status": "success",
            "message": "Organizations retrieved successfully",
            "data": {
                "organisation": organizations
            }
        }), 200

    @app.route("/api/organisations/<orgId>", methods=['GET'])
    @jwt_required()
    def get_organization_by_id(orgId):
        organization = Organisation.query.get(orgId)

        if not organization:
            return jsonify({"message": "Organization not found"}), 404

        return jsonify({
            "status": "success",
            "message": "Organization found",
            "data": {
                "orgId": organization.orgid,
                "name": organization.name,
                "description": organization.description or ""
            }
        }), 200

    @app.route("/api/organisations", methods=['POST'])
    @jwt_required()
    def create_organization():
        data = request.get_json() or {}

        name = data.get('name')
        description = data.get('description')

        if not name:
            return jsonify({"message": "Name is required"}), 400

        new_organization = Organisation(
            orgid=str(uuid.uuid4()),
            name=name,
            description=description
        )

        db.session.add(new_organization)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Organization created successfully",
            "data": {
                "orgId": new_organization.orgid,
                "name": new_organization.name,
                "description": new_organization.description or ""
            }
        }), 201

    @app.route("/api/organisations/<orgId>/users", methods=['POST'])
    def add_user_to_organization(orgId):
        data = request.get_json() or {}

        userid = data.get('userId')
        if not userid:
            return jsonify({"message": "User ID is required"}), 400

        organization = Organisation.query.filter_by(orgid=orgId).first()
        if not organization:
            return jsonify({
                "status": "error",
                "message": "Organization not found"
            }), 404

        new_user_organization = UserOrganisation(
            userid=userid,
            orgid=orgId
        )

        db.session.add(new_user_organization)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "User added to organization successfully",
            "data": {
                "userId": userid,
                "orgId": orgId
            }
        }), 201
