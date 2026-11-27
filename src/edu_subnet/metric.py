"""The measured quantity: YouTube's LIVE estimatedMinutesWatched for one lecture (spec §8.1, §9.4).

The platform fetches it with `analytics_query` and validators repeat exactly the same
query to check the platform's numbers.
"""
from datetime import date

ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
DIMENSION = "liveOrOnDemand"
METRIC = "estimatedMinutesWatched"


def analytics_query(channel_id: str, video_id: str, start_date: date, end_date: date) -> dict:
    """The YouTube Analytics request for one lecture. Dates are Pacific-time reporting days."""
    return {"ids": f"channel=={channel_id}", "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(), "dimensions": DIMENSION,
            "filters": f"video=={video_id}", "metrics": METRIC}


def live_minutes(response: dict) -> int | None:
    """The LIVE row's watch-minutes. Replays (ON_DEMAND) never count. None if there is no LIVE row."""
    headers = [column["name"] for column in response.get("columnHeaders", [])]
    for row in response.get("rows") or []:
        record = dict(zip(headers, row))
        if record.get(DIMENSION) == "LIVE":
            return int(record[METRIC])
    return None
