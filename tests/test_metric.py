from datetime import date

from edu_subnet.metric import analytics_query, live_minutes


def test_the_query_asks_for_live_and_on_demand_minutes_of_one_video():
    query = analytics_query("UCchannel", "video1", date(2026, 10, 14), date(2026, 10, 15))
    assert query == {"ids": "channel==UCchannel", "startDate": "2026-10-14", "endDate": "2026-10-15",
                     "dimensions": "liveOrOnDemand", "filters": "video==video1",
                     "metrics": "estimatedMinutesWatched"}


def test_only_the_live_row_counts():
    response = {"columnHeaders": [{"name": "liveOrOnDemand"}, {"name": "estimatedMinutesWatched"}],
                "rows": [["ON_DEMAND", 900], ["LIVE", 120]]}
    assert live_minutes(response) == 120


def test_column_order_does_not_matter():
    response = {"columnHeaders": [{"name": "estimatedMinutesWatched"}, {"name": "liveOrOnDemand"}],
                "rows": [[120, "LIVE"]]}
    assert live_minutes(response) == 120


def test_no_live_row_is_unavailable_not_zero():
    headers = [{"name": "liveOrOnDemand"}, {"name": "estimatedMinutesWatched"}]
    assert live_minutes({"columnHeaders": headers, "rows": [["ON_DEMAND", 900]]}) is None
    assert live_minutes({"columnHeaders": headers}) is None
    assert live_minutes({"columnHeaders": headers, "rows": [["LIVE", 0]]}) == 0
