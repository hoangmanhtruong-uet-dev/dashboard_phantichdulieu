from calendar import monthrange
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.config import settings
from backend.auth.dependencies import (
    AuthContext,
    get_auth_repository,
    require_admin,
    require_analyst,
    require_csrf,
    require_viewer,
)
from backend.auth.router import router as auth_router, workspace_router
from backend.errors import register_error_handlers
from backend.ingestion.parser import IngestionError
from backend.ingestion.router import router as ingestion_router
from backend.query import PageSpec, query_meta
from backend.responses import error_response, success_response
from backend.schemas import (
    AlertCreate,
    ChatRequest,
    CustomerData,
    DataSourceCreate,
    ProfileUpdate,
    ReportCreate,
    SalesData,
)
from data.migrate import run_migrations
from data.auth_repository import AuthRepository
from data.repositories import NexusRepository
from data.seeds import seed_demo_records


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = settings.database_path

app = FastAPI(title="Nexus Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(ingestion_router)


@app.exception_handler(IngestionError)
async def ingestion_error_handler(_request, exc: IngestionError):
    return JSONResponse(
        status_code=exc.status_code, content=error_response(exc.code, exc.message)
    )


def get_repository():
    return NexusRepository(DB_FILE)


def ensure_database():
    """Apply deterministic migrations and optional development seed data."""
    run_migrations(DB_FILE)
    if settings.seed_demo_data:
        seed_demo_records(DB_FILE)


@app.on_event("startup")
def initialize_application():
    app.state.database_path = DB_FILE
    app.state.upload_dir = (
        DB_FILE.parent / "uploads"
        if settings.app_env == "test"
        else settings.upload_dir
    )
    ensure_database()


def parse_date(value: str):
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def add_months(date: datetime, months: int):
    month_index = date.month - 1 + months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date.day, monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


@app.post("/forecast", dependencies=[Depends(require_csrf)])
async def forecast_sales(
    data: List[SalesData], _context: AuthContext = Depends(require_analyst)
):
    try:
        if not data:
            return {"success": True, "status": "empty", "data": [], "forecast": []}

        monthly_totals: dict[str, float] = {}
        for item in data:
            date = parse_date(item.ds)
            if not date:
                continue
            month_key = date.strftime("%Y-%m")
            monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + float(
                item.y or 0
            )

        if not monthly_totals:
            return {"success": True, "status": "empty", "data": [], "forecast": []}

        months = sorted(monthly_totals)
        values = [monthly_totals[month] for month in months]
        count = len(values)

        if count >= 2:
            x_mean = (count - 1) / 2
            y_mean = sum(values) / count
            denominator = sum((index - x_mean) ** 2 for index in range(count)) or 1
            slope = (
                sum(
                    (index - x_mean) * (values[index] - y_mean)
                    for index in range(count)
                )
                / denominator
            )
            intercept = y_mean - slope * x_mean
        else:
            slope = 0.0
            intercept = values[0]

        predicted_history = [slope * index + intercept for index in range(count)]
        residuals = [values[index] - predicted_history[index] for index in range(count)]
        if len(residuals) > 2:
            avg_residual = sum(residuals) / len(residuals)
            spread = (
                sum((r - avg_residual) ** 2 for r in residuals) / len(residuals)
            ) ** 0.5
        else:
            spread = abs(values[-1]) * 0.1

        last_month = datetime.strptime(months[-1] + "-01", "%Y-%m-%d")
        forecast = []
        for step in range(1, 7):
            yhat = max(0.0, float(slope * (count + step - 1) + intercept))
            date = add_months(last_month, step)
            forecast.append(
                {
                    "ds": date.strftime("%Y-%m"),
                    "yhat": yhat,
                    "yhat_lower": max(0.0, yhat - spread),
                    "yhat_upper": yhat + spread,
                }
            )

        return {
            "success": True,
            "status": "success",
            "data": forecast,
            "forecast": forecast,
        }
    except Exception as exc:
        print(f"Forecast error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/cluster", dependencies=[Depends(require_csrf)])
async def cluster_customers(
    data: List[CustomerData], _context: AuthContext = Depends(require_analyst)
):
    try:
        if not data:
            return {"success": True, "status": "empty", "data": [], "clusters": []}

        max_frequency = max(max(0, int(item.frequency or 0)) for item in data) or 1
        max_monetary = max(max(0.0, float(item.monetary or 0)) for item in data) or 1

        clusters = []
        for item in data:
            frequency = max(0, int(item.frequency or 0))
            monetary = max(0.0, float(item.monetary or 0))
            score = (frequency / max_frequency) * 0.45 + (
                monetary / max_monetary
            ) * 0.55
            if score >= 0.75:
                cluster = 0
            elif score >= 0.5:
                cluster = 1
            elif score >= 0.25:
                cluster = 2
            else:
                cluster = 3

            clusters.append(
                {
                    "id": str(item.id),
                    "frequency": frequency,
                    "monetary": monetary,
                    "cluster": cluster,
                }
            )

        return {
            "success": True,
            "status": "success",
            "data": clusters,
            "clusters": clusters,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
async def health_check():
    return success_response(
        {"service": "Nexus Analytics API", "environment": settings.app_env},
        legacy={"status": "ok", "service": "Nexus Analytics API"},
    )


@app.get("/api/sales/realtime")
async def get_realtime_sales(context: AuthContext = Depends(require_viewer)):
    try:
        repository = get_repository()
        if not repository.table_exists("orders"):
            return {"success": True, "status": "empty", "data": []}
        rows = repository.recent_orders(context.workspace_id, 1000)

        data = [
            {
                "OrderID": row["order_id"],
                "CustomerID": row["customer_id"],
                "Category": row["category"],
                "Region": row["region"],
                "Amount": row["amount"],
                "OrderDate": row["order_date"],
            }
            for row in rows
        ]
        return {"success": True, "status": "success", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/anomalies")
async def check_anomalies(context: AuthContext = Depends(require_viewer)):
    try:
        repository = get_repository()
        if not repository.table_exists("orders"):
            return {
                "success": True,
                "status": "success",
                "anomaly": False,
                "message": "No data",
            }
        rows = repository.recent_region_amounts(context.workspace_id, 500)

        if len(rows) < 50:
            return {
                "success": True,
                "status": "success",
                "anomaly": False,
                "message": "Not enough data",
            }

        recent_10 = rows[:10]
        baseline = rows[10:]
        regions = {region for region, _ in rows if region}

        for region in regions:
            recent_values = [
                float(amount or 0)
                for row_region, amount in recent_10
                if row_region == region
            ]
            baseline_values = [
                float(amount or 0)
                for row_region, amount in baseline
                if row_region == region
            ]
            if not recent_values or not baseline_values:
                continue

            recent_avg = sum(recent_values) / len(recent_values)
            baseline_avg = sum(baseline_values) / len(baseline_values)
            if baseline_avg and recent_avg < baseline_avg * 0.8:
                drop_pct = (1 - recent_avg / baseline_avg) * 100
                return {
                    "success": True,
                    "status": "success",
                    "anomaly": True,
                    "message": f"Canh bao: Doanh thu vung {region} giam dot ngot {drop_pct:.1f}%!",
                    "region": region,
                    "drop_pct": drop_pct,
                }

        return {
            "success": True,
            "status": "success",
            "anomaly": False,
            "message": "Normal",
        }
    except Exception as exc:
        print(f"Anomaly error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


def percentage_change(current: float, previous: float):
    if not previous:
        return 0.0
    return round(((current - previous) / previous) * 100, 1)


def latest_order_date(repository, workspace_id: int):
    return parse_date(repository.latest_order_date(workspace_id)) or datetime.now()


def analytics_period(
    repository,
    workspace_id: int,
    days: int,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime, datetime]:
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=400,
            detail="date_from and date_to must be provided together",
        )
    if date_from and date_to:
        if date_from > date_to:
            raise HTTPException(
                status_code=400, detail="date_from must not be after date_to"
            )
        if (date_to - date_from).days > 365:
            raise HTTPException(status_code=400, detail="Date range is too large")
        return datetime.combine(date_from, time.min), datetime.combine(
            date_to, time.max
        )
    latest = latest_order_date(repository, workspace_id)
    return latest - timedelta(days=days - 1), latest


def paged_resource(
    table: str,
    context: AuthContext,
    *,
    page: int,
    page_size: int,
    search: str,
    filters: dict[str, object],
    sort_by: str,
    sort_order: str,
    date_from: date | None,
    date_to: date | None,
):
    page_spec = PageSpec(page, page_size)
    rows, total = get_repository().query_rows(
        table,
        context.workspace_id,
        page=page,
        page_size=page_size,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    return success_response(
        rows,
        meta=query_meta(
            page_spec,
            total,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
        legacy={"status": "success"},
    )


@app.get("/api/dashboard/overview")
async def dashboard_overview(
    days: int = Query(default=7, ge=1, le=365),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    repository = get_repository()
    current_start, latest = analytics_period(
        repository, context.workspace_id, days, date_from, date_to
    )
    period_days = max(1, (latest.date() - current_start.date()).days + 1)
    previous_end = current_start - timedelta(seconds=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    current = repository.period_stats(context.workspace_id, current_start, latest)
    previous = repository.period_stats(
        context.workspace_id, previous_start, previous_end
    )
    trend_rows = repository.daily_revenue(context.workspace_id, current_start, latest)
    source_rows = repository.revenue_grouped(
        context.workspace_id, "category", current_start, latest
    )
    total_source = sum(row["revenue"] for row in source_rows) or 1
    unread_alerts = repository.count_unread_alerts(context.workspace_id)
    insights = repository.list_rows(
        "insights", context.workspace_id, order_by="id", limit=3
    )

    sessions = max(current["orders_count"] * 12, current["users_count"] * 25)
    previous_sessions = max(previous["orders_count"] * 12, previous["users_count"] * 25)
    conversion = round((current["orders_count"] / sessions * 100), 2) if sessions else 0
    previous_conversion = (
        round((previous["orders_count"] / previous_sessions * 100), 2)
        if previous_sessions
        else 0
    )
    data = {
        "period": {
            "days": period_days,
            "from": current_start.date().isoformat(),
            "to": latest.date().isoformat(),
        },
        "summary": {
            "revenue": round(current["revenue"], 2),
            "revenue_change": percentage_change(
                current["revenue"], previous["revenue"]
            ),
            "users": current["users_count"],
            "users_change": percentage_change(
                current["users_count"], previous["users_count"]
            ),
            "conversion": conversion,
            "conversion_change": round(conversion - previous_conversion, 2),
            "sessions": sessions,
            "sessions_change": percentage_change(sessions, previous_sessions),
            "orders": current["orders_count"],
            "average_order": round(current["average_order"], 2),
            "unread_alerts": unread_alerts,
        },
        "trend": trend_rows,
        "traffic_sources": [
            {
                "name": row["name"],
                "value": row["revenue"],
                "share": round(row["revenue"] / total_source * 100, 1),
            }
            for row in source_rows
        ],
        "attention": insights,
    }
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/api/analytics/revenue")
async def revenue_analytics(
    days: int = Query(default=30, ge=1, le=365),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    repository = get_repository()
    start, latest = analytics_period(
        repository, context.workspace_id, days, date_from, date_to
    )
    daily = [
        {"label": row["label"], "revenue": row["value"], "orders": row["orders"]}
        for row in repository.daily_revenue(context.workspace_id, start, latest)
    ]
    by_region = repository.revenue_grouped(
        context.workspace_id, "region", start, latest
    )
    by_category = repository.revenue_grouped(
        context.workspace_id, "category", start, latest
    )
    data = {"daily": daily, "by_region": by_region, "by_category": by_category}
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/api/analytics/funnel")
async def funnel_analytics(
    days: int = Query(default=30, ge=1, le=365),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    repository = get_repository()
    start, latest = analytics_period(
        repository, context.workspace_id, days, date_from, date_to
    )
    stats = repository.period_stats(context.workspace_id, start, latest)
    purchases = stats["orders_count"]
    steps = [
        ("Truy cập", purchases * 8),
        ("Xem sản phẩm", purchases * 6),
        ("Thêm giỏ hàng", purchases * 3),
        ("Bắt đầu checkout", purchases * 2),
        ("Hoàn tất", purchases),
    ]
    first = steps[0][1] or 1
    data = {
        "completion_rate": round(purchases / first * 100, 2),
        "steps": [
            {"name": name, "users": users, "rate": round(users / first * 100, 1)}
            for name, users in steps
        ],
    }
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/api/analytics/cohort")
async def cohort_analytics(_context: AuthContext = Depends(require_viewer)):
    cohorts = []
    for index in range(6):
        base = 1250 - index * 73
        retention = [
            100,
            61 - index,
            44 - index,
            37 - index,
            30 - index,
            23 - index,
            18 - index,
            12,
        ]
        cohorts.append(
            {"cohort": f"Tuần {index + 1}", "users": base, "retention": retention}
        )
    data = {
        "periods": ["W0", "W1", "W2", "W3", "W4", "W5", "W6", "W7"],
        "cohorts": cohorts,
    }
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/api/insights")
async def list_insights(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    severity: str | None = Query(
        default=None, pattern="^(info|low|medium|high|success)$"
    ),
    insight_type: str | None = Query(default=None, max_length=100),
    sort_by: str = Query(
        default="created_at", pattern="^(id|created_at|title|severity)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    return paged_resource(
        "insights",
        context,
        page=page,
        page_size=page_size,
        search=search,
        filters={"severity": severity, "insight_type": insight_type},
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/api/alerts")
async def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    unread_only: bool = False,
    severity: str | None = Query(default=None, pattern="^(low|medium|high|success)$"),
    sort_by: str = Query(
        default="created_at", pattern="^(id|created_at|title|severity|is_read)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    return paged_resource(
        "alerts",
        context,
        page=page,
        page_size=page_size,
        search=search,
        filters={"is_read": 0 if unread_only else None, "severity": severity},
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
    )


@app.post("/api/alerts", status_code=201, dependencies=[Depends(require_csrf)])
async def create_alert(
    payload: AlertCreate, context: AuthContext = Depends(require_analyst)
):
    now = datetime.now().isoformat(timespec="seconds")
    row = get_repository().create_alert(
        context.workspace_id,
        (payload.title, payload.description, payload.severity, 0, now),
    )
    return {"success": True, "status": "success", "data": row}


@app.patch("/api/alerts/{alert_id}/read", dependencies=[Depends(require_csrf)])
async def mark_alert_read(
    alert_id: int = ApiPath(gt=0), context: AuthContext = Depends(require_analyst)
):
    if not get_repository().mark_alert_read(context.workspace_id, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    data = {"id": alert_id, "is_read": True}
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/api/reports")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    status: str | None = Query(default=None, max_length=50),
    report_type: str | None = Query(default=None, max_length=50),
    sort_by: str = Query(
        default="updated_at", pattern="^(id|updated_at|name|status|report_type)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    return paged_resource(
        "reports",
        context,
        page=page,
        page_size=page_size,
        search=search,
        filters={"status": status, "report_type": report_type},
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
    )


@app.post("/api/reports", status_code=201, dependencies=[Depends(require_csrf)])
async def create_report(
    payload: ReportCreate, context: AuthContext = Depends(require_analyst)
):
    now = datetime.now().isoformat(timespec="seconds")
    row = get_repository().create_report(
        context.workspace_id, (payload.name, payload.report_type, "draft", now)
    )
    return {"success": True, "status": "success", "data": row}


@app.get("/api/data-sources")
async def list_data_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    status: str | None = Query(default=None, max_length=50),
    source_type: str | None = Query(default=None, max_length=50),
    health_status: str | None = Query(default=None, max_length=50),
    sort_by: str = Query(
        default="last_sync",
        pattern="^(id|name|status|source_type|last_sync|last_import_at|event_count|health_status)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: AuthContext = Depends(require_viewer),
):
    return paged_resource(
        "data_sources",
        context,
        page=page,
        page_size=page_size,
        search=search,
        filters={
            "status": status,
            "source_type": source_type,
            "health_status": health_status,
        },
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
    )


@app.post("/api/data-sources", status_code=201, dependencies=[Depends(require_csrf)])
async def create_data_source(
    payload: DataSourceCreate, context: AuthContext = Depends(require_admin)
):
    now = datetime.now().isoformat(timespec="seconds")
    row = get_repository().create_data_source(
        context.workspace_id, (payload.name, payload.source_type, "pending", now)
    )
    return {"success": True, "status": "success", "data": row}


@app.get("/api/saved-views")
async def list_saved_views(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    view_type: str | None = Query(default=None, max_length=50),
    is_favorite: bool | None = Query(default=None),
    sort_by: str = Query(
        default="is_favorite", pattern="^(id|name|view_type|is_favorite)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    context: AuthContext = Depends(require_viewer),
):
    return paged_resource(
        "saved_views",
        context,
        page=page,
        page_size=page_size,
        search=search,
        filters={
            "view_type": view_type,
            "is_favorite": int(is_favorite) if is_favorite is not None else None,
        },
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=None,
        date_to=None,
    )


@app.get("/api/profile")
async def get_profile(context: AuthContext = Depends(require_viewer)):
    row = {
        "id": context.user_id,
        "full_name": context.full_name,
        "job_title": context.job_title,
        "email": context.email,
        "phone": context.phone,
        "workspace": context.workspace_name,
        "workspace_id": context.workspace_id,
        "role": context.role,
    }
    return {"success": True, "status": "success", "data": row}


@app.put("/api/profile", dependencies=[Depends(require_csrf)])
async def update_profile(
    payload: ProfileUpdate,
    context: AuthContext = Depends(require_viewer),
    repository: AuthRepository = Depends(get_auth_repository),
):
    try:
        row = repository.update_user_profile(
            context.user_id,
            payload.full_name,
            payload.job_title,
            payload.email,
            payload.phone or "",
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Email is already in use")
        raise
    if row:
        row.update(
            {
                "workspace": context.workspace_name,
                "workspace_id": context.workspace_id,
                "role": context.role,
            }
        )
    return {"success": True, "status": "success", "data": row}


@app.get("/api/bootstrap")
async def bootstrap_application(
    days: int = Query(default=7, ge=1, le=365),
    context: AuthContext = Depends(require_viewer),
):
    overview = await dashboard_overview(days, None, None, context)
    insights = paged_resource(
        "insights",
        context,
        page=1,
        page_size=4,
        search="",
        filters={"severity": None, "insight_type": None},
        sort_by="created_at",
        sort_order="desc",
        date_from=None,
        date_to=None,
    )
    alerts = paged_resource(
        "alerts",
        context,
        page=1,
        page_size=20,
        search="",
        filters={"is_read": None, "severity": None},
        sort_by="created_at",
        sort_order="desc",
        date_from=None,
        date_to=None,
    )
    profile = await get_profile(context)
    data = {
        "overview": overview,
        "insights": insights["data"],
        "alerts": alerts["data"],
        "profile": profile["data"],
    }
    return {"success": True, "status": "success", "data": data, **data}


@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")


@app.head("/")
async def head_index():
    return Response(status_code=200)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/frontend/{filename}")
async def serve_frontend_asset(filename: str):
    allowed_files = {"api-client.js", "resource-state.js", "resource-state.css"}
    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(BASE_DIR / "frontend" / filename)


@app.get("/{filename}")
async def serve_static_file(filename: str):
    allowed_files = {
        "index.html",
        "style.css",
        "app.js",
        "sales_data.csv",
        "sample_data.csv",
    }
    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="Not found")

    file_path = BASE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(file_path)


@app.post("/api/chat", dependencies=[Depends(require_csrf)])
async def chat_with_gemini(
    req: ChatRequest, _context: AuthContext = Depends(require_analyst)
):
    del req
    return JSONResponse(
        status_code=501,
        content=error_response(
            "NOT_IMPLEMENTED", "AI chat is not available in Phase 1"
        ),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
