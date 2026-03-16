from datetime import date
import os
import joblib
import pandas as pd

from model.user import User
from model.sobriety_models import SobrietyProfile, DailyCheckin
from api.sobriety_utils import GARDEN_LEVELS, SOBRIETY_MILESTONES, POINT_RULES
from __init__ import db


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "sobriety_risk_model.pkl")

try:
    ML_MODEL = joblib.load(MODEL_PATH)
except Exception:
    ML_MODEL = None


ML_FEATURE_COLUMNS = [
    "age",
    "education",
    "nscore",
    "escore",
    "oscore",
    "ascore",
    "cscore",
    "impulsive",
    "ss",
    "baseline_vulnerability",
    "mood_score",
    "stress_score",
    "craving_score",
    "sleep_hours",
    "attended_meeting",
    "exercise_done",
    "journal_entry_present",
    "stayed_sober_today",
    "current_streak_days",
    "checkin_streak_days",
    "days_since_last_relapse",
    "avg_mood_last_3",
    "avg_stress_last_3",
    "avg_craving_last_3",
    "avg_sleep_last_3",
    "craving_delta_3",
    "stress_delta_3",
    "sleep_delta_3",
    "recent_not_sober_flag",
    "high_risk_count_last_3",
]


def process_daily_checkin(
    user_id,
    mood_score,
    stress_score,
    craving_score,
    sleep_hours,
    stayed_sober_today,
    attended_meeting=False,
    exercise_done=False,
    journal_note=None
):
    profile = get_or_create_sobriety_profile(user_id)
    today = date.today()

    existing_checkin = DailyCheckin.query.filter_by(user_id=user_id, date=today).first()
    if existing_checkin:
        return {
            "success": False,
            "message": "You have already submitted a check-in for today."
        }

    risk_score = calculate_risk_score(
        mood_score=mood_score,
        stress_score=stress_score,
        craving_score=craving_score,
        sleep_hours=sleep_hours,
        attended_meeting=attended_meeting,
        exercise_done=exercise_done
    )

    risk_level = determine_risk_level(risk_score)

    points_earned = calculate_checkin_points(
        craving_score=craving_score,
        stayed_sober_today=stayed_sober_today,
        attended_meeting=attended_meeting,
        exercise_done=exercise_done,
        journal_note=journal_note
    )

    xp_earned = calculate_garden_xp(
        stayed_sober_today=stayed_sober_today,
        attended_meeting=attended_meeting,
        exercise_done=exercise_done,
        journal_note=journal_note
    )

    # Check-in streak
    if profile.last_checkin_date is None:
        profile.checkin_streak_days = 1
    else:
        days_since_last = (today - profile.last_checkin_date).days
        if days_since_last == 1:
            profile.checkin_streak_days += 1
        elif days_since_last > 1:
            profile.checkin_streak_days = 1

    # Sobriety streak
    if stayed_sober_today:
        if profile.last_checkin_date is None:
            profile.current_streak_days = 1
        else:
            days_since_last = (today - profile.last_checkin_date).days
            if profile.current_streak_days == 0:
                profile.current_streak_days = 1
            elif days_since_last == 1:
                profile.current_streak_days += 1
            elif days_since_last > 1:
                profile.current_streak_days = 1

        profile.longest_streak_days = max(
            profile.longest_streak_days,
            profile.current_streak_days
        )
    else:
        profile.current_streak_days = 0

    profile.total_points += points_earned
    profile.garden_xp += xp_earned
    profile.garden_level = calculate_garden_level(profile.garden_xp)
    profile.last_checkin_date = today

    checkin = DailyCheckin(
        user_id=user_id,
        date=today,
        mood_score=mood_score,
        stress_score=stress_score,
        craving_score=craving_score,
        sleep_hours=sleep_hours,
        stayed_sober_today=stayed_sober_today,
        attended_meeting=attended_meeting,
        exercise_done=exercise_done,
        journal_note=journal_note,
        risk_score=risk_score,
        risk_level=risk_level,
        points_earned=points_earned
    )

    db.session.add(checkin)
    db.session.commit()

    return {
        "success": True,
        "profile": profile.read(),
        "checkin": checkin.read()
    }


def get_sobriety_dashboard(user_id):
    profile = get_or_create_sobriety_profile(user_id)

    recent_checkins = (
        DailyCheckin.query
        .filter_by(user_id=user_id)
        .order_by(DailyCheckin.date.desc(), DailyCheckin.created_at.desc())
        .limit(7)
        .all()
    )

    next_milestone = get_next_milestone(profile.current_streak_days)

    garden_summary = {
        "level": profile.garden_level,
        "label": GARDEN_LEVELS.get(profile.garden_level, "Unknown"),
        "xp": profile.garden_xp,
        "xp_to_next_level": get_xp_to_next_level(profile.garden_xp)
    }

    ml_prediction = predict_ml_support_level(user_id, profile, recent_checkins)

    return {
        "success": True,
        "profile": profile.read(),
        "recent_checkins": [checkin.read() for checkin in recent_checkins],
        "next_milestone": next_milestone,
        "garden": garden_summary,
        "ml_risk_score": ml_prediction["ml_risk_score"],
        "ml_risk_level": ml_prediction["ml_risk_level"],
        "ml_support_message": ml_prediction["ml_support_message"],
        "ml_suggested_action": ml_prediction["ml_suggested_action"]
    }


def get_or_create_sobriety_profile(user_id):
    profile = SobrietyProfile.query.filter_by(user_id=user_id).first()

    if profile is None:
        profile = SobrietyProfile(user_id=user_id, sobriety_start_date=None)
        db.session.add(profile)
        db.session.commit()

    return profile


def sync_sobriety_profiles():
    users = User.query.all()
    created_count = 0

    for user in users:
        existing_profile = SobrietyProfile.query.filter_by(user_id=user.id).first()

        if existing_profile is None:
            profile = SobrietyProfile(user_id=user.id, sobriety_start_date=None)
            db.session.add(profile)
            created_count += 1

    db.session.commit()

    return {
        "success": True,
        "users_checked": len(users),
        "profiles_created": created_count
    }


def determine_risk_level(risk_score):
    if risk_score < 3:
        return "low"
    elif risk_score < 6:
        return "medium"
    return "high"


def calculate_risk_score(
    mood_score,
    stress_score,
    craving_score,
    sleep_hours,
    attended_meeting=False,
    exercise_done=False
):
    risk_score = (
        craving_score * 0.35 +
        stress_score * 0.25 +
        max(0, 8 - sleep_hours) * 0.15 +
        max(0, 6 - mood_score) * 0.15
    )

    if attended_meeting:
        risk_score -= 2

    if exercise_done:
        risk_score -= 1

    return round(max(risk_score, 0), 2)


def calculate_checkin_points(
    craving_score,
    stayed_sober_today,
    attended_meeting=False,
    exercise_done=False,
    journal_note=None,
    milestone_bonus=0
):
    points = POINT_RULES["daily_checkin"]

    if craving_score is not None:
        points += POINT_RULES["honest_craving_log"]

    if stayed_sober_today:
        points += 10

    if attended_meeting:
        points += POINT_RULES["attended_meeting"]

    if exercise_done:
        points += POINT_RULES["exercise_done"]

    if journal_note and journal_note.strip():
        points += POINT_RULES["journal_entry"]

    points += milestone_bonus
    return points


def calculate_garden_xp(
    stayed_sober_today,
    attended_meeting=False,
    exercise_done=False,
    journal_note=None
):
    xp = 10

    if stayed_sober_today:
        xp += 15

    if attended_meeting:
        xp += 5

    if exercise_done:
        xp += 5

    if journal_note and journal_note.strip():
        xp += 5

    return xp


def calculate_garden_level(garden_xp):
    if garden_xp >= 400:
        return 4
    if garden_xp >= 250:
        return 3
    if garden_xp >= 120:
        return 2
    if garden_xp >= 40:
        return 1
    return 0


def get_xp_to_next_level(garden_xp):
    thresholds = [40, 120, 250, 400]

    for threshold in thresholds:
        if garden_xp < threshold:
            return threshold

    return thresholds[-1]


def get_next_milestone(current_streak_days):
    for milestone in SOBRIETY_MILESTONES:
        if current_streak_days < milestone:
            return {
                "days": milestone,
                "days_remaining": milestone - current_streak_days
            }

    return {
        "days": SOBRIETY_MILESTONES[-1],
        "days_remaining": 0
    }


def get_recent_checkins_for_analysis(user_id, limit=5):
    return (
        DailyCheckin.query
        .filter_by(user_id=user_id)
        .order_by(DailyCheckin.date.desc(), DailyCheckin.created_at.desc())
        .limit(limit)
        .all()
    )


def compute_trend_metrics(checkins):
    if not checkins:
        return {
            "avg_mood": 5.0,
            "avg_craving": 5.0,
            "avg_stress": 5.0,
            "avg_sleep": 8.0,
            "high_risk_count": 0,
            "recent_not_sober": False,
            "craving_delta": 0.0,
            "stress_delta": 0.0,
            "sleep_delta": 0.0,
        }

    ordered = list(reversed(checkins))

    moods = [c.mood_score for c in ordered]
    cravings = [c.craving_score for c in ordered]
    stresses = [c.stress_score for c in ordered]
    sleeps = [c.sleep_hours for c in ordered]

    return {
        "avg_mood": round(sum(moods) / len(moods), 2),
        "avg_craving": round(sum(cravings) / len(cravings), 2),
        "avg_stress": round(sum(stresses) / len(stresses), 2),
        "avg_sleep": round(sum(sleeps) / len(sleeps), 2),
        "high_risk_count": sum(1 for c in ordered if c.risk_level == "high"),
        "recent_not_sober": any(c.stayed_sober_today is False for c in ordered[-3:]),
        "craving_delta": round(cravings[-1] - cravings[0], 2) if len(cravings) >= 2 else 0.0,
        "stress_delta": round(stresses[-1] - stresses[0], 2) if len(stresses) >= 2 else 0.0,
        "sleep_delta": round(sleeps[-1] - sleeps[0], 2) if len(sleeps) >= 2 else 0.0,
    }


def calculate_baseline_vulnerability(profile, latest_checkin):
    """
    Placeholder baseline vulnerability for now because your app does not yet
    collect personality-trait fields like nscore/cscore/impulsive/ss.
    """
    if latest_checkin is None:
        return 0.0

    score = (
        0.35 * latest_checkin.craving_score +
        0.25 * latest_checkin.stress_score +
        0.15 * max(0, 8 - latest_checkin.sleep_hours) +
        0.10 * max(0, 6 - latest_checkin.mood_score)
    )

    return round(score, 3)


def build_ml_feature_row(profile, recent_checkins):
    latest = recent_checkins[0] if recent_checkins else None
    metrics = compute_trend_metrics(recent_checkins)

    if latest is None:
        row = {
            "age": 0.0,
            "education": 0.0,
            "nscore": 0.0,
            "escore": 0.0,
            "oscore": 0.0,
            "ascore": 0.0,
            "cscore": 0.0,
            "impulsive": 0.0,
            "ss": 0.0,
            "baseline_vulnerability": 0.0,
            "mood_score": 5.0,
            "stress_score": 5.0,
            "craving_score": 5.0,
            "sleep_hours": 8.0,
            "attended_meeting": 0,
            "exercise_done": 0,
            "journal_entry_present": 0,
            "stayed_sober_today": 1,
            "current_streak_days": profile.current_streak_days,
            "checkin_streak_days": profile.checkin_streak_days,
            "days_since_last_relapse": profile.current_streak_days,
            "avg_mood_last_3": 5.0,
            "avg_stress_last_3": 5.0,
            "avg_craving_last_3": 5.0,
            "avg_sleep_last_3": 8.0,
            "craving_delta_3": 0.0,
            "stress_delta_3": 0.0,
            "sleep_delta_3": 0.0,
            "recent_not_sober_flag": 0,
            "high_risk_count_last_3": 0,
        }
    else:
        days_since_last_relapse = 0 if latest.stayed_sober_today is False else profile.current_streak_days

        row = {
            "age": 0.0,
            "education": 0.0,
            "nscore": 0.0,
            "escore": 0.0,
            "oscore": 0.0,
            "ascore": 0.0,
            "cscore": 0.0,
            "impulsive": 0.0,
            "ss": 0.0,
            "baseline_vulnerability": calculate_baseline_vulnerability(profile, latest),
            "mood_score": latest.mood_score,
            "stress_score": latest.stress_score,
            "craving_score": latest.craving_score,
            "sleep_hours": latest.sleep_hours,
            "attended_meeting": int(latest.attended_meeting),
            "exercise_done": int(latest.exercise_done),
            "journal_entry_present": int(bool(latest.journal_note and latest.journal_note.strip())),
            "stayed_sober_today": int(latest.stayed_sober_today),
            "current_streak_days": profile.current_streak_days,
            "checkin_streak_days": profile.checkin_streak_days,
            "days_since_last_relapse": days_since_last_relapse,
            "avg_mood_last_3": metrics["avg_mood"],
            "avg_stress_last_3": metrics["avg_stress"],
            "avg_craving_last_3": metrics["avg_craving"],
            "avg_sleep_last_3": metrics["avg_sleep"],
            "craving_delta_3": metrics["craving_delta"],
            "stress_delta_3": metrics["stress_delta"],
            "sleep_delta_3": metrics["sleep_delta"],
            "recent_not_sober_flag": int(metrics["recent_not_sober"]),
            "high_risk_count_last_3": metrics["high_risk_count"],
        }

    return pd.DataFrame([row], columns=ML_FEATURE_COLUMNS)


def ml_score_to_level(score):
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def get_ml_support_message(ml_risk_level):
    if ml_risk_level == "low":
        return "Your recent pattern looks stable. Keep protecting the habits that are helping."
    if ml_risk_level == "medium":
        return "Your recent check-ins suggest some increased support need. Slow down and choose one stabilizing action today."
    return "Your recent pattern suggests elevated support need. Consider reaching out, attending a meeting, or changing your environment right now."


def get_ml_suggested_action(ml_risk_level):
    if ml_risk_level == "low":
        return "Repeat one healthy routine that has been helping you stay steady."
    if ml_risk_level == "medium":
        return "Hydrate, reduce friction, and make one support-oriented choice before the day gets harder."
    return "Use a high-support action now: text someone, attend a meeting, or leave a triggering environment."


def predict_ml_support_level(user_id, profile, recent_checkins):
    if ML_MODEL is None:
        return {
            "ml_risk_score": None,
            "ml_risk_level": "unknown",
            "ml_support_message": "ML model is not available yet.",
            "ml_suggested_action": "Continue checking in daily."
        }

    feature_df = build_ml_feature_row(profile, recent_checkins)
    risk_score = float(ML_MODEL.predict_proba(feature_df)[0][1])
    risk_level = ml_score_to_level(risk_score)

    return {
        "ml_risk_score": round(risk_score, 4),
        "ml_risk_level": risk_level,
        "ml_support_message": get_ml_support_message(risk_level),
        "ml_suggested_action": get_ml_suggested_action(risk_level)
    }