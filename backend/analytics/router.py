from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.analytics.engine import AnalyticsEngine, parse_time
from backend.analytics.repository import AnalyticsRepository
from backend.analytics.schemas import SegmentRequest
from backend.auth.dependencies import (
    AuthContext,
    require_analyst,
    require_csrf,
    require_viewer,
)
from backend.responses import success_response


router = APIRouter(prefix="/api/analytics", tags=["analytics"])
engine = AnalyticsEngine()
DEFAULT_FUNNEL = ["view_product", "add_to_cart", "begin_checkout", "purchase"]


def repository(request: Request) -> AnalyticsRepository:
    return AnalyticsRepository(request.app.state.database_path)


def period(
    repo: AnalyticsRepository,
    workspace_id: int,
    days: int,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime, datetime]:
    if (date_from is None) != (date_to is None):
        raise HTTPException(400, "date_from and date_to must be provided together")
    if date_from and date_to:
        if date_from > date_to:
            raise HTTPException(400, "date_from must not be after date_to")
        if (date_to - date_from).days > 365:
            raise HTTPException(400, "Date range is too large")
        return (
            datetime.combine(date_from, time.min, tzinfo=timezone.utc),
            datetime.combine(date_to, time.max, tzinfo=timezone.utc),
        )
    latest_text = repo.latest_event_at(workspace_id)
    latest = parse_time(latest_text) if latest_text else datetime.now(timezone.utc)
    return latest - timedelta(days=days - 1), latest


def event_window(
    repo: AnalyticsRepository, workspace_id: int, start: datetime, end: datetime
) -> list[dict]:
    return repo.events(workspace_id, start.isoformat(), end.isoformat())


@router.get("/revenue")
def revenue(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    context: AuthContext = Depends(require_viewer),
):
    repo = repository(request)
    start, end = period(repo, context.workspace_id, days, date_from, date_to)
    duration = end - start
    previous_end = start - timedelta(microseconds=1)
    previous_start = previous_end - duration
    result = engine.revenue(
        event_window(repo, context.workspace_id, start, end),
        event_window(repo, context.workspace_id, previous_start, previous_end),
    )
    result["period"] = {"from": start.date().isoformat(), "to": end.date().isoformat()}
    result["daily"] = [
        {**point, "label": point["date"], "orders": point["purchases"]}
        for point in result["daily"]
    ]
    result["by_region"] = [
        {"label": item["value"], "name": item["value"], **item}
        for item in result["dimensions"]["region"]
    ]
    result["by_category"] = [
        {"label": item["value"], "name": item["value"], **item}
        for item in result["dimensions"]["product"]
    ]
    return success_response(result, legacy={"status": "success", **result})


@router.get("/funnel")
def funnel(
    request: Request,
    steps: str = Query(default=",".join(DEFAULT_FUNNEL), max_length=300),
    days: int = Query(default=30, ge=1, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    context: AuthContext = Depends(require_viewer),
):
    step_names = [item.strip() for item in steps.split(",") if item.strip()]
    if not 2 <= len(step_names) <= 10 or len(set(step_names)) != len(step_names):
        raise HTTPException(400, "Provide 2 to 10 distinct ordered funnel steps")
    repo = repository(request)
    start, end = period(repo, context.workspace_id, days, date_from, date_to)
    result = engine.funnel(
        event_window(repo, context.workspace_id, start, end), step_names
    )
    result["completion_rate"] = result["conversion_rate"]
    result["steps"] = [
        {**item, "users": item["completed"], "rate": item["conversion_rate"]}
        for item in result["steps"]
    ]
    return success_response(result, legacy={"status": "success", **result})


@router.get("/retention")
def retention(request: Request, context: AuthContext = Depends(require_viewer)):
    result = engine.retention(repository(request).all_events(context.workspace_id))
    return success_response(result, legacy={"status": "success", **result})


@router.get("/cohort")
def cohort(request: Request, context: AuthContext = Depends(require_viewer)):
    result = engine.cohort(repository(request).all_events(context.workspace_id))
    return success_response(result, legacy={"status": "success", **result})


@router.post("/segments/preview")
def preview_segment(
    payload: SegmentRequest,
    request: Request,
    context: AuthContext = Depends(require_analyst),
    _csrf: None = Depends(require_csrf),
):
    rules = [rule.model_dump() for rule in payload.rules]
    result = engine.segment(
        repository(request).all_events(context.workspace_id), payload.match_type, rules
    )
    return success_response(
        {**result, "match_type": payload.match_type, "rules": rules}
    )


@router.post("/segments", status_code=201)
def create_segment(
    payload: SegmentRequest,
    request: Request,
    context: AuthContext = Depends(require_analyst),
    _csrf: None = Depends(require_csrf),
):
    if not payload.name:
        raise HTTPException(400, "name is required when saving a segment")
    repo = repository(request)
    rules = [rule.model_dump() for rule in payload.rules]
    row = repo.create_segment(
        context.workspace_id, context.user_id, payload.name, payload.match_type, rules
    )
    row["preview"] = engine.segment(
        repo.all_events(context.workspace_id), payload.match_type, rules
    )
    return success_response(row)


@router.get("/segments")
def list_segments(request: Request, context: AuthContext = Depends(require_viewer)):
    repo = repository(request)
    items = repo.list_segments(context.workspace_id)
    events = repo.all_events(context.workspace_id)
    for item in items:
        item["metrics"] = engine.segment(events, item["match_type"], item["rules"])
    return success_response(items)


@router.get("/anomalies")
def anomalies(request: Request, context: AuthContext = Depends(require_viewer)):
    result = engine.anomalies(repository(request).all_events(context.workspace_id))
    return success_response(result, legacy={"status": "success", **result})


@router.get("/forecast")
def forecast(
    request: Request,
    horizon: int = Query(default=7, ge=1, le=30),
    context: AuthContext = Depends(require_viewer),
):
    result = engine.forecast(
        repository(request).all_events(context.workspace_id), horizon
    )
    return success_response(
        result, legacy={"status": result["status"].lower(), **result}
    )


@router.get("/insights/explanations")
def deterministic_insights(
    request: Request, context: AuthContext = Depends(require_viewer)
):
    events = repository(request).all_events(context.workspace_id)
    anomalies_result = engine.anomalies(events)
    forecast_result = engine.forecast(events)
    explanations = []
    for item in anomalies_result["anomalies"][-5:]:
        direction = "above" if item["observed"] > item["expected"] else "below"
        explanations.append(
            {
                "type": "ANOMALY_EXPLANATION",
                "severity": item["severity"],
                "text": f"Daily revenue on {item['date']} was {direction} the deterministic expected range.",
                "evidence": item,
            }
        )
    return success_response(
        {
            "generation_mode": "DETERMINISTIC_TEMPLATE",
            "numeric_source_of_truth": "analytics engine",
            "external_ai_enabled": False,
            "forecast_status": forecast_result["status"],
            "items": explanations,
        }
    )
