#!/bin/bash

# Navigate to project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "🚀 Khởi động GoAffPro Store Hunter & CRM Local App"
echo "=========================================================="

# Check prerequisites
if ! command -v python3 &> /dev/null; then
    echo "❌ Lỗi: Không tìm thấy Python 3 trên máy của bạn!"
    echo "👉 Vui lòng tải và cài đặt Python từ: https://www.python.org/downloads/"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Lỗi: Không tìm thấy Node.js trên máy của bạn!"
    echo "👉 Vui lòng tải và cài đặt Node.js từ: https://nodejs.org/"
    exit 1
fi

# Check and setup Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "📦 Đang tạo môi trường ảo Python (.venv)..."
    python3 -m venv .venv
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
echo "🧹 Đang dọn dẹp các tiến trình cũ..."
lsof -ti :8001 | xargs kill -9 2>/dev/null
lsof -ti :5174 | xargs kill -9 2>/dev/null

# Start Backend API Server
echo "⚡ Đang khởi động Backend FastAPI (Port 8001)..."
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload &
BACKEND_PID=$!

# Start Frontend Vite Server
echo "🌐 Đang khởi động Frontend Dashboard (Port 5174)..."
cd frontend
npm run dev -- --host 127.0.0.1 --port 5174 &
FRONTEND_PID=$!
cd ..

# Wait for servers to spin up
sleep 3
echo ""
echo "=========================================================="
echo "✨ Ứng dụng đã sẵn sàng hoạt động tại:"
echo "👉 Dashboard: http://localhost:5174"
echo "👉 Backend API Docs: http://localhost:8001/docs"
echo "=========================================================="
echo "💡 Nhấn Ctrl + C để dừng toàn bộ ứng dụng."

# Auto-open browser
if which open > /dev/null; then
    open "http://localhost:5174"
fi

# Trap Ctrl+C to kill both servers cleanly
trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM
wait
