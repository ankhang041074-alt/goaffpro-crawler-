# 🎯 GoAffPro Store Hunter & Affiliate CRM

Ứng dụng nội bộ (Local Web App) chuyên dụng để cào tự động hàng nghìn cửa hàng (stores) trên nền tảng **GoAffPro Marketplace**, bóc tách tỷ lệ hoa hồng, thời hạn cookie, ngành hàng, và hỗ trợ xuất file Excel lọc tìm kiếm đối tác Shopify Affiliate tiềm năng.

---

## 🚀 Tính Năng Chính

1. **🔑 Đăng Nhập & Giữ Phiên Tự Động (Persistent Browser Session)**:
   - Bấm nút `Mở Trình Duyệt Login` để tự mở Chrome thật.
   - Bạn đăng nhập tài khoản GoAffPro và giải captcha thoải mái. Cookie được lưu vĩnh viễn trong thư mục `data/browser_profile`. Lần sau mở app là tự động sẵn sàng cào mà không cần login lại.
2. **⚡ Bắt Gói Dữ Liệu Tự Động & Lật Trang Thông Minh (API Interception + DOM Scraper)**:
   - Tự động bắt trực tiếp các gói API JSON từ GoAffPro khi lật trang, giúp tốc độ cào nhanh gấp 10 lần so với đọc HTML thông thường.
   - Cơ chế tự lật trang (Pagination) mượt mà đến 30 - 50 trang tùy chọn.
3. **📊 Dashboard Quản Lý Như Tool TikTok Analyzer**:
   - Thống kê tổng số store, hoa hồng cao nhất, hoa hồng trung bình, số store đã gắn sao theo dõi.
   - Tìm kiếm theo tên store, website, ngành hàng.
   - Lọc nhanh theo mức hoa hồng: $\ge 10\%$, $\ge 15\%$, $\ge 20\%$, $\ge 30\%$.
4. **📥 Xuất Dữ Liệu 1-Chạm (Excel & CSV)**:
   - Xuất file `.xlsx` hoặc `.csv` tức thì với đầy đủ cột Tên, Website, % Hoa hồng, Cookie, Ngành hàng, Ghi chú.
5. **⭐ Quản Lý Trạng Thái & Ghi Chú Riêng (Affiliate CRM)**:
   - Gắn sao yêu thích, ghi chú riêng cho từng store (ví dụ: *Đã gửi email xin sample*, *Chờ duyệt*, *Hoa hồng thương lượng thêm*).
   - Dữ liệu lưu trong SQLite nội bộ (`data/goaffpro.db`), không bao giờ bị mất hoặc đứt kết nối như AppSheet.

---

## 🛠️ Hướng Dẫn Chạy App

Chỉ cần mở Terminal tại thư mục này và chạy:

```bash
./start_app.sh
```

Hệ thống sẽ tự động:
- Khởi động Backend FastAPI tại: `http://localhost:8001`
- Khởi động Frontend Dashboard tại: `http://localhost:5174`
- Tự mở trình duyệt lên cho bạn sử dụng ngay lập tức!
