# Deploy len Render

Du an nay deploy len Render bang mot Python Web Service. FastAPI se phuc vu ca backend API va giao dien `index.html`.

## Cach 1: Dung Blueprint

1. Day code len GitHub.
2. Vao Render, chon **New +** > **Blueprint**.
3. Chon repository cua du an.
4. Render se doc file `render.yaml` va tao service `datainsight-dashboard`.
5. Neu muon dung Gemini that, them gia tri cho bien moi truong `GEMINI_API_KEY`.
6. Bam **Apply** de build va deploy.

## Cach 2: Tao Web Service thu cong

1. Vao Render, chon **New +** > **Web Service**.
2. Chon repository cua du an.
3. Cau hinh:
   - Runtime: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn ai_service:app --host 0.0.0.0 --port $PORT`
4. Them Environment Variable:
   - `PYTHON_VERSION=3.11.9`
   - `GEMINI_API_KEY=<key cua ban>` neu can AI chat that
5. Bam **Create Web Service**.

## Luu y

- Frontend da dung URL tuong doi, nen tren Render se goi API cung domain.
- Render free plan co the sleep sau mot thoi gian khong truy cap.
- Neu build bi cham, nguyen nhan thuong la goi `prophet` can cai nhieu dependency.
