from datetime import datetime
from __init__ import db
from __init__ import app


class SobrietyProfile(db.Model):
    __tablename__ = "sobriety_profiles"
    __bind_key__ = "sobriety"
    id = db.Column(db.Integer, primary_key=True)

    # Link to existing users table
    user_id = db.Column(db.Integer, nullable=False, unique=True)

    sobriety_start_date = db.Column(db.Date, nullable=True)

    current_streak_days = db.Column(db.Integer, default=0, nullable=False)
    longest_streak_days = db.Column(db.Integer, default=0, nullable=False)
    checkin_streak_days = db.Column(db.Integer, default=0, nullable=False)

    total_points = db.Column(db.Integer, default=0, nullable=False)

    garden_level = db.Column(db.Integer, default=0, nullable=False)
    garden_xp = db.Column(db.Integer, default=0, nullable=False)

    last_checkin_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __init__(self, user_id, sobriety_start_date=None):
        self.user_id = user_id
        self.sobriety_start_date = sobriety_start_date

    def read(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "sobriety_start_date": self.sobriety_start_date.isoformat() if self.sobriety_start_date else None,
            "current_streak_days": self.current_streak_days,
            "longest_streak_days": self.longest_streak_days,
            "checkin_streak_days": self.checkin_streak_days,
            "total_points": self.total_points,
            "garden_level": self.garden_level,
            "garden_xp": self.garden_xp,
            "last_checkin_date": self.last_checkin_date.isoformat() if self.last_checkin_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DailyCheckin(db.Model):
    __tablename__ = "daily_checkins"
    __bind_key__ = "sobriety"
    id = db.Column(db.Integer, primary_key=True)

    # Link to existing users table
    user_id = db.Column(db.Integer, nullable=False)

    date = db.Column(db.Date, nullable=False)

    mood_score = db.Column(db.Integer, nullable=False)
    stress_score = db.Column(db.Integer, nullable=False)
    craving_score = db.Column(db.Integer, nullable=False)
    sleep_hours = db.Column(db.Float, nullable=False)

    stayed_sober_today = db.Column(db.Boolean, nullable=False)

    attended_meeting = db.Column(db.Boolean, default=False, nullable=False)
    exercise_done = db.Column(db.Boolean, default=False, nullable=False)
    journal_note = db.Column(db.Text, nullable=True)

    risk_score = db.Column(db.Float, nullable=True)
    risk_level = db.Column(db.String(20), nullable=True)

    points_earned = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(
        self,
        user_id,
        date,
        mood_score,
        stress_score,
        craving_score,
        sleep_hours,
        stayed_sober_today,
        attended_meeting=False,
        exercise_done=False,
        journal_note=None,
        risk_score=None,
        risk_level=None,
        points_earned=0
    ):
        self.user_id = user_id
        self.date = date
        self.mood_score = mood_score
        self.stress_score = stress_score
        self.craving_score = craving_score
        self.sleep_hours = sleep_hours
        self.stayed_sober_today = stayed_sober_today
        self.attended_meeting = attended_meeting
        self.exercise_done = exercise_done
        self.journal_note = journal_note
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.points_earned = points_earned

    def read(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "mood_score": self.mood_score,
            "stress_score": self.stress_score,
            "craving_score": self.craving_score,
            "sleep_hours": self.sleep_hours,
            "stayed_sober_today": self.stayed_sober_today,
            "attended_meeting": self.attended_meeting,
            "exercise_done": self.exercise_done,
            "journal_note": self.journal_note,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "points_earned": self.points_earned,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserReward(db.Model):
    __tablename__ = "user_rewards"
    __bind_key__ = "sobriety"
    id = db.Column(db.Integer, primary_key=True)

    # Link to existing users table
    user_id = db.Column(db.Integer, nullable=False)

    reward_name = db.Column(db.String(100), nullable=False)
    points_cost = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="redeemed", nullable=False)

    redeemed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, user_id, reward_name, points_cost, status="redeemed"):
        self.user_id = user_id
        self.reward_name = reward_name
        self.points_cost = points_cost
        self.status = status

    def read(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "reward_name": self.reward_name,
            "points_cost": self.points_cost,
            "status": self.status,
            "redeemed_at": self.redeemed_at.isoformat() if self.redeemed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


def initSobrietyTables():
    with app.app_context():
        db.create_all()