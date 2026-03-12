from flask import Blueprint, jsonify

sobriety_api = Blueprint("sobriety_api", __name__)

@sobriety_api.route("/api/sobriety/health", methods=["GET"])
def sobriety_health():
    return jsonify({
        "success": True,
        "message": "Sobriety API is working"
    }), 200