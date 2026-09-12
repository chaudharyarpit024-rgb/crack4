import re
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Set
import zoneinfo

from database.mongodb import db

logger = logging.getLogger(__name__)

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _resolve_reference_date(client_date: Optional[str] = None, client_tz: Optional[str] = None) -> date:
    """
    Determine the 'today' reference date based on client input or server UTC.
    Priority:
    1. Valid client_date (YYYY-MM-DD)
    2. Valid client_tz (e.g., 'Asia/Kolkata', 'America/New_York')
    3. Server UTC date
    """
    if client_date and DATE_REGEX.match(client_date):
        try:
            return date.fromisoformat(client_date)
        except ValueError:
            pass

    if client_tz:
        try:
            tz = zoneinfo.ZoneInfo(client_tz)
            return datetime.now(tz).date()
        except Exception:
            pass

    return datetime.now(timezone.utc).date()


def _parse_timestamp_to_date_str(ts: str, tz: Optional[zoneinfo.ZoneInfo] = None) -> Optional[str]:
    """Parse an ISO timestamp string into a YYYY-MM-DD date string, optionally converted to timezone."""
    if not ts:
        return None
    try:
        # Fast path if no timezone conversion needed and ts starts with YYYY-MM-DD
        if tz is None:
            prefix = ts[:10]
            if DATE_REGEX.match(prefix):
                return prefix

        # Parse ISO datetime
        clean_ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if tz:
            dt = dt.astimezone(tz)
        return dt.date().isoformat()
    except Exception:
        # Fallback to prefix if standard ISO
        if len(ts) >= 10 and DATE_REGEX.match(ts[:10]):
            return ts[:10]
        return None


def calculate_longest_streak_from_dates(logged_dates: Set[str]) -> int:
    """Calculate the longest consecutive day streak from a set of unique 'YYYY-MM-DD' dates."""
    if not logged_dates:
        return 0

    sorted_dates = []
    for d_str in logged_dates:
        try:
            sorted_dates.append(date.fromisoformat(d_str))
        except ValueError:
            continue

    sorted_dates.sort()
    if not sorted_dates:
        return 0

    max_streak = 1
    current_run = 1
    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i - 1]).days
        if diff == 1:
            current_run += 1
            if current_run > max_streak:
                max_streak = current_run
        elif diff > 1:
            current_run = 1

    return max_streak


async def compute_user_streak(
    user_id: str,
    client_date: Optional[str] = None,
    client_tz: Optional[str] = None,
) -> dict:
    """
    Calculate streak details dynamically from the user's food logs.
    Self-healing: automatically reflects added, edited, or deleted logs.
    """
    target_tz: Optional[zoneinfo.ZoneInfo] = None
    if client_tz:
        try:
            target_tz = zoneinfo.ZoneInfo(client_tz)
        except Exception:
            target_tz = None

    ref_date = _resolve_reference_date(client_date, client_tz)
    today_str = ref_date.isoformat()
    yesterday_date = ref_date - timedelta(days=1)
    yesterday_str = yesterday_date.isoformat()

    # Fetch all food log timestamps for this user
    cursor = db.food_logs.find({"user_id": user_id}, {"timestamp": 1, "_id": 0})
    logs = await cursor.to_list(10000)

    logged_dates: Set[str] = set()
    for log in logs:
        ts = log.get("timestamp")
        if ts:
            d_str = _parse_timestamp_to_date_str(ts, target_tz)
            if d_str:
                logged_dates.add(d_str)

    logged_today = today_str in logged_dates
    logged_yesterday = yesterday_str in logged_dates

    # Determine current streak count
    current_streak = 0
    if logged_today:
        check_date = ref_date
        while check_date.isoformat() in logged_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
        streak_active = True
    elif logged_yesterday:
        # Streak is still alive for today until midnight!
        check_date = yesterday_date
        while check_date.isoformat() in logged_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
        streak_active = True
    else:
        current_streak = 0
        streak_active = False

    # Calculate longest streak across history
    historical_longest = calculate_longest_streak_from_dates(logged_dates)

    # Sync with stored longest streak in db.users (ensures all-time records are never lost)
    user_doc = await db.users.find_one({"id": user_id}, {"longest_streak": 1})
    stored_longest = (user_doc or {}).get("longest_streak", 0) if user_doc else 0
    longest_streak = max(historical_longest, stored_longest, current_streak)

    if longest_streak > stored_longest:
        try:
            await db.users.update_one(
                {"id": user_id},
                {"$set": {"longest_streak": longest_streak}},
            )
        except Exception as e:
            logger.warning("Failed to update longest_streak for user %s: %s", user_id, e)

    # Build 7-day rolling weekly activity window ending on ref_date
    day_letters = ["M", "T", "W", "T", "F", "S", "S"]
    weekly_activity = []
    for offset in range(6, -1, -1):
        d = ref_date - timedelta(days=offset)
        d_str = d.isoformat()
        weekly_activity.append({
            "date": d_str,
            "day_name": day_letters[d.weekday()],
            "day_abbr": d.strftime("%a"),
            "logged": d_str in logged_dates,
            "is_today": (d == ref_date),
        })

    # User-friendly motivational messages
    if current_streak == 0:
        message = "Log a meal today to start your streak!"
    elif logged_today and current_streak == 1:
        message = "Day 1 complete! Come back tomorrow to keep it going 🔥"
    elif logged_today:
        message = f"You're on a {current_streak}-day streak! Keep up the momentum 🔥"
    else:
        message = f"Keep your {current_streak}-day streak alive! Log a meal today ⚡"

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "logged_today": logged_today,
        "streak_active": streak_active,
        "today_date": today_str,
        "weekly_activity": weekly_activity,
        "message": message,
    }
