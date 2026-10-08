# 🚀 GoAffPro Store Hunter, Traffic Intelligence & CRM Suite

Ứng dụng nội bộ hoàn chỉnh (Full-Stack Desktop & Web App) chuyên dụng để săn tìm, phân tích lưu lượng truy cập thực tế (Similarweb & Tranco), bóc tách xu hướng tìm kiếm 5 năm (Google Trends), phân loại ngành hàng thông minh và quản lý quan hệ đối tác affiliate (CRM).

---

## 🌟 Tính Năng Cốt Lõi (Key Features)

### 1. 🌐 Tích Hợp Similarweb Thực Tế (Traffic.cv Worker)
* **Dữ liệu thật 100% từ Similarweb:** Bóc tách chính xác Total Monthly Visits, Global Rank, Country Rank, Bounce Rate (Tỷ lệ thoát), Avg Visit Duration (Thời gian onsite), và Pages per Visit.
* **Cơ Chế Vượt Rào Cloudflare Turnstile 3 Lớp:**
  * **Lớp 1 (Tự động):** Chạy Chrome thật với profile lưu phiên, hầu hết các lượt truy vấn tự động vượt qua Turnstile.
  * **Lớp 2 (Cảnh báo thông minh):** Nếu gặp Captcha người thật, cửa sổ tự động bung lên màn hình, phát chuông báo macOS `Glass.aiff` để người dùng bấm giải.
  * **Lớp 3 (Chống treo luồng sau 90s):** Nếu người dùng đi vắng quá 90 giây, hệ thống tự động Fallback sang công thức Tranco Zipf và tiếp tục sang store tiếp theo, **tuyệt đối không bao giờ bị đơ hay treo máy**.
* **Cào Ngầm 100% Không Làm Phiền (Stealth Crawling):** Cửa sổ Chrome tự động thu nhỏ xuống Dock (`windowState: minimized`), không chiếm con trỏ chuột, không giật màn hình.

---

### 2. 📈 Google Trends 5 Năm & Bộ Lọc Đón Sóng Mùa Bán Chạy (Growth & Evergreen)
* **Biểu đồ thời gian thực (Interactive SVG Timeline):** Thể hiện chi tiết mức độ quan tâm tìm kiếm từ 0 - 100 điểm suốt 2 - 5 năm, đánh dấu tháng bùng nổ nhất (`🔥 Peak Month`).
* **Bộ lọc Đều Đặn Quanh Năm (`🟢 Evergreen / Nhấp đều`):** Tìm các store có lượng tìm kiếm bền vững, không bị phụ thuộc vào mùa vụ.
* **Bộ lọc theo Tháng (Tháng 1 -> Tháng 12) với 4 tiêu chí:**
  1. `🌊 Tất cả`: Xem các store có phát sinh tìm kiếm trong tháng.
  2. `↗️ Đón sóng tăng trưởng`: Store đang vào mùa bán chạy (điểm tháng này tăng so với tháng trước).
  3. `🏔️ Bùng nổ đạt đỉnh`: Tháng được chọn chính là mùa bán chạy nhất năm (`🏔️ Đỉnh T{tháng}`).
  4. `🔥 Lượng tìm kiếm cao`: Thương hiệu lớn có độ hot vượt trội ($\ge 50$ điểm).
* **Cơ Chế HTTP/2 TLS Fingerprint:** Sử dụng `curl_cffi` giả lập Chrome 124 TLS/JA3 và cơ chế tái sử dụng Cookie NID/SOCS trên ổ đĩa, phản hồi cực nhanh (~0.3s) và tự động giãn cách khi gặp giới hạn của Google mà không cần bật VPN.

---

### 3. 🎯 Bộ Lọc Thời Hạn Cookie Tinh Gọn (Cookie Retention)
Được tối ưu thành 4 nhóm chuẩn hóa:
* `Dưới 14 ngày (< 14 days)`
* `14 – 30 ngày (14d – 30d)`
* `30 ngày trở lên (≥ 30 days)`
* `≥ 14 ngày (Chuẩn)`: Tập trung các cơ hội affiliate bền vững với tỷ lệ giữ chân hoa hồng tốt nhất.

---

### 4. 🏷️ Phân Loại Ngành Hàng Đa Tầng & Lọc 18+ Tinh Tế
* **Nhận diện chính xác Decor & Home:** Tự động xếp các store trang trí, quà tặng, nội thất vào đúng nhóm `Home, Living & Decor`.
* **Phân biệt rạch ròi 18+ vs Sức khỏe & Chăm sóc cá nhân:**
  * **Sức khỏe / Sinh lý sạch:** Bao cao su y tế, gel bôi trơn, dung dịch vệ sinh $\rightarrow$ Gán nhãn `Health & Personal Care` an toàn (`is_adult = 0`).
  * **18+ Thô tục / Hardcore NSFW:** Búp bê tình dục, đồ chơi BDSM $\rightarrow$ Gán nhãn `Adult 18+` (`is_adult = 1`) và hỗ trợ ẩn mặc định bằng bộ lọc SafeFilter.
* **Nút 1-Click Xóa Store Nam Á / Ấn Độ:** Tự động quét sạch các store sử dụng tiền tệ Nam Á (`INR`, `PKR`, `BDT`...) hoặc tên miền nội địa `.in`, `.pk`, `.bd`.

---

### 5. 💼 CRM Mini & Xuất Báo Cáo
* Đánh dấu yêu thích (`★`), lưu ghi chú nội bộ cho từng store trực tiếp vào database.
* Xuất file **Excel (.xlsx)** hoặc **CSV** chỉ với 1 click, tương thích 100% với các bộ lọc đang chọn.

---

## 💻 Hướng Dẫn Cài Đặt & Chạy Mới Từ Đầu (Setup from Scratch)

Dự án được đóng gói khép kín, hoạt động độc lập trên máy sạch mà không phụ thuộc vào bất kỳ cấu hình máy cũ nào.

### 📋 Yêu Cầu Tiên Quyết
* **Python**: 3.10 trở lên ([Tải Python](https://www.python.org/downloads/))
* **Node.js**: 18 trở lên ([Tải Node.js](https://nodejs.org/))
* **Git**: ([Tải Git](https://git-scm.com/))

---

### 🍏 Cách 1: Chạy Tự Động 1-Click (Khuyên Dùng)

#### Trên macOS / Linux:
Mở Terminal tại thư mục dự án và chạy:
```bash
bash start_app.sh
```

#### Trên Windows:
Nhấp đúp chuột (Double-click) vào file:
```cmd
start_app.bat
```

> **Script sẽ tự động thực hiện từ A đến Z:**
> 1. Tự tạo môi trường ảo Python `.venv` nếu chưa có.
> 2. Tự cài đặt đầy đủ dependencies trong `requirements.txt` (FastAPI, Playwright, curl_cffi, pytrends, pandas...).
> 3. Tự cài đặt trình duyệt Chromium cho Playwright (`python -m playwright install chromium`).
> 4. Tự tải và cài đặt Frontend `npm install`.
> 5. Khởi động Backend API tại `http://127.0.0.1:8001`.
> 6. Khởi động Frontend Vite tại `http://127.0.0.1:5174`.
> 7. Tự động mở trình duyệt web lên để bạn sử dụng ngay lập tức!

---

### 🛠️ Cách 2: Khởi Động Thủ Công Từng Bước (Manual Setup)

#### 1. Clone Source Code
```bash
git clone https://github.com/ankhang041074-alt/goaffpro-crawler-.git
cd goaffpro-crawler-
```

#### 2. Cài Đặt Môi Trường Python Backend
```bash
# Tạo môi trường ảo
python3 -m venv .venv

# Kích hoạt môi trường (macOS/Linux)
source .venv/bin/activate
# Hoặc trên Windows: .venv\Scripts\activate

# Cài đặt thư viện
pip install -r requirements.txt

# Cài đặt browser Playwright
python -m playwright install chromium
```

#### 3. Khởi Động Backend API
```bash
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload
```
*API docs & Swagger:* `http://127.0.0.1:8001/docs`

#### 4. Cài Đặt & Khởi Động Frontend UI
Mở một cửa sổ Terminal mới:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```
*Giao diện Dashboard:* `http://127.0.0.1:5174`

---

## 📁 Cấu Trúc Thư Mục Dự Án (File Structure)

```
goaffpro-crawler/
├── backend/
│   ├── api.py                 # FastAPI RESTful Server (Routes, Filter, Export, Worker Control)
│   ├── categorizer.py         # NLP phân loại ngành hàng đa tầng & lọc an toàn 18+
│   ├── crawler.py             # Playwright crawler tự động 5 bước cào danh sách GoAffPro
│   ├── db.py                  # Quản lý SQLite, auto-migration, index tối ưu & query tốc độ cao
│   ├── traffic_worker.py      # Background worker Google Trends & Tranco Zipf ranking
│   ├── traffic_cv_worker.py   # Background worker Similarweb Traffic.cv (Vượt Cloudflare 3 lớp)
│   └── traffic_cv_scraper.py  # Playwright bóc tách dữ liệu Similarweb từ traffic.cv
├── data/
│   ├── goaffpro.db            # Cơ sở dữ liệu SQLite đã làm giàu (20.800+ stores sạch)
│   └── schema.sql             # Bản sao lưu cấu trúc database hoàn chỉnh
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Dashboard React 19: Accordion row, Biểu đồ SVG, Bộ lọc đa năng
│   │   ├── main.tsx           # Entry point React
│   │   └── index.css          # Tailwind CSS v4 styling
│   ├── package.json           # Dependencies Frontend
│   ├── package-lock.json      # Dependency lockfile đảm bảo tính nhất quán
│   └── vite.config.ts         # Cấu hình Vite bundler
├── scripts/
│   └── test_30_traffic_cv.py  # Script kiểm thử và benchmark tự động
├── .env.example               # Mẫu biến môi trường cấu hình hệ thống
├── .gitignore                 # Danh sách loại trừ file nhạy cảm và tạm thời
├── requirements.txt           # Danh sách thư viện Python chuẩn
├── start_app.sh               # Script tự động hóa 1-click (macOS / Linux)
├── start_app.bat              # Script tự động hóa 1-click (Windows)
└── README.md                  # Hướng dẫn chi tiết này
```

---

## 🔒 Chính Sách An Toàn & Bảo Mật Dữ Liệu
* **Zero-Fake-Data:** Tuyệt đối không sinh dữ liệu ảo. Store dưới ngưỡng thống kê được đánh dấu trung thực là `no_data`.
* **Zero-Leakage:** Dự án không chứa bất kỳ secret token, mật khẩu hay API key cá nhân nào.
* **Tự lưu & Chống mất mát:** Mỗi store cào xong được commit ngay vào SQLite; hỗ trợ dừng/tiếp tục bất kỳ lúc nào mà không sợ mất tiến độ.
