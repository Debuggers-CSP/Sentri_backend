from sobriety_utils import SOBRIETY_MILESTONES, POINT_RULES


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