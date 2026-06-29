from calendar import monthrange
from datetime import datetime
from pathlib import Path
import os
import sqlite3
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "sales.db"

app = FastAPI(title="DataInsight AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SalesData(BaseModel):
    ds: str
    y: float


class CustomerData(BaseModel):
    id: str
    frequency: int
    monetary: float


class ChatRequest(BaseModel):
    message: str


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


@app.post("/forecast")
async def forecast_sales(data: List[SalesData]):
    try:
        if not data:
            return {"status": "empty", "forecast": []}

        monthly_totals = {}
        for item in data:
            date = parse_date(item.ds)
            if not date:
                continue
            month_key = date.strftime("%Y-%m")
            monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + float(item.y or 0)

        if not monthly_totals:
            return {"status": "empty", "forecast": []}

        months = sorted(monthly_totals)
        values = [monthly_totals[month] for month in months]
        count = len(values)

        if count >= 2:
            x_mean = (count - 1) / 2
            y_mean = sum(values) / count
            denominator = sum((index - x_mean) ** 2 for index in range(count)) or 1
            slope = sum((index - x_mean) * (values[index] - y_mean) for index in range(count)) / denominator
            intercept = y_mean - slope * x_mean
        else:
            slope = 0.0
            intercept = values[0]

        predicted_history = [slope * index + intercept for index in range(count)]
        residuals = [values[index] - predicted_history[index] for index in range(count)]
        if len(residuals) > 2:
            avg_residual = sum(residuals) / len(residuals)
            spread = (sum((r - avg_residual) ** 2 for r in residuals) / len(residuals)) ** 0.5
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

        return {"status": "success", "forecast": forecast}
    except Exception as exc:
        print(f"Forecast error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/cluster")
async def cluster_customers(data: List[CustomerData]):
    try:
        if not data:
            return {"status": "empty", "clusters": []}

        max_frequency = max(max(0, int(item.frequency or 0)) for item in data) or 1
        max_monetary = max(max(0.0, float(item.monetary or 0)) for item in data) or 1

        clusters = []
        for item in data:
            frequency = max(0, int(item.frequency or 0))
            monetary = max(0.0, float(item.monetary or 0))
            score = (frequency / max_frequency) * 0.45 + (monetary / max_monetary) * 0.55
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

        return {"status": "success", "clusters": clusters}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "DataInsight AI"}


@app.get("/api/sales/realtime")
async def get_realtime_sales():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if not cursor.fetchone():
            conn.close()
            return {"status": "empty", "data": []}

        cursor.execute(
            "SELECT order_id, customer_id, category, region, amount, order_date "
            "FROM orders ORDER BY order_date DESC LIMIT 1000"
        )
        rows = cursor.fetchall()
        conn.close()

        data = [
            {
                "OrderID": row[0],
                "CustomerID": row[1],
                "Category": row[2],
                "Region": row[3],
                "Amount": row[4],
                "OrderDate": row[5],
            }
            for row in rows
        ]
        return {"status": "success", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/anomalies")
async def check_anomalies():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if not cursor.fetchone():
            conn.close()
            return {"status": "success", "anomaly": False, "message": "No data"}

        cursor.execute("SELECT region, amount FROM orders ORDER BY order_date DESC LIMIT 500")
        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 50:
            return {"status": "success", "anomaly": False, "message": "Not enough data"}

        recent_10 = rows[:10]
        baseline = rows[10:]
        regions = {region for region, _ in rows if region}

        for region in regions:
            recent_values = [float(amount or 0) for row_region, amount in recent_10 if row_region == region]
            baseline_values = [float(amount or 0) for row_region, amount in baseline if row_region == region]
            if not recent_values or not baseline_values:
                continue

            recent_avg = sum(recent_values) / len(recent_values)
            baseline_avg = sum(baseline_values) / len(baseline_values)
            if baseline_avg and recent_avg < baseline_avg * 0.8:
                drop_pct = (1 - recent_avg / baseline_avg) * 100
                return {
                    "status": "success",
                    "anomaly": True,
                    "message": f"Canh bao: Doanh thu vung {region} giam dot ngot {drop_pct:.1f}%!",
                    "region": region,
                    "drop_pct": drop_pct,
                }

        return {"status": "success", "anomaly": False, "message": "Normal"}
    except Exception as exc:
        print(f"Anomaly error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")


@app.head("/")
async def head_index():
    return Response(status_code=200)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/{filename}")
async def serve_static_file(filename: str):
    allowed_files = {"index.html", "style.css", "app.js", "sales_data.csv", "sample_data.csv"}
    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="Not found")

    file_path = BASE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(file_path)


@app.post("/api/chat")
async def chat_with_gemini(req: ChatRequest):
    return {
        "status": "success",
        "reply": f"Toi da nhan yeu cau: '{req.message}'. Ban Render free dang dung che do AI mo phong nhe de tiet kiem RAM.",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
