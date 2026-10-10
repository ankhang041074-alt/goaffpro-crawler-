@echo off
chcp 65001 >nul
title GoAffPro Store Hunter & Spy Google Ads
setlocal enabledelayedexpansion

echo ==========================================================
echo 🚀 Khởi động GoAffPro Store Hunter & CRM Local App (Windows)
echo ==========================================================

:: 1. Kiểm tra Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo ❌ Lỗi: Không tìm thấy Python trên máy tính của bạn!
        echo 👉 Vui lòng tải và cài đặt Python từ: https://www.python.org/downloads/
        echo ⚠️ Lưu ý: Khi cài đặt nhớ tick chọn "Add python.exe to PATH"
        pause
        exit /b 1
    ) else (
        set "PY_CMD=py -3"
    )
) else (
    set "PY_CMD=python"
)

:: 2. Kiểm tra Node.js
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Lỗi: Không tìm thấy Node.js trên máy tính của bạn!
    echo 👉 Vui lòng tải và cài đặt Node.js LTS từ: https://nodejs.org/
    pause
    exit /b 1
)

:: 3. Tạo môi trường ảo Python nếu chưa có
if not exist ".venv" (
    echo 📦 Đang khởi tạo môi trường ảo Python (.venv)...
    %PY_CMD% -m venv .venv
)

:: 4. Kích hoạt môi trường ảo
call .venv\Scripts\activate.bat
echo ✅ Đã kích hoạt môi trường Python (.venv)

:: 5. Cài đặt thư viện Python & Playwright Chromium
echo 📦 Đang kiểm tra thư viện Python...
pip install -r requirements.txt -q
python -m playwright install chromium

:: 6. Cài đặt thư viện Frontend nếu chưa có
if not exist "frontend\node_modules" (
    echo 📦 Đang cài đặt thư viện frontend (npm install)...
    cd frontend
    call npm install
    cd ..
)

:: 7. Khởi động Backend FastAPI trong cửa sổ riêng
echo ⚡ Đang khởi động Backend FastAPI (Port 8001)...
start "GoAffPro Backend (FastAPI)" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload"

:: 8. Khởi động Frontend Vite Dashboard trong cửa sổ riêng
echo 🌐 Đang khởi động Frontend Dashboard (Port 5174)...
start "GoAffPro Frontend (Dashboard)" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port 5174"

:: 9. Đợi server khởi động rồi mở trình duyệt
echo ⏳ Đang đợi server khởi chạy...
timeout /t 4 /nobreak >nul

echo.
echo ==========================================================
echo ✨ Ứng dụng đã sẵn sàng hoạt động tại:
echo 👉 Dashboard: http://127.0.0.1:5174 hoặc http://localhost:5174
echo 👉 Direct API: http://127.0.0.1:8001
echo ==========================================================
echo 💡 Không tắt 2 cửa sổ cmd phụ vừa mở (Backend & Frontend).
echo 💡 Đóng cửa sổ này khi bạn không cần theo dõi thêm.
echo.

start http://localhost:5174
pause
