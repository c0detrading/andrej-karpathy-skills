"""Pipeline stages, platforms and the thresholds behind each concern in the daily report."""

GRAPH_URL = "https://graph.facebook.com/v26.0"

# Stage key -> label, in board order. "active" are current clients; "lost" is hidden unless asked for.
STAGES = {
    "lead": "Lead",
    "contacted": "Contacted",
    "proposal": "Proposal sent",
    "negotiation": "Negotiation",
    "active": "Current client",
    "lost": "Lost",
}

# "auto": fetched daily from Meta. "manual": typed in or imported from a CSV.
PLATFORMS = {"instagram": "auto", "facebook": "auto", "tiktok": "manual"}
PLATFORM_NAMES = {"instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok"}

RECENT_POSTS = 12                       # posts averaged for likes/comments (posts under a day old are skipped)
HISTORY_DAYS = 40                       # snapshots loaded per account (30-day changes and averages)
STALE_DAYS = {"auto": 2, "manual": 8}   # numbers older than this many days are flagged
FOLLOWER_DROP_PCT = (1.0, 3.0)          # followers lost over 7 days, %: medium, high
FOLLOWER_DROP_MIN = 10                  # ...and at least this many, so small accounts don't flag on noise
QUIET_DAYS = (7, 14)                    # days since the last post: medium, high
ENGAGEMENT_DROP_PCT = (30, 50)          # engagement rate below its 30-day average, %: medium, high
ENGAGEMENT_MIN_HISTORY = 7              # days of history needed before judging engagement
