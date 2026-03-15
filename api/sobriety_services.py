from model.user import User
from model.sobriety_models import SobrietyProfile
from model.sobriety_models import SobrietyProfile, DailyCheckin
from datetime import date

from __init__ import db
from api.sobriety_utils import SOBRIETY_MILESTONES, POINT_RULES
def process_daily_checkin(
    user_id,
    mood_score,
    stress_score,
    craving_score,
    sleep_hours,
    attended_meeting=False,
    exercise_done=False,
    journal_note=None
):
    """
    Process a daily check-in:
    - create profile if missing
    - calculate risk and points
    - save DailyCheckin
    - update sobriety profile
    """
    profile = get_or_create_sobriety_profile(user_id)

    today = date.today()

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
        attended_meeting=attended_meeting,
        exercise_done=exercise_done,
        journal_note=journal_note
    )

    # Basic check-in streak logic
    if profile.last_checkin_date is None:
        profile.checkin_streak_days = 1
    else:
        days_since_last = (today - profile.last_checkin_date).days

        if days_since_last == 1:
            profile.checkin_streak_days += 1
        elif days_since_last > 1:
            profile.checkin_streak_days = 1
        # if days_since_last == 0, same day check-in, keep streak unchanged

    profile.total_points += points_earned
    profile.last_checkin_date = today

    checkin = DailyCheckin(
        user_id=user_id,
        date=today,
        mood_score=mood_score,
        stress_score=stress_score,
        craving_score=craving_score,
        sleep_hours=sleep_hours,
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
    
def get_or_create_sobriety_profile(user_id):
    """
    Return the user's sobriety profile.
    If it does not exist yet, create it lazily.
    """
    profile = SobrietyProfile.query.filter_by(user_id=user_id).first()

    if profile is None:
        profile = SobrietyProfile(user_id=user_id, sobriety_start_date=None)
        db.session.add(profile)
        db.session.commit()

    return profile

def sync_sobriety_profiles():
    """
    Ensure every user in user_management.db has a matching
    SobrietyProfile row in sobriety_tracker.db.
    """
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
    """
    Convert a numeric risk score into a labeled support level.
    """
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
    """
    Calculate a simple weighted risk/support score.

    Higher score = more support recommended.
    """
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
    attended_meeting=False,
    exercise_done=False,
    journal_note=None,
    milestone_bonus=0
):
    """
    Calculate points earned from one daily check-in.
    """
    points = POINT_RULES["daily_checkin"]

    if craving_score is not None:
        points += POINT_RULES["honest_craving_log"]

    if attended_meeting:
        points += POINT_RULES["attended_meeting"]

    if exercise_done:
        points += POINT_RULES["exercise_done"]

    if journal_note and journal_note.strip():
        points += POINT_RULES["journal_entry"]

    points += milestone_bonus
    return points


def get_next_milestone(current_streak_days):
    """
    Return the next sobriety milestone and days remaining.
    If all milestones are passed, return the highest one.
    """
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