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
  Building,
  Trash2,
  Megaphone,
  DollarSign,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Filter
} from 'lucide-react';

interface Store {
  id: number;
  store_id: string;
  name: string;
  website_url: string;
  portal_url: string;
  logo_url: string;
  currency: string;
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
  currencies?: { currency: string; count: number }[];
  cookie_durations?: { days: number; count: number }[];
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
  const [currencyFilter, setCurrencyFilter] = useState<string>('all');
  const [commissionFilter, setCommissionFilter] = useState<string>('all');
  const [cookieFilter, setCookieFilter] = useState<string>('all');
  const [notesFilter, setNotesFilter] = useState<string>('all');
  const [favoriteOnly, setFavoriteOnly] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>('commission_value');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;

  // Crawl State
  const [activeJob, setActiveJob] = useState<CrawlJob | null>(null);
  const [showCrawlModal, setShowCrawlModal] = useState<boolean>(false);
  const [crawlMaxPages, setCrawlMaxPages] = useState<number>(30);
  const [crawlStartUrl, setCrawlStartUrl] = useState<string>('https://goaffpro.com/login');
  const [isOpeningBrowser, setIsOpeningBrowser] = useState<boolean>(false);

  // Selected Store Modal
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [editingNote, setEditingNote] = useState<string>('');
  const [editingStatus, setEditingStatus] = useState<string>('available');

  // User Customizable Tracking (Ads & Revenue)
  const [runningAds, setRunningAds] = useState<string>(() => localStorage.getItem('running_ads') || '0');
  const [monthlyRevenue, setMonthlyRevenue] = useState<string>(() => localStorage.getItem('monthly_revenue') || '$0');

  function updateRunningAds(val: string) {
    setRunningAds(val);
    localStorage.setItem('running_ads', val);
  }

  function updateMonthlyRevenue(val: string) {
    setMonthlyRevenue(val);
    localStorage.setItem('monthly_revenue', val);
  }

  function handleSort(col: string) {
    if (sortBy === col) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setSortOrder(col === 'name' || col === 'currency' ? 'asc' : 'desc');
    }
    setPage(1);
  }

  const pollingRef = useRef<any>(null);

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchCategories();
  }, []);

  // Fetch stores on filter change
  useEffect(() => {
    fetchStores();
  }, [search, selectedCategory, currencyFilter, commissionFilter, cookieFilter, notesFilter, favoriteOnly, sortBy, sortOrder, page]);

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
        currency: currencyFilter !== 'all' ? currencyFilter : '',
        cookie_days: cookieFilter !== 'all' ? cookieFilter : '',
        min_commission: commissionFilter !== 'all' ? commissionFilter : '0',
        notes_filter: notesFilter !== 'all' ? notesFilter : '',
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
      const rawUrl = (crawlStartUrl || '').trim();
      const isInvalidStoresUrl = !rawUrl || (rawUrl.toLowerCase().includes('goaffpro.com/stores') && !rawUrl.toLowerCase().includes('affiliate'));
      const sanitizedUrl = isInvalidStoresUrl
        ? 'https://goaffpro.com/login'
        : rawUrl;
      const res = await fetch('/api/crawl/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_pages: crawlMaxPages,
          start_url: sanitizedUrl
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

  async function handleDeleteStore(storeId: string, storeName?: string) {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa cửa hàng "${storeName || storeId}" khỏi danh sách?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/stores/${encodeURIComponent(storeId)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setStores(prev => prev.filter(s => s.store_id !== storeId));
        setTotalCount(prev => Math.max(0, prev - 1));
        if (selectedStore?.store_id === storeId) {
          setSelectedStore(null);
        }
        fetchStats();
      }
    } catch (err) {
      alert('Lỗi xóa cửa hàng: ' + err);
    }
  }

  async function handleDeleteByCurrency(currency: string) {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa TẤT CẢ các dự án tiền ${currency} (Ấn Độ)? Thao tác này không thể hoàn tác!`)) {
      return;
    }
    try {
      const res = await fetch(`/api/stores/currency/${encodeURIComponent(currency)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        const json = await res.json();
        alert(`Đã xóa thành công ${json.deleted_count} cửa hàng tiền ${currency}!`);
        fetchStores();
        fetchStats();
      }
    } catch (err) {
      alert('Lỗi xóa dự án theo tiền tệ: ' + err);
    }
  }

  function handleExport(format: 'excel' | 'csv') {
    const params = new URLSearchParams({
      search: search.trim(),
      category: selectedCategory,
      currency: currencyFilter !== 'all' ? currencyFilter : '',
      cookie_days: cookieFilter !== 'all' ? cookieFilter : '',
      min_commission: commissionFilter !== 'all' ? commissionFilter : '0',
      notes_filter: notesFilter !== 'all' ? notesFilter : '',
      favorite_only: favoriteOnly ? 'true' : 'false'
    });
    window.open(`/api/export/${format}?${params.toString()}`, '_blank');
  }

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-100 flex flex-col font-sans">
      {/* HEADER */}
      <header className="border-b border-slate-200 bg-slate-50/90 backdrop-blur-md sticky top-0 z-40 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Layers className="text-slate-900 w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
                <span>GoAffPro Store Hunter</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700">
                  Affiliate CRM
                </span>
              </h1>
              <p className="text-xs text-slate-500">
                Cào danh sách cửa hàng tự động & quản lý chương trình Affiliate Shopify
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={handleOpenLoginBrowser}
              disabled={isOpeningBrowser}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-200 hover:bg-slate-700 text-slate-700 border border-slate-300 hover:border-slate-600 transition cursor-pointer shadow-sm"
              title="Mở trình duyệt Chromium để đăng nhập tài khoản GoAffPro và lưu cookie vĩnh viễn"
            >
              <Key size={14} className="text-amber-400" />
              <span>{isOpeningBrowser ? 'Đang mở...' : 'Mở Trình Duyệt Login'}</span>
            </button>

            <button
              onClick={() => setShowCrawlModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-slate-900 shadow-lg shadow-indigo-600/25 transition cursor-pointer"
            >
              <Play size={14} fill="currentColor" />
              <span>Cào Dữ Liệu Mới</span>
            </button>

            <div className="h-5 w-px bg-slate-200 mx-1 hidden sm:block" />

            <button
              onClick={() => handleExport('excel')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 transition cursor-pointer"
              title="Xuất danh sách ra file Excel .xlsx"
            >
              <FileSpreadsheet size={14} />
              <span>Xuất Excel</span>
            </button>

            <button
              onClick={() => handleDeleteByCurrency('INR')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 transition cursor-pointer"
              title="Xóa tất cả các dự án tiền Ấn Độ (INR)"
            >
              <Trash2 size={13} />
              <span>Xóa Tiền INR</span>
            </button>

            <button
              onClick={() => {
                fetchStats();
                fetchStores();
              }}
              className="p-2 rounded-xl bg-slate-200 hover:bg-slate-700 text-slate-500 hover:text-slate-900 transition cursor-pointer border border-slate-300"
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
              <RefreshCw className="animate-spin text-indigo-600 w-5 h-5 flex-shrink-0" />
              <div>
                <p className="text-xs font-bold text-slate-900 flex items-center gap-2">
                  <span>Tiến trình cào GoAffPro đang chạy</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300 font-mono">
                    Trang {activeJob.current_page} / {activeJob.total_pages}
                  </span>
                </p>
                <p className="text-[11px] text-indigo-200 mt-0.5">{activeJob.message}</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-sm font-black text-emerald-600 font-mono">
                +{activeJob.total_stores}
              </span>
              <span className="text-[11px] text-slate-500 block">stores thu thập</span>
            </div>
          </div>
        </div>
      )}

      {/* MAIN CONTAINER */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 flex flex-col gap-6">
        {/* STATS OVERVIEW */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Tổng Stores</span>
              <Building size={16} className="text-indigo-600" />
            </div>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {(stats?.total_stores || 0).toLocaleString()}
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Đã lưu trong database</span>
          </div>

          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm hover:border-indigo-300 transition group">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Số Ads Đang Chạy</span>
              <Megaphone size={16} className="text-indigo-600 group-hover:scale-110 transition" />
            </div>
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={runningAds}
                onChange={e => updateRunningAds(e.target.value)}
                placeholder="0"
                className="text-2xl font-black text-indigo-600 font-mono bg-transparent border-b border-dashed border-indigo-200 focus:border-indigo-500 focus:outline-none w-full py-0.5"
                title="Nhấp vào để tự điền số ads đang chạy"
              />
            </div>
            <span className="text-[11px] text-slate-400 mt-0.5 block flex items-center gap-1">
              <Edit3 size={10} /> Nhấp số để tự điền
            </span>
          </div>

          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm hover:border-emerald-300 transition group">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Doanh Thu Tháng Này</span>
              <DollarSign size={16} className="text-emerald-600 group-hover:scale-110 transition" />
            </div>
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={monthlyRevenue}
                onChange={e => updateMonthlyRevenue(e.target.value)}
                placeholder="$0"
                className="text-2xl font-black text-emerald-600 font-mono bg-transparent border-b border-dashed border-emerald-200 focus:border-emerald-500 focus:outline-none w-full py-0.5"
                title="Nhấp vào để tự điền doanh thu tháng này"
              />
            </div>
            <span className="text-[11px] text-slate-400 mt-0.5 block flex items-center gap-1">
              <Edit3 size={10} /> Nhấp số để tự điền
            </span>
          </div>

          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 mb-1">
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
        <section className="bg-white border border-slate-200 rounded-2xl p-3 shadow-sm flex flex-col gap-2.5">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search store name, website, notes..."
                value={search}
                onChange={e => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-9 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <span className="text-xs text-slate-500 font-medium px-2 whitespace-nowrap">
              Hiển thị {stores.length} / {totalCount.toLocaleString()} stores
            </span>
          </div>

          {/* Active filters bar if any filter is active */}
          {(currencyFilter !== 'all' || commissionFilter !== 'all' || cookieFilter !== 'all' || notesFilter !== 'all' || search.trim() !== '') && (
            <div className="flex items-center gap-2 pt-1 border-t border-slate-100 flex-wrap text-xs">
              <span className="text-[11px] font-semibold text-indigo-600 flex items-center gap-1">
                <Filter size={12} /> Đang lọc:
              </span>
              {currencyFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-200 font-medium">
                  Tiền: <strong>{currencyFilter}</strong>
                  <button onClick={() => { setCurrencyFilter('all'); setPage(1); }} className="hover:text-indigo-900 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {commissionFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-200 font-medium">
                  Hoa hồng ≥ <strong>{commissionFilter}%</strong>
                  <button onClick={() => { setCommissionFilter('all'); setPage(1); }} className="hover:text-indigo-900 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {cookieFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-200 font-medium">
                  Cookie: <strong>{cookieFilter} days</strong>
                  <button onClick={() => { setCookieFilter('all'); setPage(1); }} className="hover:text-indigo-900 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {notesFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-200 font-medium">
                  {notesFilter === 'has_notes' ? 'Đã có ghi chú' : 'Chưa có ghi chú'}
                  <button onClick={() => { setNotesFilter('all'); setPage(1); }} className="hover:text-indigo-900 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              <button
                onClick={() => {
                  setSearch('');
                  setCurrencyFilter('all');
                  setCommissionFilter('all');
                  setCookieFilter('all');
                  setNotesFilter('all');
                  setPage(1);
                }}
                className="text-[11px] text-rose-500 hover:text-rose-700 hover:underline font-semibold ml-auto cursor-pointer"
              >
                Xóa tất cả bộ lọc
              </button>
            </div>
          )}
        </section>

        {/* STORES TABLE */}
        <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xl flex-1 flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/90 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-3 w-12 text-center">⭐</th>
                  <th className="py-3 px-4 w-[240px]">
                    <button
                      onClick={() => handleSort('name')}
                      className="flex items-center gap-1.5 hover:text-indigo-600 transition cursor-pointer"
                    >
                      <span>Store / Website</span>
                      {sortBy === 'name' ? (
                        sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                      ) : (
                        <ArrowUpDown size={11} className="text-slate-400" />
                      )}
                    </button>
                  </th>

                  {/* CURRENCY COLUMN */}
                  <th className="py-2.5 px-3 w-32">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleSort('currency')}
                        className="flex items-center justify-between hover:text-indigo-600 transition cursor-pointer w-full"
                        title="Bấm để sắp xếp A-Z hoặc Z-A"
                      >
                        <span>Currency</span>
                        {sortBy === 'currency' ? (
                          sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                        ) : (
                          <ArrowUpDown size={11} className="text-slate-400" />
                        )}
                      </button>
                      <select
                        value={currencyFilter}
                        onChange={e => {
                          setCurrencyFilter(e.target.value);
                          setPage(1);
                        }}
                        className={`text-[11px] font-normal py-1 px-1.5 rounded-lg border focus:outline-none transition cursor-pointer ${
                          currencyFilter !== 'all'
                            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <option value="all">Tất cả tiền tệ</option>
                        {stats?.currencies?.map(c => (
                          <option key={c.currency} value={c.currency}>
                            {c.currency} ({c.count.toLocaleString()})
                          </option>
                        ))}
                      </select>
                    </div>
                  </th>

                  {/* COMMISSION COLUMN */}
                  <th className="py-2.5 px-3 w-36">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleSort('commission_value')}
                        className="flex items-center justify-between hover:text-indigo-600 transition cursor-pointer w-full"
                        title="Bấm để sắp xếp hoa hồng Cao nhất / Thấp nhất"
                      >
                        <span>Commission</span>
                        {sortBy === 'commission_value' ? (
                          sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                        ) : (
                          <ArrowUpDown size={11} className="text-slate-400" />
                        )}
                      </button>
                      <select
                        value={commissionFilter}
                        onChange={e => {
                          setCommissionFilter(e.target.value);
                          setPage(1);
                        }}
                        className={`text-[11px] font-normal py-1 px-1.5 rounded-lg border focus:outline-none transition cursor-pointer ${
                          commissionFilter !== 'all'
                            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <option value="all">Tất cả %</option>
                        <option value="10">≥ 10%</option>
                        <option value="15">≥ 15% (Chuẩn)</option>
                        <option value="20">≥ 20% (Cao)</option>
                        <option value="30">≥ 30% (Rất cao)</option>
                        <option value="50">≥ 50% (Khủng)</option>
                      </select>
                    </div>
                  </th>

                  {/* COOKIE COLUMN */}
                  <th className="py-2.5 px-3 w-36">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleSort('cookie_days')}
                        className="flex items-center justify-between hover:text-indigo-600 transition cursor-pointer w-full"
                        title="Bấm để sắp xếp ngày cookie Dài nhất / Ngắn nhất"
                      >
                        <span>Cookie</span>
                        {sortBy === 'cookie_days' ? (
                          sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                        ) : (
                          <ArrowUpDown size={11} className="text-slate-400" />
                        )}
                      </button>
                      <select
                        value={cookieFilter}
                        onChange={e => {
                          setCookieFilter(e.target.value);
                          setPage(1);
                        }}
                        className={`text-[11px] font-normal py-1 px-1.5 rounded-lg border focus:outline-none transition cursor-pointer ${
                          cookieFilter !== 'all'
                            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <option value="all">Tất cả ngày</option>
                        {stats?.cookie_durations && stats.cookie_durations.length > 0 ? (
                          stats.cookie_durations.map(c => (
                            <option key={c.days} value={c.days.toString()}>
                              {c.days} days ({c.count.toLocaleString()})
                            </option>
                          ))
                        ) : (
                          <>
                            <option value="7">7 days</option>
                            <option value="14">14 days</option>
                            <option value="30">30 days</option>
                            <option value="60">60 days</option>
                            <option value="90">90 days</option>
                            <option value="180">180 days</option>
                            <option value="365">365 days</option>
                          </>
                        )}
                      </select>
                    </div>
                  </th>

                  {/* NOTES COLUMN */}
                  <th className="py-2.5 px-4 w-44">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleSort('notes')}
                        className="flex items-center justify-between hover:text-indigo-600 transition cursor-pointer w-full"
                        title="Bấm để sắp xếp theo ghi chú"
                      >
                        <span>Notes</span>
                        {sortBy === 'notes' ? (
                          sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                        ) : (
                          <ArrowUpDown size={11} className="text-slate-400" />
                        )}
                      </button>
                      <select
                        value={notesFilter}
                        onChange={e => {
                          setNotesFilter(e.target.value);
                          setPage(1);
                        }}
                        className={`text-[11px] font-normal py-1 px-1.5 rounded-lg border focus:outline-none transition cursor-pointer ${
                          notesFilter !== 'all'
                            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <option value="all">Tất cả notes</option>
                        <option value="has_notes">Đã có ghi chú 📝</option>
                        <option value="no_notes">Chưa có ghi chú</option>
                      </select>
                    </div>
                  </th>

                  <th className="py-3 px-4 text-right w-24">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
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
                      className="hover:bg-slate-200/40 transition cursor-pointer group"
                    >
                      {/* Favorite Button */}
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={e => handleToggleFavorite(store, e)}
                          className="p-1 rounded-md hover:bg-slate-200 text-slate-500 hover:text-amber-400 transition cursor-pointer"
                        >
                          <Star
                            size={16}
                            className={store.is_favorite ? 'text-amber-400 fill-amber-400' : ''}
                          />
                        </button>
                      </td>

                      {/* Store Name & Link */}
                      <td className="py-3 px-4 max-w-[220px]">
                        <div className="flex items-center gap-2.5">
                          {store.logo_url ? (
                            <img
                              src={store.logo_url}
                              alt={store.name}
                              className="w-8 h-8 rounded-lg object-contain bg-slate-50 border border-slate-200 p-0.5 flex-shrink-0"
                              onError={e => {
                                (e.target as HTMLElement).style.display = 'none';
                              }}
                            />
                          ) : (
                            <div className="w-8 h-8 rounded-lg bg-slate-200 border border-slate-300 flex items-center justify-center font-bold text-xs text-slate-600 flex-shrink-0">
                              {store.name.slice(0, 2).toUpperCase()}
                            </div>
                          )}

                          <div className="min-w-0 max-w-[160px]">
                            <span
                              className="font-bold text-xs text-slate-900 group-hover:text-indigo-600 transition block truncate"
                              title={store.name}
                            >
                              {store.name}
                            </span>
                            {store.website_url && (
                              <a
                                href={store.website_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-[11px] text-slate-500 hover:text-indigo-500 inline-flex items-center gap-1 truncate max-w-[150px]"
                                title={store.website_url}
                              >
                                <Globe size={10} className="flex-shrink-0" />
                                <span className="truncate">{store.website_url.replace(/^https?:\/\//, '')}</span>
                                <ExternalLink size={9} className="flex-shrink-0" />
                              </a>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Currency */}
                      <td className="py-3 px-3 w-28">
                        <span className="text-slate-700 font-mono text-xs font-semibold">
                          {store.currency || 'USD'}
                        </span>
                      </td>

                      {/* Commission */}
                      <td className="py-3 px-3 w-36">
                        {(() => {
                          const rawComm = (store.commission_rate || `${store.commission_value}%`).trim();
                          const isFlatCash = rawComm.includes('$') || rawComm.includes('€') || rawComm.includes('£') || rawComm.includes('₹') || (!rawComm.includes('%') && store.commission_value >= 100);
                          
                          return (
                            <span
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold font-mono border ${
                                isHighComm
                                  ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                                  : isMidComm
                                  ? 'bg-sky-50 text-sky-600 border-sky-200'
                                  : 'bg-slate-200 text-slate-700 border-slate-300'
                              }`}
                            >
                              {isFlatCash ? (
                                <>
                                  <DollarSign size={11} className="text-emerald-600 flex-shrink-0" />
                                  <span>{rawComm.replace(/^[\$]/, '')}</span>
                                </>
                              ) : (
                                <>
                                  <Percent size={11} className="flex-shrink-0" />
                                  <span>{rawComm.endsWith('%') ? rawComm : `${rawComm}%`}</span>
                                </>
                              )}
                            </span>
                          );
                        })()}
                      </td>

                      {/* Cookie Duration */}
                      <td className="py-3 px-3 w-32 whitespace-nowrap">
                        <span className="text-slate-600 inline-flex items-center gap-1 font-mono text-xs">
                          <Clock size={12} className="text-slate-500" />
                          {store.cookie_days} days
                        </span>
                      </td>

                      {/* Notes */}
                      <td className="py-3 px-4">
                        {store.notes ? (
                          <span className="text-[11px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 inline-block max-w-[280px] truncate font-medium">
                            📝 {store.notes}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">No notes</span>
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
                              className="p-1.5 rounded-lg bg-slate-200 hover:bg-slate-700 text-slate-600 hover:text-slate-900 transition cursor-pointer"
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
                            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 border border-slate-200 transition cursor-pointer"
                            title="Ghi chú & Chi tiết"
                          >
                            <Edit3 size={14} />
                          </button>
                          <button
                            onClick={e => {
                              e.stopPropagation();
                              handleDeleteStore(store.store_id, store.name);
                            }}
                            className="p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 transition cursor-pointer"
                            title="Xóa cửa hàng này"
                          >
                            <Trash2 size={14} />
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
                        <p className="text-sm font-semibold text-slate-500">Không tìm thấy store nào</p>
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
          <div className="border-t border-slate-200 px-4 py-3 flex items-center justify-between text-xs text-slate-500 bg-slate-50/60">
            <span>
              Trang <strong className="text-slate-900">{page}</strong> / {totalPages} (Tổng{' '}
              {totalCount.toLocaleString()} stores)
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg border border-slate-200 bg-slate-50 disabled:opacity-40 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 bg-slate-50 disabled:opacity-40 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
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
          <div className="bg-slate-50 border border-slate-300 rounded-3xl max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-indigo-600 text-slate-900">
                  <Play size={16} />
                </div>
                <h3 className="text-base font-bold text-slate-900">Bắt Đầu Cào Stores GoAffPro</h3>
              </div>
              <button
                onClick={() => setShowCrawlModal(false)}
                className="text-slate-500 hover:text-slate-900 text-lg p-1"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              Playwright sẽ tự động mở trang đăng nhập GoAffPro, tự động chuyển qua <strong>I am an affiliate</strong>, mở mục <strong>Stores</strong> rồi sang tab <strong>Available Stores</strong> để bóc tách dữ liệu từng trang vào hệ thống.
            </p>

            <div className="space-y-3.5 mb-5 text-xs">
              <div>
                <label className="font-semibold text-slate-600 block mb-1">
                  Đường dẫn bắt đầu cào (Target URL):
                </label>
                <input
                  type="text"
                  value={crawlStartUrl}
                  onChange={e => setCrawlStartUrl(e.target.value)}
                  placeholder="https://goaffpro.com/login"
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-700 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-600 block mb-1">
                  Số trang tối đa cần cào:
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={crawlMaxPages}
                    onChange={e => setCrawlMaxPages(Number(e.target.value))}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-700 font-mono focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setCrawlMaxPages(300)}
                    className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-200 hover:bg-slate-300 text-slate-700 whitespace-nowrap cursor-pointer"
                  >
                    Cào Sạch (300 trang)
                  </button>
                </div>
                <span className="text-[11px] text-slate-500 block mt-1">
                  Mỗi trang gồm 100 stores. Bot sẽ tự động dừng khi đến trang cuối cùng.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowCrawlModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-200 hover:bg-slate-700 text-slate-600 cursor-pointer"
              >
                Hủy
              </button>
              <button
                onClick={handleStartCrawl}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 text-slate-900 cursor-pointer shadow-lg shadow-indigo-600/30"
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
          <div className="bg-slate-50 border border-slate-300 rounded-3xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
              <div className="flex items-center gap-3">
                {selectedStore.logo_url && (
                  <img
                    src={selectedStore.logo_url}
                    alt={selectedStore.name}
                    className="w-10 h-10 rounded-xl object-contain bg-slate-50 border border-slate-200 p-1"
                  />
                )}
                <div>
                  <h3 className="text-base font-bold text-slate-900">{selectedStore.name}</h3>
                  <span className="text-[11px] text-slate-500">{selectedStore.category}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedStore(null)}
                className="text-slate-500 hover:text-slate-900 text-lg p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 mb-6 text-xs">
              <div className="grid grid-cols-3 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-500 block mb-0.5">Tiền tệ:</span>
                  <span className="text-sm font-bold text-slate-600 font-mono">
                    {selectedStore.currency || 'USD'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Tỷ lệ hoa hồng:</span>
                  <span className="text-sm font-bold text-emerald-600 font-mono">
                    {selectedStore.commission_rate || `${selectedStore.commission_value}%`}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Thời hạn Cookie:</span>
                  <span className="text-sm font-bold text-slate-900 font-mono">
                    {selectedStore.cookie_days} ngày
                  </span>
                </div>
              </div>

              {selectedStore.description && (
                <div>
                  <span className="font-semibold text-slate-600 block mb-1">Mô tả cửa hàng:</span>
                  <p className="text-slate-500 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-200">
                    {selectedStore.description}
                  </p>
                </div>
              )}

              <div>
                <label className="font-semibold text-slate-600 block mb-1">
                  Trạng thái liên hệ / Hợp tác:
                </label>
                <select
                  value={editingStatus}
                  onChange={e => setEditingStatus(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-500"
                >
                  <option value="available">Mới tìm thấy (Available)</option>
                  <option value="applied">Đã gửi đơn đăng ký (Applied)</option>
                  <option value="joined">Đã được duyệt & Có link (Joined)</option>
                  <option value="promoted">Đang chạy quảng cáo / đẩy số (Promoting)</option>
                  <option value="ignored">Bỏ qua (Ignored)</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-600 block mb-1">
                  Ghi chú riêng của bạn (Notes):
                </label>
                <textarea
                  rows={3}
                  value={editingNote}
                  onChange={e => setEditingNote(e.target.value)}
                  placeholder="Ví dụ: Cần xin mẫu sản phẩm, liên hệ qua email support@... hoặc hoa hồng thương lượng thêm..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-200">
              <button
                onClick={() => handleDeleteStore(selectedStore.store_id, selectedStore.name)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 cursor-pointer inline-flex items-center gap-1.5 transition"
                title="Xóa cửa hàng này khỏi cơ sở dữ liệu"
              >
                <Trash2 size={13} />
                <span>Xóa Cửa Hàng</span>
              </button>

              <div className="flex items-center gap-2">
                {selectedStore.website_url && (
                  <a
                    href={selectedStore.website_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1 mr-2"
                  >
                    <Globe size={13} /> Trang chủ <ExternalLink size={11} />
                  </a>
                )}
                <button
                  onClick={() => setSelectedStore(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 cursor-pointer"
                >
                  Đóng
                </button>
                <button
                  onClick={handleSaveNote}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer shadow-sm transition"
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
