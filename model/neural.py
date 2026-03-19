""" database dependencies to support sqliteDB examples """
from flask import current_app
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import json
import math

from __init__ import app, db

""" Helper Functions """

def current_timestamp():
    """Returns the current UTC timestamp."""
    return datetime.utcnow()

""" Database Models """

''' Neural Meeting Recommender — Poway Recovery Center
    KNN-based meeting recommendation engine using community tags and feedback. '''


# ══════════════════════════════════════════
#  MEETING MODEL
# ══════════════════════════════════════════

class Meeting(db.Model):
    """
    Meeting Model

    Represents a single PRC recovery meeting in the database.

    Attributes:
        id (Column): The primary key, an integer representing the unique identifier for the meeting.
        _name (Column): A string representing the name of the meeting. Cannot be null.
        _time (Column): A string representing the meeting day and time (e.g. 'Mon 7:00 AM'). Cannot be null.
        _type (Column): A string representing the meeting type (e.g. 'AA', 'NA', 'Other'). Cannot be null.
        _location (Column): A string representing the room or location. Cannot be null.
    """
    __tablename__ = 'meetings'

    id        = db.Column(db.Integer, primary_key=True)
    _name     = db.Column(db.String(255), unique=False, nullable=False)
    _time     = db.Column(db.String(255), unique=False, nullable=False)
    _type     = db.Column(db.String(50),  unique=False, nullable=False)
    _location = db.Column(db.String(255), unique=False, nullable=False)

    # One-to-many: one meeting can have many tags and feedback entries
    tags     = db.relationship('MeetingTag',      backref='meeting', cascade='all, delete-orphan', lazy=True)
    feedback = db.relationship('MeetingFeedback', backref='meeting', cascade='all, delete-orphan', lazy=True)

    def __init__(self, name, time, type, location):
        self._name     = name
        self._time     = time
        self._type     = type
        self._location = location

    @property
    def name(self):
        return self._name

    @property
    def time(self):
        return self._time

    @property
    def type(self):
        return self._type

    @property
    def location(self):
        return self._location

    def __repr__(self):
        return f"Meeting(_id={self.id}, name={self._name}, time={self._time}, type={self._type})"

    # CRUD create
    def create(self):
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except IntegrityError:
            db.session.rollback()
            return None

    # CRUD read
    def read(self):
        # Aggregate tag counts for this meeting
        tag_counts = {}
        for t in self.tags:
            tag_counts[t.tag_name] = tag_counts.get(t.tag_name, 0) + 1

        return {
            "id":       self.id,
            "name":     self._name,
            "time":     self._time,
            "type":     self._type,
            "location": self._location,
            "tags":     tag_counts
        }

    # CRUD delete
    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return None


# ══════════════════════════════════════════
#  MEETING TAG MODEL
# ══════════════════════════════════════════

class MeetingTag(db.Model):
    """
    MeetingTag Model

    Each row represents one tag submission by one user for one meeting.
    The recommender aggregates these by meeting_id + tag_name to build tag vectors.

    Attributes:
        id (Column): The primary key.
        meeting_id (Column): Foreign key referencing the meetings table.
        user_id (Column): Foreign key referencing the users table.
        tag_name (Column): A string representing the tag (e.g. '#Meditation'). Cannot be null.
        created_at (Column): Timestamp of when the tag was submitted.
    """
    __tablename__ = 'meeting_tags'

    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'),  nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('nmr_users.id'), nullable=False)
    tag_name   = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=current_timestamp)

    def __init__(self, meeting_id, user_id, tag_name):
        self.meeting_id = meeting_id
        self.user_id    = user_id
        self.tag_name   = tag_name

    def __repr__(self):
        return f"MeetingTag(meeting_id={self.meeting_id}, user_id={self.user_id}, tag={self.tag_name})"

    # CRUD create
    def create(self):
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except IntegrityError:
            db.session.rollback()
            return None

    # CRUD read
    def read(self):
        return {
            "id":         self.id,
            "meeting_id": self.meeting_id,
            "user_id":    self.user_id,
            "tag_name":   self.tag_name,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    # CRUD delete
    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return None


# ══════════════════════════════════════════
#  MEETING FEEDBACK MODEL
# ══════════════════════════════════════════

class MeetingFeedback(db.Model):
    """
    MeetingFeedback Model

    Stores a single post-meeting survey response from one user for one meeting.

    Attributes:
        id (Column): The primary key.
        meeting_id (Column): Foreign key referencing the meetings table.
        user_id (Column): Foreign key referencing the users table.
        energy_rating (Column): An integer 1–5 representing the meeting's energy level.
        beginner_friendly (Column): A string: 'Yes', 'Somewhat', or 'No'.
        description (Column): Optional free-text description from Q3.
        created_at (Column): Timestamp of when the feedback was submitted.
    """
    __tablename__ = 'meeting_feedback'

    id                = db.Column(db.Integer, primary_key=True)
    meeting_id        = db.Column(db.Integer, db.ForeignKey('meetings.id'),  nullable=False)
    user_id           = db.Column(db.Integer, db.ForeignKey('nmr_users.id'), nullable=False)
    energy_rating     = db.Column(db.Integer, nullable=False)        # 1–5
    beginner_friendly = db.Column(db.String(20), nullable=False)     # Yes | Somewhat | No
    description       = db.Column(db.Text, nullable=True)
    created_at        = db.Column(db.DateTime, default=current_timestamp)

    def __init__(self, meeting_id, user_id, energy_rating, beginner_friendly, description=''):
        self.meeting_id        = meeting_id
        self.user_id           = user_id
        self.energy_rating     = energy_rating
        self.beginner_friendly = beginner_friendly
        self.description       = description

    def __repr__(self):
        return f"MeetingFeedback(meeting_id={self.meeting_id}, user_id={self.user_id}, energy={self.energy_rating})"

    # CRUD create
    def create(self):
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except IntegrityError:
            db.session.rollback()
            return None

    # CRUD read
    def read(self):
        return {
            "id":                self.id,
            "meeting_id":        self.meeting_id,
            "user_id":           self.user_id,
            "energy_rating":     self.energy_rating,
            "beginner_friendly": self.beginner_friendly,
            "description":       self.description,
            "created_at":        self.created_at.isoformat() if self.created_at else None
        }

    # CRUD delete
    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return None


# ══════════════════════════════════════════
#  NMR USER MODEL
# ══════════════════════════════════════════

class NMRUser(db.Model, UserMixin):
    """
    NMRUser Model

    Manages user accounts for the Neural Meeting Recommender feature.
    Stores login credentials and saved tag preferences for KNN input.

    Attributes:
        id (Column): The primary key.
        _username (Column): A unique string identifier for the user. Cannot be null.
        _password (Column): A hashed password string. Cannot be null.
        _preferences (Column): A JSON list of the user's saved preference tags (e.g. ['#Meditation', '#SmallGroup']).
        joined_at (Column): Timestamp of account creation.
    """
    __tablename__ = 'nmr_users'

    id           = db.Column(db.Integer, primary_key=True)
    _username    = db.Column(db.String(255), unique=True, nullable=False)
    _password    = db.Column(db.String(255), unique=False, nullable=False)
    _preferences = db.Column(db.JSON, nullable=True, default=list)
    joined_at    = db.Column(db.DateTime, default=current_timestamp)

    # One-to-many: one user can submit many tags and feedback entries
    tags     = db.relationship('MeetingTag',      backref='user', cascade='all, delete-orphan', lazy=True)
    feedback = db.relationship('MeetingFeedback', backref='user', cascade='all, delete-orphan', lazy=True)

    def __init__(self, username, password):
        self._username    = username
        self._preferences = []
        self.set_password(password)

    # Flask-Login requirements
    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    # Username getter/setter
    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, username):
        self._username = username

    # Password methods
    @property
    def password(self):
        return self._password[0:10] + "..."

    def set_password(self, password):
        """Hash and store password."""
        if password and password.startswith("pbkdf2:sha256:"):
            self._password = password
        else:
            self._password = generate_password_hash(password, "pbkdf2:sha256", salt_length=10)

    def is_password(self, password):
        """Check a plaintext password against the stored hash."""
        return check_password_hash(self._password, password)

    # Preferences getter/setter
    @property
    def preferences(self):
        return self._preferences if self._preferences else []

    @preferences.setter
    def preferences(self, tags):
        """Set user preference tags. Expects a list of tag strings."""
        self._preferences = tags if tags is not None else []

    def __str__(self):
        return json.dumps(self.read())

    def __repr__(self):
        return f"NMRUser(_id={self.id}, username={self._username})"

    # CRUD create
    def create(self):
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except IntegrityError:
            db.session.rollback()
            return None

    # CRUD read
    def read(self):
        return {
            "id":          self.id,
            "username":    self._username,
            "preferences": self.preferences,
            "joined_at":   self.joined_at.isoformat() if self.joined_at else None
        }

    # CRUD update
    def update(self, inputs):
        if not isinstance(inputs, dict):
            return self
        username    = inputs.get("username", "")
        password    = inputs.get("password", "")
        preferences = inputs.get("preferences", None)
        if username:
            self._username = username
        if password:
            self.set_password(password)
        if preferences is not None:
            self.preferences = preferences
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None
        return self

    # CRUD delete
    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        return None

    def read_history(self):
        """Returns combined tag + feedback history for this user, newest first."""
        tag_history = [t.read() for t in self.tags]
        fb_history  = [f.read() for f in self.feedback]
        history = tag_history + fb_history
        history.sort(key=lambda x: x["created_at"] or "", reverse=True)
        return history


# ══════════════════════════════════════════
#  KNN RECOMMENDER LOGIC
# ══════════════════════════════════════════

ALL_TAGS = [
    "#Meditation", "#HighEnergy", "#BeginnerFriendly", "#YoungAdults",
    "#Speaker", "#SmallGroup", "#LargeGroup", "#Spiritual", "#BookStudy",
    "#WomenOnly", "#MenOnly", "#LGBTQ+", "#Newcomers", "#DualRecovery",
    "#Candlelight", "#Discussion", "#StepWork", "#Outdoor", "#NA", "#AA"
]

def build_meeting_vector(tag_counts: dict) -> dict:
    """
    Convert raw tag counts for one meeting into a normalised frequency vector.
    e.g. { "#Meditation": 3, "#Spiritual": 1 } → { "#Meditation": 0.75, "#Spiritual": 0.25, ... }
    All tags not present are set to 0.
    """
    total = sum(tag_counts.values()) or 1
    return {tag: tag_counts.get(tag, 0) / total for tag in ALL_TAGS}


def build_user_vector(selected_tags: list) -> dict:
    """
    Convert the user's selected preference tags into a binary vector.
    e.g. ["#Meditation", "#SmallGroup"] → { "#Meditation": 1, "#SmallGroup": 1, ... rest 0 }
    """
    return {tag: (1 if tag in selected_tags else 0) for tag in ALL_TAGS}


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """
    Cosine similarity between two tag vectors.
    Returns a float between 0.0 (no overlap) and 1.0 (identical).
    """
    dot    = sum(vec_a[t] * vec_b[t] for t in ALL_TAGS)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def run_knn(selected_tags: list) -> list:
    """
    Main KNN entry point called by the API route.

    Parameters
    ----------
    selected_tags : list of str
        Tags the user selected as preferences, e.g. ["#Meditation", "#SmallGroup"]

    Returns
    -------
    List of dicts sorted by compatibility_score descending.
    Each dict contains full meeting info + score fields.
    """
    meetings = Meeting.query.all()
    user_vec = build_user_vector(selected_tags)
    no_prefs = len(selected_tags) == 0

    results = []
    for m in meetings:
        # Aggregate tag counts for this meeting
        raw_counts = {}
        for t in m.tags:
            raw_counts[t.tag_name] = raw_counts.get(t.tag_name, 0) + 1

        meet_vec = build_meeting_vector(raw_counts)
        score    = 0.0 if no_prefs else cosine_similarity(user_vec, meet_vec)

        # Top 4 tags by count for display
        top_tags = [
            tag for tag, _ in
            sorted(raw_counts.items(), key=lambda x: x[1], reverse=True)[:4]
        ]

        results.append({
            **m.read(),
            "compatibility_score": round(score * 100),
            "top_tags":   top_tags,
            "score_tier": "high" if score >= 0.6 else "med" if score >= 0.3 else "low"
        })

    results.sort(key=lambda x: x["compatibility_score"], reverse=True)
    return results


# ══════════════════════════════════════════
#  DATABASE INITIALISATION
# ══════════════════════════════════════════

def initMeetings():
    """
    Creates all tables and seeds the PRC meeting list and a test user.
    Safe to call multiple times — skips existing records.
    """
    with app.app_context():
        db.create_all()

        # Seed PRC meeting list
        meetings_seed = [
            Meeting("Monday Morning Serenity",  "Mon 7:00 AM",  "AA",    "Room A"),
            Meeting("Steps to Freedom",          "Mon 6:30 PM",  "NA",    "Main Hall"),
            Meeting("Tuesday Speaker Series",    "Tue 7:00 PM",  "AA",    "Chapel"),
            Meeting("Women's Wisdom Circle",     "Wed 10:00 AM", "AA",    "Room B"),
            Meeting("Young People's Meeting",    "Wed 7:00 PM",  "AA",    "Main Hall"),
            Meeting("Big Book Deep Dive",        "Thu 6:00 PM",  "AA",    "Library"),
            Meeting("Thursday Night NA",         "Thu 8:00 PM",  "NA",    "Room C"),
            Meeting("Meditation & Mindfulness",  "Fri 7:00 AM",  "Other", "Garden"),
            Meeting("Friday Night Speaker",      "Fri 7:30 PM",  "AA",    "Main Hall"),
            Meeting("Weekend Warriors",          "Sat 10:00 AM", "NA",    "Room A"),
            Meeting("Saturday Spiritual Hour",   "Sat 6:00 PM",  "Other", "Chapel"),
            Meeting("Sunday Newcomers Welcome",  "Sun 9:00 AM",  "AA",    "Room B"),
            Meeting("Steps 1-3 Workshop",        "Sun 3:00 PM",  "AA",    "Library"),
            Meeting("LGBTQ+ Safe Space",         "Mon 8:00 PM",  "AA",    "Room D"),
            Meeting("Men's Group Discussion",    "Tue 6:00 PM",  "AA",    "Room A"),
            Meeting("Dual Recovery Meeting",     "Wed 6:30 PM",  "Other", "Room C"),
        ]

        for meeting in meetings_seed:
            try:
                meeting.create()
            except IntegrityError:
                db.session.remove()
                print(f"Records exist or error: {meeting.name}")

        # Seed a test user
        test_user = NMRUser(username="testuser", password="test1234")
        try:
            test_user.create()
        except IntegrityError:
            db.session.remove()
            print("Test user already exists.")