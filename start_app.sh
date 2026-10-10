#!/bin/bash

# Navigate to project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure standard user binary locations are in PATH
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Try loading NVM if node is not immediately found
if ! command -v node &> /dev/null; then
    if [ -s "$HOME/.nvm/nvm.sh" ]; then
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    elif [ -s "/usr/local/opt/nvm/nvm.sh" ]; then
        \. "/usr/local/opt/nvm/nvm.sh"
    elif [ -s "/opt/homebrew/opt/nvm/nvm.sh" ]; then
        \. "/opt/homebrew/opt/nvm/nvm.sh"
    fi
fi

echo "=========================================================="
echo "🚀 Khởi động GoAffPro Store Hunter & CRM Local App"
echo "=========================================================="

# Check Python (python3 or python)
PY_BIN=""
if command -v python3 &> /dev/null; then
    PY_BIN="python3"
elif command -v python &> /dev/null; then
    PY_BIN="python"
else
    echo "❌ Lỗi: Không tìm thấy Python 3 trên máy của bạn!"
    echo "👉 Vui lòng tải và cài đặt Python từ: https://www.python.org/downloads/"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Lỗi: Không tìm thấy Node.js trên máy của bạn!"
    echo "👉 Vui lòng tải và cài đặt Node.js từ: https://nodejs.org/"
    exit 1
fi

# Check npm
if ! command -v npm &> /dev/null; then
    echo "❌ Lỗi: Không tìm thấy npm trên máy của bạn!"
    echo "👉 Vui lòng kiểm tra lại cài đặt Node.js từ: https://nodejs.org/"
    exit 1
fi

# Check and setup Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "📦 Đang tạo môi trường ảo Python (.venv)..."
    "$PY_BIN" -m venv .venv
fi

source .venv/bin/activate
echo "✅ Đã kích hoạt môi trường Python (.venv)"

# Install backend dependencies
echo "📦 Đang kiểm tra thư viện Python..."
pip install -r requirements.txt -q
python -m playwright install chromium

# Check and install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Đang cài đặt thư viện frontend (npm install)..."
    cd frontend && npm install && cd ..
fi

# Cleanup old processes on port 8001 and 5174 if any
PIDS_8001=$(lsof -ti :8001 2>/dev/null || true)
if [ -n "$PIDS_8001" ]; then
    echo "🧹 Đang giải phóng port 8001..."
    echo "$PIDS_8001" | xargs kill -9 2>/dev/null || true
fi

PIDS_5174=$(lsof -ti :5174 2>/dev/null || true)
if [ -n "$PIDS_5174" ]; then
    echo "🧹 Đang giải phóng port 5174..."
    echo "$PIDS_5174" | xargs kill -9 2>/dev/null || true
fi

# Start Backend API Server
echo "⚡ Đang khởi động Backend FastAPI (Port 8001)..."
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload &
BACKEND_PID=$!

# Start Frontend Vite Server
echo "🌐 Đang khởi động Frontend Dashboard (Port 5174)..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174 &
FRONTEND_PID=$!
cd ..

# Graceful shutdown handler
cleanup() {
    echo ""
    echo "🛑 Đang tắt ứng dụng GoAffPro..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    sleep 0.5
    lsof -ti :8001 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti :5174 2>/dev/null | xargs kill -9 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for servers to spin up
sleep 3
echo ""
echo "=========================================================="
echo "✨ Ứng dụng đã sẵn sàng hoạt động tại:"
echo "👉 Dashboard: http://127.0.0.1:5174 hoặc http://localhost:5174"
echo "👉 Direct API & Swagger: http://127.0.0.1:8001/docs"
echo "=========================================================="
echo "💡 Nhấn Ctrl + C để dừng toàn bộ ứng dụng."

# Auto-open browser
if command -v open &> /dev/null; then
    open "http://127.0.0.1:5174"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:5174"
fi

wait
