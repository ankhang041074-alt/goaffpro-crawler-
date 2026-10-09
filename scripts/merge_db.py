#!/usr/bin/env python3
"""
scripts/merge_db.py

Script an toàn để gộp dữ liệu từ một file database khác (ví dụ: máy ở nhà) vào database chính (data/goaffpro.db).
Nguyên tắc:
- Không bao giờ xóa dữ liệu hiện có.
- Nếu ở file phụ có data (Traffic, Similarweb, Google Trends, Notes, Favorites) mà DB chính chưa có thì tự động cập nhật vào.
- Nếu ở file phụ có store mới mà DB chính chưa có thì INSERT thêm vào.

Cách dùng:
    python scripts/merge_db.py /path/to/home_backup.db
"""

import sys
import os
import sqlite3
import shutil
from datetime import datetime

MAIN_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "goaffpro.db")

def merge_databases(source_db_path: str, target_db_path: str = MAIN_DB_PATH):
    if not os.path.isfile(source_db_path):
        print(f"❌ Lỗi: Không tìm thấy file source database tại: {source_db_path}")
        sys.exit(1)

    if not os.path.isfile(target_db_path):
        print(f"❌ Lỗi: Không tìm thấy target database tại: {target_db_path}")
        sys.exit(1)

    # 1. Tạo backup an toàn cho target DB trước khi merge
    backup_path = f"{target_db_path}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(target_db_path, backup_path)
    print(f"🛡️ Đã tạo bản backup an toàn tại: {backup_path}")

    src_conn = sqlite3.connect(source_db_path)
    src_conn.row_factory = sqlite3.Row
    src_cursor = src_conn.cursor()

    tgt_conn = sqlite3.connect(target_db_path)
    tgt_conn.row_factory = sqlite3.Row
    tgt_cursor = tgt_conn.cursor()

    # Lấy danh sách cột của bảng stores ở target DB
    tgt_cursor.execute("PRAGMA table_info(stores)")
    tgt_columns = {col["name"] for col in tgt_cursor.fetchall()}

    src_cursor.execute("SELECT * FROM stores")
    src_stores = src_cursor.fetchall()
    print(f"📊 Đang kiểm tra {len(src_stores)} stores từ source DB...")

    updated_traffic_count = 0
    updated_trends_count = 0
    updated_notes_count = 0
    inserted_count = 0

    for s in src_stores:
        s_dict = dict(s)
        sid = s_dict.get("store_id")
        if not sid:
            continue

        tgt_cursor.execute("SELECT * FROM stores WHERE store_id = ?", (sid,))
        tgt_row = tgt_cursor.fetchone()

        if tgt_row is None:
            # Store mới hoàn toàn -> Insert
            valid_keys = [k for k in s_dict.keys() if k in tgt_columns and k != "id"]
            cols = ", ".join(valid_keys)
            placeholders = ", ".join(["?"] * len(valid_keys))
            vals = [s_dict[k] for k in valid_keys]
            sql = f"INSERT INTO stores ({cols}) VALUES ({placeholders})"
            tgt_cursor.execute(sql, vals)
            inserted_count += 1
        else:
            tgt_dict = dict(tgt_row)
            updates = []
            params = []

            # 1. Merge Traffic nếu source có dữ liệu thành công mà target chưa có
            src_tr_status = s_dict.get("traffic_status")
            tgt_tr_status = tgt_dict.get("traffic_status")
            if src_tr_status == "success" and tgt_tr_status != "success":
                for col in ["traffic_visits", "traffic_raw_value", "traffic_status", "traffic_top_country",
                            "traffic_source", "traffic_bounce_rate", "traffic_avg_duration",
                            "traffic_global_rank", "traffic_country_rank", "traffic_pages_per_visit", "traffic_updated_at"]:
                    if col in tgt_columns and col in s_dict:
                        updates.append(f"{col} = ?")
                        params.append(s_dict[col])
                updated_traffic_count += 1

            # 2. Merge Google Trends nếu source có dữ liệu thành công mà target chưa có
            src_trend_status = s_dict.get("trend_status")
            tgt_trend_status = tgt_dict.get("trend_status")
            if src_trend_status == "success" and tgt_trend_status != "success":
                for col in ["trend_timeline_json", "trend_peak_month", "trend_status", "trend_is_steady"]:
                    if col in tgt_columns and col in s_dict:
                        updates.append(f"{col} = ?")
                        params.append(s_dict[col])
                updated_trends_count += 1

            # 3. Merge Notes & Favorites
            if s_dict.get("notes") and not tgt_dict.get("notes"):
                updates.append("notes = ?")
                params.append(s_dict["notes"])
                updated_notes_count += 1
            if s_dict.get("is_favorite") and not tgt_dict.get("is_favorite"):
                updates.append("is_favorite = ?")
                params.append(s_dict["is_favorite"])

            if updates:
                params.append(sid)
                sql = f"UPDATE stores SET {', '.join(updates)} WHERE store_id = ?"
                tgt_cursor.execute(sql, params)

    tgt_conn.commit()
    src_conn.close()
    tgt_conn.close()

    print("\n✅ GỘP DỮ LIỆU HOÀN TẤT:")
    print(f" - Số stores mới được thêm (INSERT): {inserted_count}")
    print(f" - Số stores được cập nhật thêm Traffic: {updated_traffic_count}")
    print(f" - Số stores được cập nhật thêm Google Trends: {updated_trends_count}")
    print(f" - Số stores được cập nhật Notes: {updated_notes_count}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python scripts/merge_db.py <đường_dẫn_tới_file_db_ở_nhà>")
        print("Ví dụ: python scripts/merge_db.py ~/Desktop/goaffpro_home.db")
        sys.exit(1)
    merge_databases(sys.argv[1])
