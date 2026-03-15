from flask import Blueprint, jsonify, request
from api.sobriety_services import (
    get_or_create_sobriety_profile,
    sync_sobriety_profiles,
    process_daily_checkin,
)

sobriety_api = Blueprint("sobriety_api", __name__)

@sobriety_api.route("/api/sobriety/checkin", methods=["POST"])
def submit_sobriety_checkin():
    data = request.get_json()

    required_fields = [
        "user_id",
        "mood_score",
        "stress_score",
        "craving_score",
        "sleep_hours"
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
        attended_meeting=data.get("attended_meeting", False),
        exercise_done=data.get("exercise_done", False),
        journal_note=data.get("journal_note")
    )

    return jsonify(result), 201
    
@sobriety_api.route("/api/sobriety/profile/<int:user_id>", methods=["GET"])
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