@echo off
chcp 65001 > nul
echo ==========================================================
echo 🚀 Khởi động GoAffPro Store Hunter & CRM Local App (Windows)
echo ==========================================================

REM Navigate to project root directory
cd /d "%~dp0"

REM Check and setup Python Virtual Environment
if not exist ".venv" (
    echo 📦 Đang tạo môi trường ảo Python (.venv)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo ✅ Đã kích hoạt môi trường Python (.venv)

echo 📦 Đang kiểm tra thư viện Python...
pip install -r requirements.txt -q
python -m playwright install chromium

REM Check and install frontend dependencies
if not exist "frontend\node_modules" (
    echo 📦 Đang cài đặt thư viện frontend (npm install)...
    cd frontend && npm install && cd ..
)

echo ⚡ Đang khởi động Backend FastAPI (Port 8001)...
start "GoAffPro Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001"

echo 🌐 Đang khởi động Frontend Dashboard (Port 5174)...
start "GoAffPro Frontend" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port 5174"

timeout /t 3 /nobreak > nul
echo ==========================================================
echo ✨ Ứng dụng đã sẵn sàng! Đang mở trình duyệt...
echo 👉 Dashboard: http://localhost:5174
echo 👉 Backend API Docs: http://localhost:8001/docs
echo ==========================================================

start http://localhost:5174
pause
