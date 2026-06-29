from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import pandas as pd
from prophet import Prophet
from sklearn.cluster import KMeans
import uvicorn
import sqlite3
from datetime import datetime, timedelta
import os
try:
    import google.generativeai as genai
except ImportError:
    genai = None

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / 'sales.db'

app = FastAPI(title="DataInsight AI Service")

# CẤU HÌNH CORS: Cho phép Frontend truy cập vào AI Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Cho phép tất cả các nguồn (local file, localhost, v.v.)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SalesData(BaseModel):
    ds: str # Date
    y: float # Value

class CustomerData(BaseModel):
    id: str
    frequency: int
    monetary: float

class ChatRequest(BaseModel):
    message: str

@app.post("/forecast")
async def forecast_sales(data: List[SalesData]):
    try:
        if not data: return {"status": "empty", "forecast": []}
        df = pd.DataFrame([item.dict() for item in data])
        
        # Prophet model
        model = Prophet(yearly_seasonality=True, daily_seasonality=False, weekly_seasonality=True)
        model.fit(df)
        
        future = model.make_future_dataframe(periods=6, freq='ME') # 'ME' for Month End
        forecast = model.predict(future)
        
        result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(6)
        result['ds'] = result['ds'].dt.strftime('%Y-%m') # Format date to YYYY-MM
        return {"status": "success", "forecast": result.to_dict('records')}
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cluster")
async def cluster_customers(data: List[CustomerData]):
    try:
        if not data: return {"status": "empty", "clusters": []}
        df = pd.DataFrame([item.dict() for item in data])
        
        # K-Means clustering
        X = df[['frequency', 'monetary']]
        n_clusters = min(len(df), 4) # Tránh lỗi nếu dữ liệu quá ít
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        df['cluster'] = kmeans.fit_predict(X)
        
        return {"status": "success", "clusters": df.to_dict('records')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            
        cursor.execute("SELECT order_id, customer_id, category, region, amount, order_date FROM orders ORDER BY order_date DESC LIMIT 1000")
        rows = cursor.fetchall()
        
        data = []
        for row in rows:
            data.append({
                "OrderID": row[0],
                "CustomerID": row[1],
                "Category": row[2],
                "Region": row[3],
                "Amount": row[4],
                "OrderDate": row[5]
            })
        conn.close()
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/anomalies")
async def check_anomalies():
    try:
        conn = sqlite3.connect(DB_FILE)
        # Handle case where table might not exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if not cursor.fetchone():
            conn.close()
            return {"status": "success", "anomaly": False, "message": "No data"}
            
        df = pd.read_sql_query("SELECT * FROM orders ORDER BY order_date DESC LIMIT 500", conn)
        conn.close()
        
        if df.empty or len(df) < 50:
            return {"status": "success", "anomaly": False, "message": "Not enough data"}
            
        recent_10 = df.head(10)
        baseline = df.iloc[10:]
        
        for region in df['region'].unique():
            recent_avg = recent_10[recent_10['region'] == region]['amount'].mean()
            baseline_avg = baseline[baseline['region'] == region]['amount'].mean()
            
            if pd.isna(recent_avg) or pd.isna(baseline_avg) or baseline_avg == 0: continue
                
            if recent_avg < baseline_avg * 0.8: # Drop by 20%
                drop_pct = (1 - recent_avg / baseline_avg) * 100
                return {
                    "status": "success",
                    "anomaly": True, 
                    "message": f"Cảnh báo: Doanh thu vùng {region} giảm đột ngột {drop_pct:.1f}%!",
                    "region": region,
                    "drop_pct": drop_pct
                }
                
        return {"status": "success", "anomaly": False, "message": "Normal"}
    except Exception as e:
        print(f"Anomaly Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")

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
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or not genai:
            return {
                "status": "success", 
                "reply": f"Tôi đang phân tích yêu cầu: '{req.message}'.\n(Đây là phản hồi mô phỏng. Vui lòng `pip install google-generativeai` và set biến môi trường `GEMINI_API_KEY` ở backend để dùng AI thật)."
            }
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"Bạn là trợ lý phân tích dữ liệu DataInsight. Trả lời ngắn gọn, chuyên nghiệp bằng tiếng Việt: {req.message}"
        response = model.generate_content(prompt)
        
        return {"status": "success", "reply": response.text}
    except Exception as e:
        print(f"Chat Error: {str(e)}")
        return {"status": "error", "reply": "Lỗi kết nối Gemini AI. Chi tiết: " + str(e)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
