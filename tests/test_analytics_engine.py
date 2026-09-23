import unittest
from datetime import date, timedelta

from backend.analytics.engine import AnalyticsEngine


def event(
    event_id,
    name,
    day,
    *,
    user=None,
    session=None,
    revenue=0,
    source="web",
    device="mobile",
    region="VN",
    product="Pro",
):
    return {
        "event_id": event_id,
        "event_name": name,
        "occurred_at": f"{day}T10:00:00+00:00",
        "user_id": user,
        "session_id": session,
        "revenue": revenue,
        "source": source,
        "device": device,
        "region": region,
        "product": product,
    }


class AnalyticsEngineKnownDatasetTests(unittest.TestCase):
    def setUp(self):
        self.engine = AnalyticsEngine()

    def test_revenue_metrics_and_previous_comparison_are_exact(self):
        current = [
            event("1", "view_product", "2026-01-02", user="u1", session="s1"),
            event("2", "purchase", "2026-01-02", user="u1", session="s1", revenue=100),
            event("3", "purchase", "2026-01-03", user="u2", session="s2", revenue=50),
            event("4", "view_product", "2026-01-03", user="u3", session="s3"),
        ]
        previous = [
            event("p", "purchase", "2025-12-30", user="u1", session="old", revenue=100)
        ]
        result = self.engine.revenue(current, previous)
        self.assertEqual(
            {
                "revenue": 150.0,
                "purchases": 2,
                "active_users": 3,
                "sessions": 3,
                "aov": 75.0,
                "arpu": 50.0,
                "conversion_rate": 66.67,
            },
            result["metrics"],
        )
        self.assertEqual(50.0, result["change_percent"]["revenue"])
        self.assertEqual(150.0, result["dimensions"]["source"][0]["revenue"])

    def test_ordered_funnel_rejects_out_of_order_completion(self):
        steps = ["view_product", "add_to_cart", "begin_checkout", "purchase"]
        events = [
            event("1", "view_product", "2026-01-01", session="s1"),
            {
                **event("2", "add_to_cart", "2026-01-01", session="s1"),
                "occurred_at": "2026-01-01T10:01:00Z",
            },
            {
                **event("3", "begin_checkout", "2026-01-01", session="s1"),
                "occurred_at": "2026-01-01T10:02:00Z",
            },
            {
                **event("4", "purchase", "2026-01-01", session="s1"),
                "occurred_at": "2026-01-01T10:04:00Z",
            },
            event("5", "view_product", "2026-01-01", session="s2"),
            {
                **event("6", "purchase", "2026-01-01", session="s2"),
                "occurred_at": "2026-01-01T10:01:00Z",
            },
        ]
        result = self.engine.funnel(events, steps)
        self.assertEqual(2, result["entered"])
        self.assertEqual(1, result["completed"])
        self.assertEqual(50.0, result["conversion_rate"])
        self.assertEqual(120.0, result["steps"][3]["average_seconds_from_previous"])

    def test_retention_and_cohort_use_exact_calendar_boundaries(self):
        events = [
            event("s1", "signup", "2026-01-05", user="u1"),
            event("a1", "view_product", "2026-01-06", user="u1"),
            event("a7", "view_product", "2026-01-12", user="u1"),
            event("s2", "signup", "2026-01-06", user="u2"),
            event("a2", "view_product", "2026-01-07", user="u2"),
        ]
        retention = self.engine.retention(events)
        self.assertEqual(100.0, retention["periods"][0]["retention_rate"])
        self.assertEqual(100.0, retention["periods"][1]["retention_rate"])
        self.assertEqual(1, retention["periods"][1]["eligible_users"])
        cohort = self.engine.cohort(events)
        self.assertEqual("2026-01-05", cohort["cohorts"][0]["cohort"])
        self.assertEqual([100.0, 50.0], cohort["cohorts"][0]["retention"][:2])

    def test_segment_rules_are_composable(self):
        events = [
            event("1", "purchase", "2026-01-01", user="u1", revenue=120, region="VN"),
            event("2", "purchase", "2026-01-01", user="u2", revenue=20, region="US"),
        ]
        result = self.engine.segment(
            events,
            "ALL",
            [
                {"field": "event_name", "operator": "eq", "value": "purchase"},
                {"field": "revenue", "operator": "gte", "value": 100},
            ],
        )
        self.assertEqual(
            {"event_count": 1, "user_count": 1, "session_count": 0}, result
        )

    def test_anomaly_expected_range_is_manual_seven_day_baseline(self):
        start = date(2026, 1, 1)
        events = [
            event(
                str(i), "purchase", (start + timedelta(days=i)).isoformat(), revenue=100
            )
            for i in range(7)
        ]
        events.append(event("spike", "purchase", "2026-01-08", revenue=300))
        result = self.engine.anomalies(events)
        self.assertEqual(1, len(result["anomalies"]))
        self.assertEqual(
            {"lower": 100.0, "upper": 100.0}, result["anomalies"][0]["expected_range"]
        )
        self.assertEqual(300.0, result["anomalies"][0]["observed"])

    def test_forecast_is_reproducible_and_holdout_is_reported(self):
        start = date(2026, 1, 1)
        events = [
            event(
                str(i),
                "purchase",
                (start + timedelta(days=i)).isoformat(),
                revenue=10 * (i + 1),
            )
            for i in range(10)
        ]
        first = self.engine.forecast(events, 2)
        second = self.engine.forecast(events, 2)
        self.assertEqual(first, second)
        self.assertEqual("READY", first["status"])
        self.assertEqual(110.0, first["forecast"][0]["value"])
        self.assertEqual(0.0, first["holdout"]["mae"])


if __name__ == "__main__":
    unittest.main()
