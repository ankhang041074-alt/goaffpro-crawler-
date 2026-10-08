CREATE TABLE stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        website_url TEXT DEFAULT '',
        portal_url TEXT DEFAULT '',
        logo_url TEXT DEFAULT '',
        commission_rate TEXT DEFAULT '',
        commission_value REAL DEFAULT 0.0,
        cookie_days INTEGER DEFAULT 30,
        category TEXT DEFAULT 'General',
        description TEXT DEFAULT '',
        instant_access INTEGER DEFAULT 1,
        status TEXT DEFAULT 'available',
        is_favorite INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    , currency TEXT DEFAULT 'USD', traffic_visits TEXT DEFAULT '', traffic_raw_value INTEGER DEFAULT 0, traffic_status TEXT DEFAULT 'pending', traffic_top_country TEXT DEFAULT '', trend_timeline_json TEXT DEFAULT '', trend_peak_month TEXT DEFAULT '', trend_status TEXT DEFAULT 'pending', traffic_updated_at DATETIME DEFAULT NULL, categories_json TEXT DEFAULT '[]', site_title TEXT DEFAULT '', site_description TEXT DEFAULT '', is_adult INTEGER DEFAULT 0, trend_is_steady INTEGER DEFAULT 0, traffic_source TEXT DEFAULT '', traffic_bounce_rate TEXT DEFAULT '', traffic_avg_duration TEXT DEFAULT '', traffic_global_rank INTEGER DEFAULT 0, traffic_country_rank INTEGER DEFAULT 0, traffic_pages_per_visit TEXT DEFAULT '');
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE crawl_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'pending',
        current_page INTEGER DEFAULT 0,
        total_pages INTEGER DEFAULT 0,
        total_stores INTEGER DEFAULT 0,
        new_stores INTEGER DEFAULT 0,
        message TEXT DEFAULT '',
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
CREATE INDEX idx_stores_name ON stores(name);
CREATE INDEX idx_stores_category ON stores(category);
CREATE INDEX idx_stores_commission ON stores(commission_value);
CREATE INDEX idx_stores_favorite ON stores(is_favorite);
CREATE INDEX idx_stores_currency ON stores(currency);
CREATE INDEX idx_stores_cookie ON stores(cookie_days);
CREATE INDEX idx_stores_traffic ON stores(traffic_raw_value);
CREATE INDEX idx_stores_traffic_status ON stores(traffic_status);
CREATE INDEX idx_stores_trend_status ON stores(trend_status);
CREATE INDEX idx_stores_is_adult ON stores(is_adult);
CREATE INDEX idx_stores_trend_steady ON stores(trend_is_steady);
CREATE INDEX idx_stores_traffic_source ON stores(traffic_source);
CREATE INDEX idx_stores_traffic_global_rank ON stores(traffic_global_rank);
