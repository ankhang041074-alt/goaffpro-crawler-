import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Download,
  ExternalLink,
  Star,
  RefreshCw,
  Globe,
  SlidersHorizontal,
  Clock,
  CheckCircle2,
  AlertCircle,
  Play,
  Key,
  Layers,
  Percent,
  TrendingUp,
  FileSpreadsheet,
  X,
  Edit3,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Building
} from 'lucide-react';

interface Store {
  id: number;
  store_id: string;
  name: string;
  website_url: string;
  portal_url: string;
  logo_url: string;
  commission_rate: string;
  commission_value: number;
  cookie_days: number;
  category: string;
  description: string;
  instant_access: boolean | number;
  status: string;
  is_favorite: boolean | number;
  notes: string;
  crawled_at: string;
}

interface Stats {
  total_stores: number;
  avg_commission: number;
  max_commission: number;
  total_favorites: number;
  top_categories: { category: string; count: number }[];
}

interface CrawlJob {
  job_id: string;
  status: string;
  current_page: number;
  total_pages: number;
  total_stores: number;
  message: string;
}

export default function App() {
  const [stores, setStores] = useState<Store[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters & Pagination
  const [search, setSearch] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [minCommission, setMinCommission] = useState<number>(0);
  const [favoriteOnly, setFavoriteOnly] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>('commission_value');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;

  // Crawl State
  const [activeJob, setActiveJob] = useState<CrawlJob | null>(null);
  const [showCrawlModal, setShowCrawlModal] = useState<boolean>(false);
  const [crawlMaxPages, setCrawlMaxPages] = useState<number>(30);
  const [crawlStartUrl, setCrawlStartUrl] = useState<string>('https://goaffpro.com/stores');
  const [isOpeningBrowser, setIsOpeningBrowser] = useState<boolean>(false);

  // Selected Store Modal
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [editingNote, setEditingNote] = useState<string>('');
  const [editingStatus, setEditingStatus] = useState<string>('available');

  const pollingRef = useRef<any>(null);

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchCategories();
  }, []);

  // Fetch stores on filter change
  useEffect(() => {
    fetchStores();
  }, [search, selectedCategory, minCommission, favoriteOnly, sortBy, sortOrder, page]);

  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const json = await res.json();
        setStats(json);
      }
    } catch (e) {
      console.error('Error fetching stats:', e);
    }
  }

  async function fetchCategories() {
    try {
      const res = await fetch('/api/categories');
      if (res.ok) {
        const json = await res.json();
        setCategories(json.categories || []);
      }
    } catch (e) {
      console.error('Error fetching categories:', e);
    }
  }

  async function fetchStores() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        search: search.trim(),
        category: selectedCategory,
        min_commission: minCommission.toString(),
        favorite_only: favoriteOnly ? 'true' : 'false',
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: pageSize.toString(),
        offset: ((page - 1) * pageSize).toString()
      });

      const res = await fetch(`/api/stores?${params.toString()}`);
      if (res.ok) {
        const json = await res.json();
        setStores(json.stores || []);
        setTotalCount(json.total || 0);
      }
    } catch (e) {
      console.error('Error fetching stores:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenLoginBrowser() {
    setIsOpeningBrowser(true);
    try {
      const res = await fetch('/api/browser/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://goaffpro.com/login' })
      });
      if (res.ok) {
        alert('Cửa sổ trình duyệt Chromium đã được mở! Bạn hãy đăng nhập tài khoản GoAffPro, vào mục Stores / Available Stores rồi bắt đầu cào.');
      }
    } catch (e) {
      alert('Không thể mở trình duyệt: ' + e);
    } finally {
      setIsOpeningBrowser(false);
    }
  }

  async function handleStartCrawl() {
    setShowCrawlModal(false);
    try {
      const res = await fetch('/api/crawl/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_pages: crawlMaxPages,
          start_url: crawlStartUrl.trim()
        })
      });
      if (res.ok) {
        const json = await res.json();
        setActiveJob({
          job_id: json.job_id,
          status: 'running',
          current_page: 1,
          total_pages: crawlMaxPages,
          total_stores: 0,
          message: 'Đang khởi động cào dữ liệu...'
        });

        if (pollingRef.current) clearInterval(pollingRef.current);
        pollingRef.current = setInterval(() => pollJob(json.job_id), 2500);
      }
    } catch (e) {
      alert('Lỗi khi kích hoạt cào: ' + e);
    }
  }

  async function pollJob(jobId: string) {
    try {
      const res = await fetch(`/api/crawl/job/${jobId}`);
      if (res.ok) {
        const job: CrawlJob = await res.json();
        setActiveJob(job);
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(pollingRef.current);
          fetchStats();
          fetchStores();
        }
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }

  async function handleToggleFavorite(store: Store, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/stores/${encodeURIComponent(store.store_id)}/favorite`, {
        method: 'POST'
      });
      if (res.ok) {
        const json = await res.json();
        setStores(prev =>
          prev.map(s => (s.store_id === store.store_id ? { ...s, is_favorite: json.is_favorite } : s))
        );
        fetchStats();
      }
    } catch (err) {
      console.error('Toggle favorite error:', err);
    }
  }

  async function handleSaveNote() {
    if (!selectedStore) return;
    try {
      const res = await fetch(`/api/stores/${encodeURIComponent(selectedStore.store_id)}/note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note: editingNote,
          status: editingStatus
        })
      });
      if (res.ok) {
        setStores(prev =>
          prev.map(s =>
            s.store_id === selectedStore.store_id
              ? { ...s, notes: editingNote, status: editingStatus }
              : s
          )
        );
        setSelectedStore(null);
      }
    } catch (err) {
      alert('Lỗi lưu ghi chú: ' + err);
    }
  }

  function handleExport(format: 'excel' | 'csv') {
    const params = new URLSearchParams({
      search: search.trim(),
      category: selectedCategory,
      min_commission: minCommission.toString(),
      favorite_only: favoriteOnly ? 'true' : 'false'
    });
    window.open(`/api/export/${format}?${params.toString()}`, '_blank');
  }

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* HEADER */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-40 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Layers className="text-white w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                <span>GoAffPro Store Hunter</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700">
                  Affiliate CRM
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Cào danh sách cửa hàng tự động & quản lý chương trình Affiliate Shopify
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={handleOpenLoginBrowser}
              disabled={isOpeningBrowser}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 transition cursor-pointer shadow-sm"
              title="Mở trình duyệt Chromium để đăng nhập tài khoản GoAffPro và lưu cookie vĩnh viễn"
            >
              <Key size={14} className="text-amber-400" />
              <span>{isOpeningBrowser ? 'Đang mở...' : 'Mở Trình Duyệt Login'}</span>
            </button>

            <button
              onClick={() => setShowCrawlModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-600/25 transition cursor-pointer"
            >
              <Play size={14} fill="currentColor" />
              <span>Cào Dữ Liệu Mới</span>
            </button>

            <div className="h-5 w-px bg-slate-800 mx-1 hidden sm:block" />

            <button
              onClick={() => handleExport('excel')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 transition cursor-pointer"
              title="Xuất danh sách ra file Excel .xlsx"
            >
              <FileSpreadsheet size={14} />
              <span>Xuất Excel</span>
            </button>

            <button
              onClick={() => {
                fetchStats();
                fetchStores();
              }}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition cursor-pointer border border-slate-700"
              title="Làm mới dữ liệu"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      {/* ACTIVE CRAWLER BANNER */}
      {activeJob && (activeJob.status === 'running' || activeJob.status === 'waiting_login') && (
        <div className="bg-indigo-950/60 border-b border-indigo-800/80 px-6 py-3 animate-in fade-in duration-300">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <RefreshCw className="animate-spin text-indigo-400 w-5 h-5 flex-shrink-0" />
              <div>
                <p className="text-xs font-bold text-white flex items-center gap-2">
                  <span>Tiến trình cào GoAffPro đang chạy</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300 font-mono">
                    Trang {activeJob.current_page} / {activeJob.total_pages}
                  </span>
                </p>
                <p className="text-[11px] text-indigo-200 mt-0.5">{activeJob.message}</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-sm font-black text-emerald-400 font-mono">
                +{activeJob.total_stores}
              </span>
              <span className="text-[11px] text-slate-400 block">stores thu thập</span>
            </div>
          </div>
        </div>
      )}

      {/* MAIN CONTAINER */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 flex flex-col gap-6">
        {/* STATS OVERVIEW */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Tổng Stores</span>
              <Building size={16} className="text-indigo-400" />
            </div>
            <div className="text-2xl font-black text-white font-mono">
              {(stats?.total_stores || 0).toLocaleString()}
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Đã lưu trong database</span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Hoa Hồng Cao Nhất</span>
              <Percent size={16} className="text-emerald-400" />
            </div>
            <div className="text-2xl font-black text-emerald-400 font-mono">
              {stats?.max_commission || 0}%
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Cơ hội lợi nhuận cao</span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Hoa Hồng Trung Bình</span>
              <TrendingUp size={16} className="text-sky-400" />
            </div>
            <div className="text-2xl font-black text-sky-400 font-mono">
              {stats?.avg_commission || 0}%
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Mức chiết khấu phổ biến</span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Stores Yêu Thích</span>
              <Star size={16} className="text-amber-400 fill-amber-400/30" />
            </div>
            <div className="text-2xl font-black text-amber-300 font-mono">
              {stats?.total_favorites || 0}
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Đã gắn sao theo dõi</span>
          </div>
        </section>

        {/* SEARCH & FILTERS BAR */}
        <section className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[240px]">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm theo tên store, website, ngành hàng, mô tả..."
                value={search}
                onChange={e => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Category Dropdown */}
            <select
              value={selectedCategory}
              onChange={e => {
                setSelectedCategory(e.target.value);
                setPage(1);
              }}
              className="bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value="all">Tất cả ngành hàng</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>

            {/* Sort Dropdown */}
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={e => {
                const [sb, so] = e.target.value.split('-');
                setSortBy(sb);
                setSortOrder(so);
                setPage(1);
              }}
              className="bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value="commission_value-desc">Hoa hồng cao nhất</option>
              <option value="commission_value-asc">Hoa hồng thấp nhất</option>
              <option value="name-asc">Tên thương hiệu A - Z</option>
              <option value="cookie_days-desc">Thời hạn Cookie dài nhất</option>
              <option value="crawled_at-desc">Mới cào gần đây</option>
            </select>

            {/* Starred Only Toggle */}
            <button
              onClick={() => {
                setFavoriteOnly(!favoriteOnly);
                setPage(1);
              }}
              className={`flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition cursor-pointer border ${
                favoriteOnly
                  ? 'bg-amber-950/80 text-amber-300 border-amber-700'
                  : 'bg-slate-950 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <Star size={13} className={favoriteOnly ? 'fill-amber-400' : ''} />
              <span>Chỉ xem Đã Lưu</span>
            </button>
          </div>

          {/* Quick Commission Filter Chips */}
          <div className="flex items-center gap-2 flex-wrap pt-1 border-t border-slate-800/60 text-xs">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <SlidersHorizontal size={12} /> Hoa hồng:
            </span>
            {[
              { label: 'Tất cả', val: 0 },
              { label: '≥ 10%', val: 10 },
              { label: '≥ 15%', val: 15 },
              { label: '≥ 20%', val: 20 },
              { label: '≥ 30%', val: 30 }
            ].map(chip => (
              <button
                key={chip.val}
                onClick={() => {
                  setMinCommission(chip.val);
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
                  minCommission === chip.val
                    ? 'bg-indigo-600 text-white font-bold'
                    : 'bg-slate-800/80 hover:bg-slate-800 text-slate-300'
                }`}
              >
                {chip.label}
              </button>
            ))}

            <span className="ml-auto text-[11px] text-slate-500">
              Hiển thị {stores.length} / {totalCount} kết quả
            </span>
          </div>
        </section>

        {/* STORES TABLE */}
        <section className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex-1 flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3.5 px-4 w-12 text-center">⭐</th>
                  <th className="py-3.5 px-4">Tên Cửa Hàng / Website</th>
                  <th className="py-3.5 px-4">Hoa Hồng (Commission)</th>
                  <th className="py-3.5 px-4">Thời Hạn Cookie</th>
                  <th className="py-3.5 px-4">Ngành Hàng</th>
                  <th className="py-3.5 px-4">Duyệt</th>
                  <th className="py-3.5 px-4">Ghi Chú</th>
                  <th className="py-3.5 px-4 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {stores.map(store => {
                  const isHighComm = store.commission_value >= 20;
                  const isMidComm = store.commission_value >= 15;

                  return (
                    <tr
                      key={store.store_id}
                      onClick={() => {
                        setSelectedStore(store);
                        setEditingNote(store.notes || '');
                        setEditingStatus(store.status || 'available');
                      }}
                      className="hover:bg-slate-800/40 transition cursor-pointer group"
                    >
                      {/* Favorite Button */}
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={e => handleToggleFavorite(store, e)}
                          className="p-1 rounded-md hover:bg-slate-800 text-slate-500 hover:text-amber-400 transition cursor-pointer"
                        >
                          <Star
                            size={16}
                            className={store.is_favorite ? 'text-amber-400 fill-amber-400' : ''}
                          />
                        </button>
                      </td>

                      {/* Store Name & Link */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          {store.logo_url ? (
                            <img
                              src={store.logo_url}
                              alt={store.name}
                              className="w-9 h-9 rounded-xl object-contain bg-slate-950 border border-slate-800 p-1 flex-shrink-0"
                              onError={e => {
                                (e.target as HTMLElement).style.display = 'none';
                              }}
                            />
                          ) : (
                            <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300 flex-shrink-0">
                              {store.name.slice(0, 2).toUpperCase()}
                            </div>
                          )}

                          <div className="min-w-0">
                            <span className="font-bold text-sm text-white group-hover:text-indigo-400 transition block truncate">
                              {store.name}
                            </span>
                            {store.website_url && (
                              <a
                                href={store.website_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-[11px] text-slate-400 hover:text-indigo-300 inline-flex items-center gap-1 truncate max-w-[260px]"
                              >
                                <Globe size={11} />
                                <span>{store.website_url.replace(/^https?:\/\//, '')}</span>
                                <ExternalLink size={10} />
                              </a>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Commission */}
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold font-mono border ${
                            isHighComm
                              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
                              : isMidComm
                              ? 'bg-sky-950/80 text-sky-300 border-sky-700'
                              : 'bg-slate-800 text-slate-200 border-slate-700'
                          }`}
                        >
                          <Percent size={11} />
                          {store.commission_rate || `${store.commission_value}%`}
                        </span>
                      </td>

                      {/* Cookie Duration */}
                      <td className="py-3 px-4">
                        <span className="text-slate-300 inline-flex items-center gap-1 font-mono">
                          <Clock size={12} className="text-slate-400" />
                          {store.cookie_days} ngày
                        </span>
                      </td>

                      {/* Category */}
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[11px] bg-slate-800 text-slate-300 border border-slate-700">
                          {store.category || 'General'}
                        </span>
                      </td>

                      {/* Instant Access */}
                      <td className="py-3 px-4">
                        {store.instant_access ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                            <ShieldCheck size={13} /> Tự động duyệt
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400">
                            <AlertCircle size={13} /> Cần xét duyệt
                          </span>
                        )}
                      </td>

                      {/* Notes / Status */}
                      <td className="py-3 px-4 max-w-[180px] truncate">
                        {store.notes ? (
                          <span className="text-[11px] text-indigo-300 bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-800/50 block truncate">
                            📝 {store.notes}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-600 italic">Chưa có ghi chú</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
                          {store.website_url && (
                            <a
                              href={store.website_url}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer"
                              title="Xem website cửa hàng"
                            >
                              <ExternalLink size={14} />
                            </a>
                          )}
                          <button
                            onClick={() => {
                              setSelectedStore(store);
                              setEditingNote(store.notes || '');
                              setEditingStatus(store.status || 'available');
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer"
                            title="Ghi chú & Chi tiết"
                          >
                            <Edit3 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}

                {stores.length === 0 && !loading && (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-500">
                      <div className="flex flex-col items-center gap-2">
                        <Building size={32} className="text-slate-600" />
                        <p className="text-sm font-semibold text-slate-400">Không tìm thấy store nào</p>
                        <p className="text-xs text-slate-500">
                          Hãy bấm &ldquo;Cào Dữ Liệu Mới&rdquo; hoặc xóa bớt bộ lọc để hiển thị kết quả.
                        </p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* PAGINATION CONTROLS */}
          <div className="border-t border-slate-800 px-4 py-3 flex items-center justify-between text-xs text-slate-400 bg-slate-950/60">
            <span>
              Trang <strong className="text-white">{page}</strong> / {totalPages} (Tổng{' '}
              {totalCount.toLocaleString()} stores)
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 disabled:opacity-40 hover:bg-slate-800 text-slate-200 transition cursor-pointer"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 disabled:opacity-40 hover:bg-slate-800 text-slate-200 transition cursor-pointer"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* CRAWL MODAL */}
      {showCrawlModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-indigo-600 text-white">
                  <Play size={16} />
                </div>
                <h3 className="text-base font-bold text-white">Bắt Đầu Cào Stores GoAffPro</h3>
              </div>
              <button
                onClick={() => setShowCrawlModal(false)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              Playwright sẽ tự động mở trình duyệt với tài khoản bạn đã đăng nhập, vào mục Available
              Stores và bóc tách dữ liệu từng trang vào hệ thống.
            </p>

            <div className="space-y-3.5 mb-5 text-xs">
              <div>
                <label className="font-semibold text-slate-300 block mb-1">
                  Đường dẫn bắt đầu cào (Target URL):
                </label>
                <input
                  type="text"
                  value={crawlStartUrl}
                  onChange={e => setCrawlStartUrl(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-300 block mb-1">
                  Số trang tối đa cần cào:
                </label>
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={crawlMaxPages}
                  onChange={e => setCrawlMaxPages(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[11px] text-slate-500 block mt-1">
                  Mỗi trang khoảng 15 - 20 stores. Đặt 30 - 50 trang để lấy hàng trăm store tiềm năng.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowCrawlModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
              >
                Hủy
              </button>
              <button
                onClick={handleStartCrawl}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 text-white cursor-pointer shadow-lg shadow-indigo-600/30"
              >
                Khởi Chạy Ngay
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STORE DETAIL / NOTE MODAL */}
      {selectedStore && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center gap-3">
                {selectedStore.logo_url && (
                  <img
                    src={selectedStore.logo_url}
                    alt={selectedStore.name}
                    className="w-10 h-10 rounded-xl object-contain bg-slate-950 border border-slate-800 p-1"
                  />
                )}
                <div>
                  <h3 className="text-base font-bold text-white">{selectedStore.name}</h3>
                  <span className="text-[11px] text-slate-400">{selectedStore.category}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedStore(null)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 mb-6 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800">
                <div>
                  <span className="text-slate-500 block mb-0.5">Tỷ lệ hoa hồng:</span>
                  <span className="text-sm font-bold text-emerald-400 font-mono">
                    {selectedStore.commission_rate || `${selectedStore.commission_value}%`}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Thời hạn Cookie:</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {selectedStore.cookie_days} ngày
                  </span>
                </div>
              </div>

              {selectedStore.description && (
                <div>
                  <span className="font-semibold text-slate-300 block mb-1">Mô tả cửa hàng:</span>
                  <p className="text-slate-400 leading-relaxed bg-slate-950 p-3 rounded-xl border border-slate-800">
                    {selectedStore.description}
                  </p>
                </div>
              )}

              <div>
                <label className="font-semibold text-slate-300 block mb-1">
                  Trạng thái liên hệ / Hợp tác:
                </label>
                <select
                  value={editingStatus}
                  onChange={e => setEditingStatus(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="available">Mới tìm thấy (Available)</option>
                  <option value="applied">Đã gửi đơn đăng ký (Applied)</option>
                  <option value="joined">Đã được duyệt & Có link (Joined)</option>
                  <option value="promoted">Đang chạy quảng cáo / đẩy số (Promoting)</option>
                  <option value="ignored">Bỏ qua (Ignored)</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-300 block mb-1">
                  Ghi chú riêng của bạn (Notes):
                </label>
                <textarea
                  rows={3}
                  value={editingNote}
                  onChange={e => setEditingNote(e.target.value)}
                  placeholder="Ví dụ: Cần xin mẫu sản phẩm, liên hệ qua email support@... hoặc hoa hồng thương lượng thêm..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              {selectedStore.website_url ? (
                <a
                  href={selectedStore.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-indigo-400 hover:underline inline-flex items-center gap-1"
                >
                  <Globe size={13} /> Mở trang chủ thương hiệu <ExternalLink size={11} />
                </a>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedStore(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
                >
                  Đóng
                </button>
                <button
                  onClick={handleSaveNote}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer shadow-lg shadow-indigo-600/30"
                >
                  Lưu Ghi Chú
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
