# 🎯 GoAffPro Store Hunter & Affiliate CRM

Ứng dụng nội bộ (Local Web App) chuyên dụng để tự động cào sạch toàn bộ cửa hàng (stores) trên nền tảng **GoAffPro Marketplace** (đã kiểm chứng cào thành công trọn vẹn **220 trang ~ 22.000 stores**), bóc tách chuẩn xác tỷ lệ hoa hồng, thời hạn cookie, tiền tệ, và hỗ trợ xuất file Excel để tìm kiếm đối tác tiếp thị liên kết (Shopify Affiliate) tiềm năng.

---

## 🚀 Tính Năng Chính

1. **🔑 Đăng Nhập & Giữ Phiên Tự Động (Persistent Browser Session)**:
   - Bấm `Mở Trình Duyệt Login` để mở Chrome. Bạn đăng nhập tài khoản GoAffPro và giải Turnstile/Captcha một lần.
   - Phiên đăng nhập được lưu vĩnh viễn trong `data/browser_profile`. Lần sau mở app là tự động cào mà không cần đăng nhập lại.
2. **🤖 Luồng Tự Động 5 Bước Không Lỗi 404**:
   - Tự động đi qua luồng: `Login / Main` ➔ `I am an affiliate` ➔ `Stores` ➔ Chuyển tab `Available Stores` ➔ Đặt 100 kết quả/trang ➔ Cào dữ liệu.
   - Cơ chế chặn khôi phục tab cũ của Chromium, loại bỏ hoàn toàn lỗi tab 404.
3. **⚡ Bắt Gói API Ngầm Tốc Độ Cao (API Interception & DOM Scraper)**:
   - Bắt trực tiếp gói tin `/v1/public/sites` từ GoAffPro, tốc độ cào ~1.000 store / phút.
   - Thu thập trọn vẹn: Tên thương hiệu, Website, Tiền tệ (`USD`, `EUR`, `GBP`, `CAD`, `AUD`...), Hoa hồng, Thời hạn Cookie (quy đổi chuẩn sang số ngày).
4. **🔄 Cơ Chế Lọc Trùng Tuyệt Đối (UPSERT)**:
   - Sử dụng SQLite WAL Mode với khóa `store_id UNIQUE`. Cào lại từ đầu không sợ trùng lặp dữ liệu, không lo đè mất ghi chú của bạn.
5. **🗑️ Quản Lý Xóa Linh Hoạt**:
   - Xóa từng store trực tiếp trên bảng hoặc trong popup chi tiết.
   - Nút **"Xóa Tiền INR"** hỗ trợ dọn sạch 1-click toàn bộ các dự án tiền Ấn Độ khi không có nhu cầu làm.
6. **📥 Xuất File Excel (.xlsx) & CSV 1-Chạm**:
   - Xuất dữ liệu lọc ra Excel tức thì để gửi cho team hoặc lưu trữ.

---

## 💻 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 📋 Yêu cầu tiên quyết (Prerequisites)
- **Python**: Phiên bản 3.10 trở lên ([Tải Python](https://www.python.org/downloads/))
- **Node.js**: Phiên bản 18 trở lên ([Tải Node.js](https://nodejs.org/))
- **Git** (nếu cài đặt qua clone kho lưu trữ)

---

### 🍏 Dành Cho macOS & Linux

1. **Mở Terminal** và di chuyển vào thư mục dự án:
   ```bash
   cd goaffpro-crawler
   ```

2. **Cấp quyền thực thi và chạy file khởi động:**
   ```bash
   chmod +x start_app.sh
   ./start_app.sh
   ```

> **Hệ thống sẽ tự động:**
> - Khởi tạo môi trường ảo Python (`.venv`) và cài đặt thư viện cần thiết.
> - Cài đặt trình duyệt Playwright Chromium.
> - Cài đặt gói npm frontend và khởi động đồng thời Backend (Port 8001) & Frontend (Port 5174).
> - Tự động bật trình duyệt web vào trang: `http://localhost:5174`.

---

### 🪟 Dành Cho Windows

1. **Tải mã nguồn về máy** (Download ZIP hoặc Git Clone) và giải nén.
2. **Nhấp đúp chuột (Double-click)** vào file:
   ```cmd
   start_app.bat
   ```

> **Hệ thống trên Windows sẽ tự động:**
> - Tạo virtualenv `.venv` và tải các gói thư viện Python.
> - Cài đặt Chromium cho Playwright.
> - Tải `node_modules` và chạy server dev.
> - Tự động mở trình duyệt mặc định vào giao diện Dashboard `http://localhost:5174`.

---

## 🛠️ Hướng Dẫn Sử Dụng Chi Tiết

1. **Đăng nhập GoAffPro lần đầu:**
   - Trên thanh công cụ, nhấn nút **"Mở Trình Duyệt Login"**.
   - Cửa sổ trình duyệt Chromium sẽ hiện ra, bạn điền Email/Mật khẩu đăng nhập GoAffPro và tích ô xác minh Cloudflare (nếu có).
   - Đăng nhập thành công xong, bạn có thể đóng cửa sổ trình duyệt đó lại. Phiên làm việc đã được lưu vĩnh viễn trên máy của bạn.
2. **Cào dữ liệu mới:**
   - Nhấn **"Cào Dữ Liệu Mới"**.
   - Nhập số trang bạn muốn cào (mỗi trang có 100 store, ví dụ: 10 trang = 1.000 store; hoặc nhấn nút **"Cào Sạch (300 trang)"** để bot tự động lướt đến trang cuối cùng).
   - Nhấn **"Khởi Chạy Ngay"**. Tiến trình cào sẽ hiển thị trực tiếp theo thời gian thực trên thanh thông báo.
3. **Tìm kiếm & Ghi chú (CRM):**
   - Sử dụng ô tìm kiếm để tìm nhanh bất kỳ cửa hàng hoặc tên miền nào.
   - Nhấn vào một dòng cửa hàng để mở popup xem mô tả chi tiết, chỉnh sửa trạng thái hợp tác (`Available`, `Applied`, `Joined`...) và lưu ghi chú cá nhân.
4. **Xóa & Dọn dẹp:**
   - Nhấn biểu tượng thùng rác `🗑️` ở cột Actions để xóa store không mong muốn.
   - Nhấn nút **"Xóa Tiền INR"** ở thanh trên cùng để xóa hàng loạt tất cả các store sử dụng đồng Rupee Ấn Độ.
5. **Xuất Excel:**
   - Nhấn nút **"Xuất Excel"** để tải file `.xlsx` về máy tính.

---

## 📁 Cấu Trúc Dự Án

```
goaffpro-crawler/
├── backend/
│   ├── api.py           # FastAPI RESTful API server
│   ├── crawler.py       # Playwright crawler tự động 5 bước
│   └── db.py            # SQLite database manager & deduplication logic
├── data/
│   ├── goaffpro.db      # Cơ sở dữ liệu SQLite (chứa 22.000 stores)
│   └── browser_profile/ # Thư mục lưu phiên đăng nhập & cookie Playwright
├── frontend/
│   ├── src/             # Giao diện React + TypeScript + Tailwind CSS
│   ├── package.json     # Cấu hình thư viện frontend
│   └── vite.config.ts   # Cấu hình Vite bundler
├── start_app.sh         # Script khởi chạy 1-click cho Mac/Linux
├── start_app.bat        # Script khởi chạy 1-click cho Windows
├── requirements.txt     # Danh sách thư viện Python
└── README.md            # Tài liệu hướng dẫn sử dụng
```
