from flask import Blueprint, jsonify, request
from api.authorize import token_required
from api.sobriety_services import (
    get_or_create_sobriety_profile,
    sync_sobriety_profiles,
    process_daily_checkin,
    get_sobriety_dashboard,
)

sobriety_api = Blueprint("sobriety_api", __name__)


@sobriety_api.route("/api/sobriety/checkin", methods=["POST"])
@token_required()
def submit_sobriety_checkin():
    data = request.get_json()

    required_fields = [
        "user_id",
        "mood_score",
        "stress_score",
        "craving_score",
        "sleep_hours",
        "stayed_sober_today"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "success": False,
                "message": f"Missing required field: {field}"
            }), 400

    result = process_daily_checkin(
        user_id=data["user_id"],
        mood_score=data["mood_score"],
        stress_score=data["stress_score"],
        craving_score=data["craving_score"],
        sleep_hours=data["sleep_hours"],
        stayed_sober_today=data["stayed_sober_today"],
        attended_meeting=data.get("attended_meeting", False),
        exercise_done=data.get("exercise_done", False),
        journal_note=data.get("journal_note")
    )

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result), 201


@sobriety_api.route("/api/sobriety/dashboard/<int:user_id>", methods=["GET"])
@token_required()
def sobriety_dashboard(user_id):
    result = get_sobriety_dashboard(user_id)
    return jsonify(result), 200


@sobriety_api.route("/api/sobriety/profile/<int:user_id>", methods=["GET"])
@token_required()
def get_sobriety_profile(user_id):
    profile = get_or_create_sobriety_profile(user_id)

    return jsonify({
        "success": True,
        "profile": profile.read()
    }), 200


@sobriety_api.route("/api/sobriety/sync-users", methods=["POST"])
def sync_users_to_sobriety():
    result = sync_sobriety_profiles()
    return jsonify(result), 200