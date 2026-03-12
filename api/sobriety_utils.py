SOBRIETY_MILESTONES = [1, 3, 7, 14, 30, 60, 90, 180, 365]

POINT_RULES = {
    "daily_checkin": 10,
    "honest_craving_log": 5,
    "attended_meeting": 10,
    "exercise_done": 5,
    "journal_entry": 5,
    "milestone_bonus_7": 20,
    "milestone_bonus_30": 50,
    "milestone_bonus_90": 100,
    "milestone_bonus_365": 250
}

REWARD_CATALOG = [
    {
        "name": "$5 Coffee Gift Card",
        "points_cost": 100,
        "description": "A small reward for showing up consistently."
    },
    {
        "name": "$10 Bookstore Gift Card",
        "points_cost": 250,
        "description": "Celebrate progress with something meaningful."
    },
    {
        "name": "$15 Smoothie Gift Card",
        "points_cost": 350,
        "description": "A wellness-themed reward for your effort."
    },
    {
        "name": "$25 Wellness Reward",
        "points_cost": 500,
        "description": "A bigger milestone reward for long-term consistency."
    }
]

ENCOURAGEMENT_MESSAGES = {
    "low": [
        "You’re building steady momentum.",
        "Small daily actions are adding up.",
        "Consistency is growth, even when it feels quiet."
    ],
    "medium": [
        "Today may be heavier than usual. Lean into your support system.",
        "Progress is not erased by a hard day.",
        "Pause, breathe, and focus on the next right step."
    ],
    "high": [
        "Today looks especially difficult. Consider reaching out to someone you trust.",
        "You do not have to handle this moment alone.",
        "A meeting, a call, or a grounding routine could help right now."
    ]
}

GARDEN_LEVELS = {
    0: "Empty Pot",
    1: "Sprout",
    2: "Small Plant",
    3: "Blooming Plant",
    4: "Garden Bed",
    5: "Thriving Garden"
}