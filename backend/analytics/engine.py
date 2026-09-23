from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import sqrt
from statistics import fmean, pstdev
from typing import Iterable


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def percent(numerator: float, denominator: float) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def change(current: float, previous: float) -> float | None:
    if previous == 0:
        return 0.0 if current == 0 else None
    return round((current - previous) / previous * 100, 2)


class AnalyticsEngine:
    """Pure deterministic calculations; persistence and authorization live outside."""

    def revenue(self, current: list[dict], previous: list[dict]) -> dict:
        def calculate(events: list[dict]) -> dict:
            purchases = [event for event in events if event["event_name"] == "purchase"]
            revenue = round(
                sum(float(event.get("revenue") or 0) for event in purchases), 2
            )
            users = {event["user_id"] for event in events if event.get("user_id")}
            sessions = {
                event["session_id"] for event in events if event.get("session_id")
            }
            converted = {
                event["session_id"] for event in purchases if event.get("session_id")
            }
            return {
                "revenue": revenue,
                "purchases": len(purchases),
                "active_users": len(users),
                "sessions": len(sessions),
                "aov": round(revenue / len(purchases), 2) if purchases else 0.0,
                "arpu": round(revenue / len(users), 2) if users else 0.0,
                "conversion_rate": percent(len(converted), len(sessions)),
            }

        current_metrics, previous_metrics = calculate(current), calculate(previous)
        comparisons = {
            key: change(float(current_metrics[key]), float(previous_metrics[key]))
            for key in current_metrics
        }
        dimensions = {}
        for dimension in ("source", "device", "region", "product"):
            grouped: dict[str, dict[str, float | int]] = defaultdict(
                lambda: {"revenue": 0.0, "purchases": 0}
            )
            for event in current:
                if event["event_name"] != "purchase":
                    continue
                key = str(event.get(dimension) or "Unknown")
                grouped[key]["revenue"] = round(
                    float(grouped[key]["revenue"]) + float(event.get("revenue") or 0), 2
                )
                grouped[key]["purchases"] = int(grouped[key]["purchases"]) + 1
            dimensions[dimension] = [
                {"value": key, **values}
                for key, values in sorted(
                    grouped.items(),
                    key=lambda item: (-float(item[1]["revenue"]), item[0]),
                )
            ]
        daily: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"revenue": 0.0, "purchases": 0}
        )
        for event in current:
            if event["event_name"] == "purchase":
                day = parse_time(event["occurred_at"]).date().isoformat()
                daily[day]["revenue"] = round(
                    float(daily[day]["revenue"]) + float(event.get("revenue") or 0), 2
                )
                daily[day]["purchases"] = int(daily[day]["purchases"]) + 1
        return {
            "metrics": current_metrics,
            "previous_metrics": previous_metrics,
            "change_percent": comparisons,
            "daily": [{"date": day, **values} for day, values in sorted(daily.items())],
            "dimensions": dimensions,
            "coverage": {
                "session_id_percent": percent(
                    sum(bool(e.get("session_id")) for e in current), len(current)
                ),
                "user_id_percent": percent(
                    sum(bool(e.get("user_id")) for e in current), len(current)
                ),
            },
        }

    def funnel(self, events: list[dict], step_names: list[str]) -> dict:
        sessions: dict[str, list[dict]] = defaultdict(list)
        for event in events:
            if event.get("session_id"):
                sessions[str(event["session_id"])].append(event)
        completed_counts = [0] * len(step_names)
        elapsed: list[list[float]] = [[] for _ in step_names[1:]]
        for session_events in sessions.values():
            ordered = sorted(
                session_events, key=lambda event: parse_time(event["occurred_at"])
            )
            cursor = -1
            timestamps: list[datetime] = []
            for step in step_names:
                match_index = next(
                    (
                        index
                        for index in range(cursor + 1, len(ordered))
                        if ordered[index]["event_name"] == step
                    ),
                    None,
                )
                if match_index is None:
                    break
                cursor = match_index
                timestamps.append(parse_time(ordered[cursor]["occurred_at"]))
            for index in range(len(timestamps)):
                completed_counts[index] += 1
                if index:
                    elapsed[index - 1].append(
                        (timestamps[index] - timestamps[index - 1]).total_seconds()
                    )
        entered = completed_counts[0] if completed_counts else 0
        steps = []
        for index, name in enumerate(step_names):
            count = completed_counts[index]
            previous = completed_counts[index - 1] if index else entered
            steps.append(
                {
                    "name": name,
                    "completed": count,
                    "conversion_rate": percent(count, entered),
                    "step_conversion_rate": percent(count, previous),
                    "drop_off": (previous - count) if index else 0,
                    "average_seconds_from_previous": round(fmean(elapsed[index - 1]), 1)
                    if index and elapsed[index - 1]
                    else None,
                }
            )
        return {
            "entity": "session",
            "entered": entered,
            "completed": completed_counts[-1] if completed_counts else 0,
            "conversion_rate": percent(completed_counts[-1], entered)
            if completed_counts
            else 0.0,
            "steps": steps,
            "coverage": {
                "events": len(events),
                "events_with_session": sum(bool(e.get("session_id")) for e in events),
            },
        }

    def retention(
        self, events: list[dict], days: Iterable[int] = (1, 7, 14, 30)
    ) -> dict:
        signups: dict[str, datetime] = {}
        activity: dict[str, set] = defaultdict(set)
        for event in events:
            user = event.get("user_id")
            if not user:
                continue
            when = parse_time(event["occurred_at"])
            if event["event_name"] == "signup":
                signups[str(user)] = min(signups.get(str(user), when), when)
            else:
                activity[str(user)].add(when.date())
        observed_through = max(
            (parse_time(event["occurred_at"]).date() for event in events), default=None
        )
        result = []
        for day in days:
            eligible = {
                user: signup
                for user, signup in signups.items()
                if observed_through
                and signup.date() + timedelta(days=day) <= observed_through
            }
            retained = sum(
                signup.date() + timedelta(days=day) in activity.get(user, set())
                for user, signup in eligible.items()
            )
            result.append(
                {
                    "day": day,
                    "eligible_users": len(eligible),
                    "retained_users": retained,
                    "retention_rate": percent(retained, len(eligible)),
                }
            )
        return {
            "anchor_event": "signup",
            "retained_event": "any non-signup event on exact UTC calendar day",
            "observed_through": observed_through.isoformat()
            if observed_through
            else None,
            "cohort_users": len(signups),
            "periods": result,
        }

    def cohort(self, events: list[dict], weeks: int = 8) -> dict:
        signups: dict[str, datetime] = {}
        activity: dict[str, set] = defaultdict(set)
        for event in events:
            user = event.get("user_id")
            if not user:
                continue
            when = parse_time(event["occurred_at"])
            if event["event_name"] == "signup":
                signups[str(user)] = min(signups.get(str(user), when), when)
            else:
                activity[str(user)].add(when.date() - timedelta(days=when.weekday()))
        groups: dict = defaultdict(list)
        for user, signup in signups.items():
            anchor = signup.date() - timedelta(days=signup.weekday())
            groups[anchor].append(user)
        observed_through = max(
            (parse_time(event["occurred_at"]).date() for event in events), default=None
        )
        rows = []
        for anchor, users in sorted(groups.items()):
            counts: list[int | None] = []
            rates: list[float | None] = []
            for week in range(weeks):
                if (
                    observed_through
                    and anchor + timedelta(weeks=week) > observed_through
                ):
                    counts.append(None)
                    rates.append(None)
                    continue
                active = sum(
                    anchor + timedelta(weeks=week) in activity.get(user, set())
                    for user in users
                )
                if week == 0:
                    active = len(users)
                counts.append(active)
                rates.append(percent(active, len(users)))
            rows.append(
                {
                    "cohort": anchor.isoformat(),
                    "users": len(users),
                    "retained_users": counts,
                    "retention": rates,
                }
            )
        return {
            "anchor_event": "signup",
            "periods": [f"W{i}" for i in range(weeks)],
            "cohorts": rows,
        }

    def segment(self, events: list[dict], match_type: str, rules: list[dict]) -> dict:
        def matches(event: dict, rule: dict) -> bool:
            actual, expected, operator = (
                event.get(rule["field"]),
                rule["value"],
                rule["operator"],
            )
            if rule["field"] == "revenue":
                actual, expected = float(actual or 0), float(expected)
            if operator == "eq":
                return actual == expected
            if operator == "neq":
                return actual != expected
            if operator == "in":
                return actual in expected
            if operator == "gte":
                return actual >= expected
            if operator == "lte":
                return actual <= expected
            return False

        predicate = all if match_type == "ALL" else any
        selected = [
            event
            for event in events
            if predicate(matches(event, rule) for rule in rules)
        ]
        return {
            "event_count": len(selected),
            "user_count": len({e["user_id"] for e in selected if e.get("user_id")}),
            "session_count": len(
                {e["session_id"] for e in selected if e.get("session_id")}
            ),
        }

    def anomalies(
        self, events: list[dict], window: int = 7, sigma: float = 3.0
    ) -> dict:
        daily: dict[str, float] = defaultdict(float)
        for event in events:
            if event["event_name"] == "purchase":
                daily[parse_time(event["occurred_at"]).date().isoformat()] += float(
                    event.get("revenue") or 0
                )
        points = sorted(daily.items())
        detections = []
        for index in range(window, len(points)):
            history = [value for _, value in points[index - window : index]]
            mean, std = fmean(history), pstdev(history)
            observed = points[index][1]
            lower, upper = max(0.0, mean - sigma * std), mean + sigma * std
            is_anomaly = (
                observed < lower or observed > upper or (std == 0 and observed != mean)
            )
            if is_anomaly:
                deviation = abs(observed - mean) / (std if std else max(abs(mean), 1.0))
                severity = (
                    "high" if deviation >= 5 else "medium" if deviation >= 3 else "low"
                )
                detections.append(
                    {
                        "date": points[index][0],
                        "observed": round(observed, 2),
                        "expected": round(mean, 2),
                        "expected_range": {
                            "lower": round(lower, 2),
                            "upper": round(upper, 2),
                        },
                        "severity": severity,
                        "detection_timestamp": points[index][0] + "T23:59:59Z",
                    }
                )
        return {
            "method": f"rolling_{window}_day_population_mean_{sigma:g}_sigma",
            "metric": "daily_revenue",
            "anomalies": detections,
        }

    def forecast(self, events: list[dict], horizon: int = 7) -> dict:
        daily: dict = defaultdict(float)
        for event in events:
            if event["event_name"] == "purchase":
                daily[parse_time(event["occurred_at"]).date()] += float(
                    event.get("revenue") or 0
                )
        if len(daily) < 8:
            return {
                "status": "INSUFFICIENT_DATA",
                "minimum_days": 8,
                "available_days": len(daily),
                "forecast": [],
            }
        start, end = min(daily), max(daily)
        dates, values = [], []
        cursor = start
        while cursor <= end:
            dates.append(cursor)
            values.append(daily.get(cursor, 0.0))
            cursor += timedelta(days=1)
        holdout = max(2, min(7, len(values) // 5))
        train = values[:-holdout]

        def fit(series: list[float]) -> tuple[float, float]:
            xmean, ymean = (len(series) - 1) / 2, fmean(series)
            denominator = sum((x - xmean) ** 2 for x in range(len(series)))
            slope = (
                sum((x - xmean) * (y - ymean) for x, y in enumerate(series))
                / denominator
                if denominator
                else 0.0
            )
            return slope, ymean - slope * xmean

        hslope, hintercept = fit(train)
        holdout_predictions = [
            max(0.0, hslope * i + hintercept) for i in range(len(train), len(values))
        ]
        residuals = [
            actual - predicted
            for actual, predicted in zip(values[-holdout:], holdout_predictions)
        ]
        mae = fmean(abs(value) for value in residuals)
        rmse = sqrt(fmean(value * value for value in residuals))
        slope, intercept = fit(values)
        residual_std = pstdev(
            [actual - (slope * i + intercept) for i, actual in enumerate(values)]
        )
        output = []
        for step in range(1, horizon + 1):
            estimate = max(0.0, slope * (len(values) + step - 1) + intercept)
            margin = 1.96 * residual_std
            output.append(
                {
                    "date": (dates[-1] + timedelta(days=step)).isoformat(),
                    "value": round(estimate, 2),
                    "lower": round(max(0.0, estimate - margin), 2),
                    "upper": round(estimate + margin, 2),
                }
            )
        return {
            "status": "READY",
            "method": "ordinary_least_squares_daily_baseline",
            "holdout": {"days": holdout, "mae": round(mae, 2), "rmse": round(rmse, 2)},
            "uncertainty": "95% residual interval; baseline, not a probabilistic guarantee",
            "forecast": output,
        }
