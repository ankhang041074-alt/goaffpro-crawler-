# 🚀 GoAffPro Store Hunter, Google Ads Spy & Traffic Intelligence Suite

Ứng dụng nội bộ full-stack (Desktop & Web App) chuyên dụng để **săn tìm store affiliate tiềm năng**, **bóc tách chiến dịch Google Ads Transparency (All-Time Spy)**, **phân tích lưu lượng truy cập Similarweb & Tranco**, và **đọc vị chu kỳ tìm kiếm 3-5 năm trên Google Trends** nhằm phục vụ tối đa cho Affiliate Marketer, Media Buyer và Growth Hacker.

---

## 🌟 Tính Năng Đột Phá (Core Capabilities)

### 1. 🕵️ Google Ads Transparency Spy Engine (Toàn Diện & Chuẩn Xác)
* **Bóc Tách Dữ Liệu Ads Không Giới Hạn Thời Gian (All-Time Mode):**
  * Tự động crawl toàn bộ lịch sử mẫu quảng cáo của từng store trực tiếp từ Google Ads Transparency Center.
  * Trích xuất chính xác: Tiêu đề quảng cáo (Headline), Nội dung mô tả (Description), Trang đích (Landing Page), Định dạng (Google Search Text Ads / Display Image Ads), Ngày hiển thị đầu tiên (`first_seen`) và Ngày hiển thị gần nhất (`last_shown`).
* **Phân Loại Chiến Dịch 3 Nhóm Chuẩn Hóa (Tripartite Classification):**
  * 🌲 **Chạy Quanh Năm (Evergreen):** Chiến dịch chạy liên tục xuyên suốt các quý ($\ge 6 - 7$ tháng/năm hoặc tuổi thọ $\ge 180$ ngày), doanh số và nhu cầu ổn định quanh năm.
  * 🍂 **Chạy Theo Mùa (Seasonal):** Chiến dịch tập trung dồn ngân sách vào các tháng cao điểm cố định trong năm (đặc biệt là Q4: Black Friday, Cyber Monday, Giáng Sinh).
  * 🟡 **Mới Chạy (New Test):** Mẫu quảng cáo mới được tung ra thử nghiệm trong vòng 30 ngày gần đây.
* **Ma Trận Mùa Vụ 3 Năm Trực Tiếp (3-Year Seasonality Matrix 2024 - 2026):**
  * Hiển thị bảng ma trận 3 hàng năm chồng trực tiếp (2024, 2025, 2026) với 12 tháng (T1 - T12) hiển thị trực quan các tháng chiến dịch có phân phối quảng cáo.
  * Hiển thị tuổi thọ quảng cáo chính xác theo công thức ngày thực tế: `duration_days = max(1, (last_shown - first_seen).days + 1)`.
* **Bộ Lọc Phân Cấp Quy Mô Ads:**
  * 🔥 `Quy mô lớn (≥10 mẫu ads)`: Store đang vít ngân sách cực mạnh (Super Scale).
  * 🟢 `Đang chạy đều (2 - 9 mẫu ads)`: Store có dàn quảng cáo chạy ổn định (Winning Ads).
  * 🟡 `Mới thử nghiệm (1 mẫu ad)`: Store mới test thị trường.
  * ⚪ `Chưa chạy ads (0 ads)`: Store chưa triển khai Google Ads.
* **Worker Độc Lập Cách Ly Profile (Worker Profile Isolation):**
  * Worker chạy ngầm Playwright với Chrome Profile riêng biệt (`data/chrome_profile_spy`), độc lập hoàn toàn với worker Similarweb và người dùng, không lo xung đột phiên.

---

### 2. 📈 Google Trends 5 Năm & Đánh Giá Mùa Vụ 3 Năm
* **Biểu Đồ Xu Hướng SVG Tương Tác:** Trực quan hóa điểm tìm kiếm thương hiệu từ 0 - 100 điểm suốt 3 - 5 năm, định vị chính xác tháng đỉnh (`🔥 Peak Month`).
* **Đọc Vị Từng Năm (2024, 2025, 2026):** Tự động phân tích xem từng năm thương hiệu bán theo mùa hay bán full mùa quanh năm, đưa ra lời khuyên chiến lược ngân sách cụ thể cho Affiliate.
* **Bộ Lọc Đón Sóng Mùa Bán Chạy:**
  1. `🟢 Evergreen`: Lưu lượng nhấp đều quanh năm, không đứt gãy.
  2. `↗️ Đón sóng tăng trưởng`: Store đang bước vào mùa tăng trưởng lưu lượng.
  3. `🏔️ Bùng nổ đạt đỉnh`: Lọc theo tháng đạt đỉnh cao nhất năm.
  4. `🔥 Độ hot cao`: Lượng tìm kiếm lớn ($\ge 50$ điểm).
* **Kết Nối TLS/JA3 HTTP/2 Siêu Tốc:** Giả lập Chrome TLS Fingerprint với `curl_cffi`, tái sử dụng cookie Google an toàn, phản hồi tức thì (~0.3s/store) mà không cần VPN.

---

### 3. 🌐 Similarweb Traffic Thực Tế (Traffic.cv Worker)
* **Dữ Liệu Thật 100% Từ Similarweb:** Bóc tách Total Monthly Visits, Global Rank, Country Rank, Bounce Rate, Avg Visit Duration, và Pages per Visit.
* **Cơ Chế Vượt Cloudflare Turnstile 3 Lớp:**
  * *Lớp 1 (Tự động):* Tận dụng phiên Chrome lưu cookie để tự động vượt qua Turnstile.
  * *Lớp 2 (Cảnh báo thông minh):* Khi có captcha tương tác, cửa sổ tự động hiển thị và phát âm thanh thông báo.
  * *Lớp 3 (Chống treo luồng 90s):* Nếu người dùng vắng mặt quá 90 giây, hệ thống tự động fallback công thức Tranco Zipf và tiếp tục store kế tiếp, **không bao giờ đơ hay tắc nghẽn luồng**.
* **Chế Độ Cào Tàng Hình (Stealth Mode):** Cửa sổ trình duyệt thu nhỏ xuống Taskbar/Dock, không chiếm chuột, không gây gián đoạn công việc của người dùng.

---

### 4. 🎯 Bộ Lọc Hoa Hồng, Thời Hạn Cookie & Ngành Hàng
* **Bộ Lọc Thời Hạn Cookie Tinh Gọn:**
  * `Dưới 14 ngày (< 14 days)`
  * `14 – 30 ngày (14d – 30d)`
  * `30 ngày trở lên (≥ 30 days)`
  * `≥ 14 ngày (Chuẩn khuyên dùng)`
* **Bộ Lọc Phân Cấp Hoa Hồng (% Commission):** Lọc theo dải hoa hồng từ 5%, 10%, 15%, 20%+ hoặc hoa hồng cố định.
* **Phân Loại Ngành Hàng NLP & SafeFilter 18+:**
  * Nhận diện chuẩn xác nhóm nội thất & trang trí `Home, Living & Decor`.
  * Phân biệt sinh lý sức khỏe y tế (`Health & Personal Care`) và sản phẩm người lớn nhạy cảm (`Adult 18+`).
  * Nút bấm 1-click lọc nhanh hoặc ẩn các store không phù hợp.

---

### 5. 💼 Quản Trị CRM Đối Tác & Xuất Báo Cáo
* Đánh dấu sao yêu thích (`★`), lưu ghi chú đàm phán hợp tác trực tiếp vào SQLite.
* Xuất báo cáo chuyên nghiệp ra **Excel (.xlsx)** hoặc **CSV** chỉ với 1 click, tương thích đầy đủ bộ lọc đang hiển thị.

---

## 💻 Hướng Dẫn Cài Đặt & Sử Dụng (Dễ Hiểu Cho Mọi Máy Tính)

Ứng dụng được thiết kế độc lập, đóng gói hoàn chỉnh, hỗ trợ mượt mà trên **Windows**, **macOS** và **Linux**.

### 📋 Yêu Cầu Cài Đặt Sẵn
* **Python**: 3.10 trở lên ([Tải Python chính thức](https://www.python.org/downloads/)) — *Lưu ý trên Windows: Nhớ tích chọn **"Add python.exe to PATH"** khi cài đặt.*
* **Node.js**: 18 trở lên ([Tải Node.js LTS](https://nodejs.org/))
* **Git**: ([Tải Git](https://git-scm.com/))

---

### 🚀 Cách 1: Khởi Động 1-Click (Khuyên Dùng)

#### 👉 Dành Cho macOS & Linux:
Mở Terminal tại thư mục dự án và chạy:
```bash
bash start_app.sh
```

#### 👉 Dành Cho Windows:
Nhấp đúp chuột (Double-Click) vào file:
```cmd
start_app.bat
```
*(Hoặc mở Command Prompt / PowerShell tại thư mục dự án và gõ `start_app.bat`)*

> **Script tự động làm mọi việc cho bạn:**
> 1. Tự động kiểm tra và tạo môi trường ảo Python `.venv`.
> 2. Tự động cài đặt toàn bộ thư viện từ `requirements.txt`.
> 3. Tự động cài đặt browser Chromium cho Playwright (`python -m playwright install chromium`).
> 4. Tự động cài đặt gói thư viện Frontend `npm install` (nếu chưa có).
> 5. Khởi động Backend API tại `http://127.0.0.1:8001`.
> 6. Khởi động Frontend Dashboard tại `http://127.0.0.1:5174`.
> 7. Tự động mở trình duyệt web lên để bạn sử dụng ngay!

---

### 🛠️ Cách 2: Khởi Động Thủ Công Từng Bước

#### Bước 1: Clone Repository
```bash
git clone https://github.com/ankhang041074-alt/goaffpro-crawler-.git
cd goaffpro-crawler-
```

#### Bước 2: Cài Đặt Backend Python
```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv

# 2. Kích hoạt môi trường:
# Trên macOS / Linux:
source .venv/bin/activate
# Trên Windows:
call .venv\Scripts\activate

# 3. Cài đặt các thư viện Python
pip install -r requirements.txt

# 4. Cài đặt browser Chromium cho Playwright
python -m playwright install chromium
```

#### Bước 3: Khởi Động Backend API Server
```bash
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload
```
*Tài liệu Swagger / API:* `http://127.0.0.1:8001/docs`

#### Bước 4: Cài Đặt & Khởi Động Frontend Dashboard
Mở thêm một cửa sổ Terminal mới:
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```
*Truy cập giao diện chính:* `http://127.0.0.1:5174`

---

## 🧪 Kiểm Thử Hệ Thống (Quality Assurance & Test Suite)

Dự án đi kèm bộ kiểm thử tự động toàn diện từ Backend đến Frontend để đảm bảo hoạt động 100% không có lỗi trước khi sử dụng hoặc triển khai:

### 1. Chạy Toàn Bộ Unit Test Python (Backend & Crawler)
```bash
# Kích hoạt .venv nếu chưa kích hoạt
source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate

# Chạy khám phá và thực thi toàn bộ 30+ tests
python3 -m unittest discover tests -p "test_*.py"
```
*Kiểm thử bao trùm: Phép tính ngày tháng, năm nhuận 29/02, ma trận mùa vụ 3 năm, bóc tách RPC Google Ads, chống rò rỉ token và an toàn SQLite.*

### 2. Chạy Frontend Stress Test Suite (SSR & Timeline Component)
```bash
node tests/test_frontend_stress.mjs
```
*Kiểm thử 23 bài test căng thẳng: Date math, fallback dữ liệu thiếu, render ma trận 12 tháng, nhãn phân loại Evergreen/Seasonal/New Test.*

### 3. Kiểm Tra Đóng Gói Frontend Production Build
```bash
cd frontend
npm run build
```
*Biên dịch kiểm tra TypeScript (`tsc -b`) và đóng gói tài nguyên tối ưu với Vite.*

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Architecture)

```
goaffpro-crawler/
├── backend/
│   ├── api.py                    # FastAPI server: REST endpoints, bộ lọc, CRM, xuất file & điều khiển worker
│   ├── categorizer.py            # Phân loại ngành hàng NLP, bóc tách từ khóa & SafeFilter 18+
│   ├── crawler.py                # Playwright bot cào danh sách GoAffPro Store tự động
│   ├── db.py                     # Quản lý SQLite database, migration, lập chỉ mục tốc độ cao
│   ├── spy_ads.py                # Core engine: Google Ads Transparency API & DOM scraper, bóc tách Ads All-Time
│   ├── spy_ads_worker.py         # Worker chạy nền cào Google Ads theo lô với Chrome profile độc lập
│   ├── traffic_worker.py         # Worker chạy nền bóc tách Google Trends & Tranco Zipf ranking
│   ├── traffic_cv_scraper.py     # Playwright bóc tách dữ liệu Similarweb từ Traffic.cv
│   └── traffic_cv_worker.py      # Background worker quản lý luồng vượt Cloudflare Turnstile 3 lớp
├── data/
│   ├── goaffpro.db               # Cơ sở dữ liệu SQLite chính (~8.400+ store đã làm giàu dữ liệu)
│   ├── spy_google_ads_*.json     # Bộ đệm kết quả Google Ads của các store
│   └── schema.sql                # Bản sao lưu cấu trúc database hoàn chỉnh
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Giao diện chính: Bộ lọc đa năng, bảng dữ liệu, xuất Excel/CSV
│   │   ├── SpyGoogleAdsTab.tsx   # Tab quản trị & kiểm tra Ads Spy toàn bộ hệ thống
│   │   ├── StoreAccordionSpyView.tsx # Accordion mở rộng chi tiết mẫu ads & ma trận mùa vụ từng store
│   │   ├── Campaign12MonthTimeline.tsx # Thành phần Ma trận mùa vụ 3 năm (2024-2026) & chu kỳ 12 tháng
│   │   ├── SeasonalityChart3Year.tsx   # Biểu đồ xu hướng Google Trends 3 năm tương tác
│   │   ├── main.tsx              # Entry point ứng dụng React 19
│   │   └── index.css             # Tailwind CSS styling
│   ├── package.json              # Khai báo dependencies Frontend
│   └── vite.config.ts            # Cấu hình bundler Vite
├── tests/
│   ├── test_spy_google_ads_e2e.py # 4-Tier E2E test suite kiểm thử toàn diện Google Ads Spy
│   ├── test_challenger_m1_stress.py # Adversarial stress test ngày tháng, năm nhuận & phân loại
│   └── test_frontend_stress.mjs   # Test suite kiểm tra render UI và SSR component timeline
├── scripts/
│   ├── merge_db.py               # Hỗ trợ gộp dữ liệu từ các máy khác vào DB chính an toàn
│   └── scrape_full_google_ads.py # Script dòng lệnh độc lập cào Google Ads theo danh sách domain
├── .env.example                  # Mẫu file cấu hình môi trường
├── .gitignore                    # Bộ lọc file rác, profile chrome cá nhân và cache
├── requirements.txt              # Danh sách thư viện Python chuẩn hóa
├── start_app.sh                  # Script khởi động tự động 1-click cho macOS / Linux
├── start_app.bat                 # Script khởi động tự động 1-click cho Windows
├── TEST_INFRA.md                 # Tài liệu chi tiết kiến trúc kiểm thử
└── README.md                     # Tài liệu hướng dẫn sử dụng này
```

---

## 🔒 An Toàn Dữ Liệu & Quy Chuẩn Repository

* **Tuyệt Đối Không Rò Rỉ Bí Mật (Zero Secret Leakage):** Không lưu mật khẩu, API key hay GitHub Personal Access Token trong mã nguồn.
* **Cách Ly Profile Trình Duyệt:** Thư mục lưu trữ phiên làm việc của Chrome (`data/chrome_profile_*`, `data/browser_profile`) được cấu hình trong `.gitignore`, không đưa lên repository để đảm bảo an toàn tuyệt đối.
* **Bảo Vệ Tính Toàn Vẹn Cơ Sở Dữ Liệu:** Cơ sở dữ liệu SQLite sử dụng WAL mode (`Write-Ahead Logging`) chống lỗi phân mảnh dữ liệu khi nhiều tiến trình cùng truy cập.

---

## 🤝 Hỗ Trợ & Đóng Góp

Nếu có bất kỳ thắc mắc, lỗi phát sinh hoặc ý tưởng nâng cấp, vui lòng mở một Issue trên GitHub hoặc liên hệ trực tiếp để được hỗ trợ nhanh nhất.
