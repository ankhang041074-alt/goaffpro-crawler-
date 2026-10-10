@echo off
chcp 65001 >nul
title GoAffPro Store Hunter & Spy Google Ads
setlocal enabledelayedexpansion

:: 0. Đảm bảo thư mục làm việc luôn là thư mục chứa script
cd /d "%~dp0"

echo ==========================================================
echo 🚀 Khởi động GoAffPro Store Hunter & CRM Local App (Windows)
echo ==========================================================

:: 1. Kiểm tra Python
set "PY_CMD="
python --version >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
) else (
    py -3 --version >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=py -3"
    ) else (
        echo ❌ Lỗi: Không tìm thấy Python trên máy tính của bạn!
        echo 👉 Vui lòng tải và cài đặt Python từ: https://www.python.org/downloads/
        echo ⚠️ Lưu ý: Khi cài đặt nhớ tick chọn "Add python.exe to PATH"
        pause
        exit /b 1
    )
)

:: 2. Kiểm tra Node.js & npm
node --version >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Lỗi: Không tìm thấy Node.js trên máy tính của bạn!
    echo 👉 Vui lòng tải và cài đặt Node.js LTS từ: https://nodejs.org/
    pause
    exit /b 1
)

call npm --version >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ Lỗi: Không tìm thấy npm trên máy tính của bạn!
    echo 👉 Vui lòng kiểm tra lại cài đặt Node.js từ: https://nodejs.org/
    pause
    exit /b 1
)

:: 3. Tạo môi trường ảo Python nếu chưa có
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo 📦 Đang khởi tạo môi trường ảo Python (.venv)...
    %PY_CMD% -m venv "%~dp0.venv"
    if %ERRORLEVEL% neq 0 (
        echo ❌ Lỗi khi khởi tạo môi trường ảo Python (.venv)!
        pause
        exit /b 1
    )
)

:: 4. Kích hoạt môi trường ảo & cài đặt dependencies
echo ✅ Đã xác nhận môi trường Python (.venv)
echo 📦 Đang kiểm tra thư viện Python...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" -q
"%~dp0.venv\Scripts\python.exe" -m playwright install chromium

:: 5. Cài đặt thư viện Frontend nếu chưa có
if not exist "%~dp0frontend\node_modules" (
    echo 📦 Đang cài đặt thư viện frontend (npm install)...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

:: 6. Khởi động Backend FastAPI trong cửa sổ riêng
echo ⚡ Đang khởi động Backend FastAPI (Port 8001)...
start "GoAffPro Backend (FastAPI)" cmd /k "cd /d ""%~dp0"" && call "".venv\Scripts\activate.bat"" && python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload"

:: 7. Khởi động Frontend Vite Dashboard trong cửa sổ riêng
echo 🌐 Đang khởi động Frontend Dashboard (Port 5174)...
start "GoAffPro Frontend (Dashboard)" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host 127.0.0.1 --port 5174"

:: 8. Đợi server khởi động rồi mở trình duyệt
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
