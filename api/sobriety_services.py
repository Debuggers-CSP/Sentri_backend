from datetime import date

from model.user import User
from model.sobriety_models import SobrietyProfile, DailyCheckin
from api.sobriety_utils import GARDEN_LEVELS, SOBRIETY_MILESTONES, POINT_RULES
from __init__ import db


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

    return {
        "success": True,
        "profile": profile.read(),
        "recent_checkins": [checkin.read() for checkin in recent_checkins],
        "next_milestone": next_milestone,
        "garden": garden_summary
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