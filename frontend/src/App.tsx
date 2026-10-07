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
  Filter,
  ChevronDown,
  ChevronUp,
  Pause,
  Flame,
  Eye,
  Activity,
  Info,
  BarChart2,
  Tag
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
  traffic_visits?: string;
  traffic_raw_value?: number;
  traffic_status?: 'success' | 'no_data' | 'error' | 'pending';
  traffic_top_country?: string;
  trend_timeline_json?: string;
  trend_peak_month?: string;
  trend_status?: 'success' | 'no_data' | 'error' | 'pending';
  traffic_updated_at?: string;
  categories_json?: string;
  site_title?: string;
  site_description?: string;
  is_adult?: number;
}

interface TrafficWorkerStatus {
  is_running: boolean;
  is_paused: boolean;
  current_store: string;
  scanned: number;
  with_data: number;
  no_data: number;
  errors: number;
  gt_cooldown_seconds?: number;
  remaining: number;
  total_cookie_14_plus: number;
  checked_cookie_14_plus: number;
  above_10k: number;
}

interface Stats {
  total_stores: number;
  avg_commission: number;
  max_commission: number;
  total_favorites: number;
  top_categories: { category: string; count: number }[];
  categories?: { category: string; count: number }[];
  adult_count?: number;
  currencies?: { currency: string; count: number }[];
  cookie_durations?: { days: number; count: number }[];
  traffic?: {
    total_cookie_14_plus: number;
    checked_cookie_14_plus: number;
    remaining_cookie_14_plus: number;
    with_data: number;
    no_data: number;
    errors: number;
    above_10k: number;
  };
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
  const [trafficFilter, setTrafficFilter] = useState<string>('all');
  const [trendMonthFilter, setTrendMonthFilter] = useState<string>('all');
  const [trendScoreFilter, setTrendScoreFilter] = useState<string>('all');
  const [trendPeakOnly, setTrendPeakOnly] = useState<boolean>(false);
  const [trendGrowthOnly, setTrendGrowthOnly] = useState<boolean>(false);
  const [adultFilter, setAdultFilter] = useState<string>('hide');
  const [notesFilter, setNotesFilter] = useState<string>('all');
  const [favoriteOnly, setFavoriteOnly] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>('commission_value');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;

  // Traffic Worker & Accordion States
  const [expandedStoreId, setExpandedStoreId] = useState<string | null>(null);
  const [trafficWorkerStatus, setTrafficWorkerStatus] = useState<TrafficWorkerStatus | null>(null);
  const [refreshingStoreId, setRefreshingStoreId] = useState<string | null>(null);
  const [quickNoteEdit, setQuickNoteEdit] = useState<{ [id: string]: string }>({});

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
  const trafficPollingRef = useRef<any>(null);

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchCategories();
    fetchTrafficStatus();
    return () => {
      if (trafficPollingRef.current) clearInterval(trafficPollingRef.current);
    };
  }, []);

  // Fetch stores on filter change
  useEffect(() => {
    fetchStores();
  }, [
    search, selectedCategory, currencyFilter, commissionFilter, cookieFilter,
    trafficFilter, trendMonthFilter, trendScoreFilter, trendPeakOnly, trendGrowthOnly,
    adultFilter, notesFilter, favoriteOnly, sortBy, sortOrder, page
  ]);

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

  async function fetchTrafficStatus() {
    try {
      const res = await fetch('/api/traffic/status');
      if (res.ok) {
        const json: TrafficWorkerStatus = await res.json();
        setTrafficWorkerStatus(json);
        if (json.is_running && !trafficPollingRef.current) {
          trafficPollingRef.current = setInterval(fetchTrafficStatus, 3000);
        } else if (!json.is_running && trafficPollingRef.current) {
          clearInterval(trafficPollingRef.current);
          trafficPollingRef.current = null;
        }
      }
    } catch (e) {
      console.error('Error fetching traffic status:', e);
    }
  }

  async function handleStartTrafficWorker() {
    try {
      const res = await fetch('/api/traffic/start', { method: 'POST' });
      if (res.ok) {
        fetchTrafficStatus();
        if (!trafficPollingRef.current) {
          trafficPollingRef.current = setInterval(fetchTrafficStatus, 2500);
        }
      }
    } catch (e) {
      alert('Lỗi kích hoạt traffic worker: ' + e);
    }
  }

  async function handlePauseTrafficWorker() {
    try {
      await fetch('/api/traffic/pause', { method: 'POST' });
      fetchTrafficStatus();
    } catch (e) {
      console.error(e);
    }
  }

  async function handleResumeTrafficWorker() {
    try {
      await fetch('/api/traffic/resume', { method: 'POST' });
      fetchTrafficStatus();
    } catch (e) {
      console.error(e);
    }
  }

  async function handleStopTrafficWorker() {
    try {
      await fetch('/api/traffic/stop', { method: 'POST' });
      fetchTrafficStatus();
      if (trafficPollingRef.current) {
        clearInterval(trafficPollingRef.current);
        trafficPollingRef.current = null;
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function handleRefreshSingleStore(storeId: string, e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    setRefreshingStoreId(storeId);
    try {
      const res = await fetch(`/api/stores/${encodeURIComponent(storeId)}/refresh-traffic`, {
        method: 'POST'
      });
      if (res.ok) {
        const updated: Store = await res.json();
        setStores(prev => prev.map(s => s.store_id === storeId ? { ...s, ...updated } : s));
        if (selectedStore && selectedStore.store_id === storeId) {
          setSelectedStore(prev => prev ? { ...prev, ...updated } : null);
        }
        fetchStats();
        fetchTrafficStatus();
      }
    } catch (err) {
      alert('Lỗi làm mới traffic: ' + err);
    } finally {
      setRefreshingStoreId(null);
    }
  }

  async function handleSaveQuickNote(storeId: string) {
    const noteText = quickNoteEdit[storeId] ?? '';
    try {
      const res = await fetch(`/api/stores/${encodeURIComponent(storeId)}/note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: noteText })
      });
      if (res.ok) {
        setStores(prev => prev.map(s => s.store_id === storeId ? { ...s, notes: noteText } : s));
        alert('Đã lưu ghi chú thành công!');
      }
    } catch (err) {
      alert('Lỗi lưu ghi chú: ' + err);
    }
  }

  async function fetchStores() {
    setLoading(true);
    try {
      let minTrafficVal = '';
      let trafficStatusVal = '';
      if (['10000', '20000', '50000', '100000'].includes(trafficFilter)) {
        minTrafficVal = trafficFilter;
      } else if (trafficFilter === 'has_data') {
        trafficStatusVal = 'has_data';
      } else if (trafficFilter === 'no_data') {
        trafficStatusVal = 'no_data';
      }

      let trendMinScoreVal = '';
      let trendPeakOnlyVal = false;
      let trendGrowthOnlyVal = false;

      if (trendScoreFilter === 'growth') {
        trendGrowthOnlyVal = true;
      } else if (trendScoreFilter === 'peak') {
        trendPeakOnlyVal = true;
      } else if (trendScoreFilter === 'high') {
        trendMinScoreVal = '50';
      }

      const params = new URLSearchParams({
        search: search.trim(),
        category: selectedCategory,
        currency: currencyFilter !== 'all' ? currencyFilter : '',
        cookie_days: cookieFilter !== 'all' ? cookieFilter : '',
        min_commission: commissionFilter !== 'all' ? commissionFilter : '0',
        min_traffic: minTrafficVal,
        traffic_status: trafficStatusVal,
        trend_month: trendMonthFilter !== 'all' ? trendMonthFilter : '',
        trend_min_score: trendMinScoreVal,
        trend_peak_only: trendPeakOnlyVal ? 'true' : 'false',
        trend_growth_only: trendGrowthOnlyVal ? 'true' : 'false',
        adult_filter: adultFilter,
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
    if (!window.confirm(`Bạn có chắc chắn muốn xóa TẤT CẢ các dự án tiền ${currency}? Thao tác này không thể hoàn tác!`)) {
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

  async function handlePurgeIndianStores() {
    if (!window.confirm('Bạn có chắc chắn muốn quét và xóa TOÀN BỘ các store Ấn Độ / Nam Á (INR, PKR, BDT, LKR, NPR và tên miền .in)? Thao tác này không thể hoàn tác!')) {
      return;
    }
    try {
      const res = await fetch('/api/stores/purge-indian', {
        method: 'DELETE'
      });
      if (res.ok) {
        const json = await res.json();
        alert(`Đã quét và xóa thành công ${json.deleted_count} cửa hàng Ấn Độ / Nam Á!`);
        fetchStores();
        fetchStats();
      }
    } catch (err) {
      alert('Lỗi xóa store Ấn Độ: ' + err);
    }
  }

  function handleExport(format: 'excel' | 'csv') {
    let minTrafficVal = '';
    let trafficStatusVal = '';
    if (['10000', '20000', '50000', '100000'].includes(trafficFilter)) {
      minTrafficVal = trafficFilter;
    } else if (trafficFilter === 'has_data') {
      trafficStatusVal = 'has_data';
    } else if (trafficFilter === 'no_data') {
      trafficStatusVal = 'no_data';
    }

    let trendMinScoreVal = '';
    let trendPeakOnlyVal = false;
    let trendGrowthOnlyVal = false;

    if (trendScoreFilter === 'growth') {
      trendGrowthOnlyVal = true;
    } else if (trendScoreFilter === 'peak') {
      trendPeakOnlyVal = true;
    } else if (trendScoreFilter === 'high') {
      trendMinScoreVal = '50';
    }

    const params = new URLSearchParams({
      search: search.trim(),
      category: selectedCategory,
      currency: currencyFilter !== 'all' ? currencyFilter : '',
      cookie_days: cookieFilter !== 'all' ? cookieFilter : '',
      min_commission: commissionFilter !== 'all' ? commissionFilter : '0',
      min_traffic: minTrafficVal,
      traffic_status: trafficStatusVal,
      trend_month: trendMonthFilter !== 'all' ? trendMonthFilter : '',
      trend_min_score: trendMinScoreVal,
      trend_peak_only: trendPeakOnlyVal ? 'true' : 'false',
      trend_growth_only: trendGrowthOnlyVal ? 'true' : 'false',
      adult_filter: adultFilter,
      notes_filter: notesFilter !== 'all' ? notesFilter : '',
      favorite_only: favoriteOnly ? 'true' : 'false'
    });
    window.open(`/api/export/${format}?${params.toString()}`, '_blank');
  }

  function renderTrendsChart(store: Store) {
    let timeline: { month: string; value: number }[] = [];
    try {
      if (store.trend_timeline_json) {
        timeline = JSON.parse(store.trend_timeline_json);
      }
    } catch (e) {
      timeline = [];
    }

    if (store.trend_status === 'no_data' || (timeline.length === 0 && store.trend_status !== 'pending' && store.trend_status !== 'error')) {
      return (
        <div className="py-6 px-4 rounded-xl bg-slate-100/70 border border-slate-200 text-center flex flex-col items-center justify-center gap-1.5 text-slate-500">
          <Info size={18} className="text-slate-400" />
          <p className="text-xs font-semibold text-slate-600">Chưa đủ dữ liệu (Store nhỏ hoặc mới lập)</p>
          <p className="text-[11px] text-slate-400 max-w-md">
            Hệ thống tuân thủ nguyên tắc không bịa đặt số liệu. Cửa hàng này có lượng tìm kiếm dưới ngưỡng ghi nhận của Google Trends.
          </p>
        </div>
      );
    }

    if (store.trend_status === 'error') {
      return (
        <div className="py-6 px-4 rounded-xl bg-amber-50/70 border border-amber-200 text-center flex flex-col items-center justify-center gap-1.5 text-amber-700">
          <AlertCircle size={18} className="text-amber-500" />
          <p className="text-xs font-semibold">Tạm thời chưa kết nối được Google Trends (Rate Limit / Quá tải)</p>
          <p className="text-[11px] text-amber-600/80">Google Trends hạn chế tần suất yêu cầu. Vui lòng bấm &ldquo;Làm Mới Traffic&rdquo; sau ít phút để thử lại.</p>
        </div>
      );
    }

    if (timeline.length === 0) {
      return (
        <div className="py-6 px-4 rounded-xl bg-slate-100/70 border border-slate-200 text-center flex flex-col items-center justify-center gap-1.5 text-slate-500">
          <Clock size={18} className="text-slate-400" />
          <p className="text-xs font-semibold text-slate-600">Chưa có dữ liệu xu hướng tìm kiếm</p>
          <p className="text-[11px] text-slate-400">Bấm nút &ldquo;Làm Mới Traffic&rdquo; để hệ thống quét dữ liệu ngay.</p>
        </div>
      );
    }

    // Responsive SVG Timeline Chart
    const height = 125;
    const width = 760;
    const paddingLeft = 32;
    const paddingRight = 16;
    const paddingTop = 18;
    const paddingBottom = 22;

    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    const maxVal = 100;

    const points = timeline.map((item, idx) => {
      const x = paddingLeft + (idx / Math.max(1, timeline.length - 1)) * chartWidth;
      const y = paddingTop + chartHeight - (Math.max(0, Math.min(100, item.value)) / maxVal) * chartHeight;
      return { ...item, x, y };
    });

    const pathD = points.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, '');

    const areaD = `${pathD} L ${points[points.length - 1].x} ${paddingTop + chartHeight} L ${points[0].x} ${paddingTop + chartHeight} Z`;

    const peakVal = Math.max(...timeline.map(t => t.value));
    const peakPoint = points.find(p => p.value === peakVal && peakVal > 0);

    // Year ticks
    const yearMarkers: { label: string; x: number }[] = [];
    timeline.forEach((item, idx) => {
      if (item.month.endsWith('-01') || idx === 0 || idx === timeline.length - 1) {
        const year = item.month.slice(0, 4);
        if (!yearMarkers.some(m => m.label === year)) {
          yearMarkers.push({
            label: year,
            x: paddingLeft + (idx / Math.max(1, timeline.length - 1)) * chartWidth
          });
        }
      }
    });

    return (
      <div className="w-full overflow-x-auto bg-white p-2 rounded-xl border border-slate-200">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto min-w-[520px] select-none">
          <defs>
            <linearGradient id={`grad-${store.store_id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map(v => {
            const y = paddingTop + chartHeight - (v / 100) * chartHeight;
            return (
              <g key={v}>
                <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#f1f5f9" strokeDasharray="3 3" />
                <text x={paddingLeft - 6} y={y + 3} textAnchor="end" fontSize="8.5" fill="#94a3b8" fontFamily="monospace">
                  {v}
                </text>
              </g>
            );
          })}

          {/* Target filtered month highlight columns (Seasonality Highlights) */}
          {trendMonthFilter !== 'all' && points.filter(p => p.month.endsWith(`-${trendMonthFilter.padStart(2, '0')}`)).map((p, idx) => (
            <g key={`season-hl-${idx}`}>
              <rect
                x={p.x - 7}
                y={paddingTop}
                width={14}
                height={chartHeight}
                fill="#f59e0b"
                opacity={0.18}
                rx={3}
              />
              <line
                x1={p.x}
                y1={paddingTop}
                x2={p.x}
                y2={paddingTop + chartHeight}
                stroke="#f59e0b"
                strokeWidth={1}
                strokeDasharray="2 2"
                opacity={0.6}
              />
            </g>
          ))}

          {/* Monthly vertical volume bars */}
          {points.map((p, idx) => {
            const barW = Math.max(2, Math.min(8, (chartWidth / points.length) * 0.65));
            const barH = paddingTop + chartHeight - p.y;
            const isSeasonMonth = trendMonthFilter !== 'all' && p.month.endsWith(`-${trendMonthFilter.padStart(2, '0')}`);
            return (
              <rect
                key={`bar-${idx}`}
                x={p.x - barW / 2}
                y={p.y}
                width={barW}
                height={Math.max(1, barH)}
                rx={1}
                fill={p.value === peakVal && peakVal > 0 ? '#f59e0b' : isSeasonMonth ? '#d97706' : '#6366f1'}
                opacity={p.value === peakVal && peakVal > 0 ? 0.4 : isSeasonMonth ? 0.35 : 0.12}
              >
                <title>{`${p.month}: ${p.value} pts`}</title>
              </rect>
            );
          })}

          {/* Area fill */}
          <path d={areaD} fill={`url(#grad-${store.store_id})`} />

          {/* Line stroke */}
          <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />

          {/* Monthly points & hover tooltips */}
          {points.map((p, idx) => (
            <g key={idx} className="group cursor-pointer">
              <circle
                cx={p.x}
                cy={p.y}
                r={p.value === peakVal && peakVal > 0 ? 3.5 : 2}
                fill={p.value === peakVal && peakVal > 0 ? '#f59e0b' : '#6366f1'}
              />
              <title>{`${p.month}: ${p.value} pts`}</title>
            </g>
          ))}

          {/* Target filtered month special point indicators */}
          {trendMonthFilter !== 'all' && points.filter(p => p.month.endsWith(`-${trendMonthFilter.padStart(2, '0')}`) && p !== peakPoint).map((p, idx) => (
            <g key={`season-pt-${idx}`}>
              <circle cx={p.x} cy={p.y} r={4.5} fill="#f59e0b" stroke="#ffffff" strokeWidth="1.8" />
              <text
                x={p.x}
                y={Math.max(12, p.y - 8)}
                textAnchor="middle"
                fontSize="8.5"
                fontWeight="bold"
                fill="#b45309"
              >
                🌟 {p.month.slice(2)} ({p.value})
              </text>
            </g>
          ))}

          {/* Secondary notable spikes (e.g. value >= 50 and not the primary peak and not already shown as season point) */}
          {points.filter(p => p.value >= 50 && p !== peakPoint && !(trendMonthFilter !== 'all' && p.month.endsWith(`-${trendMonthFilter.padStart(2, '0')}`))).map((sp, sIdx) => (
            <g key={`spike-${sIdx}`}>
              <circle cx={sp.x} cy={sp.y} r={3.5} fill="#6366f1" stroke="#ffffff" strokeWidth="1.2" />
              <text
                x={sp.x}
                y={Math.max(12, sp.y - 6)}
                textAnchor="middle"
                fontSize="8"
                fontWeight="bold"
                fill="#4f46e5"
              >
                {sp.month} ({sp.value})
              </text>
            </g>
          ))}

          {/* Peak point indicator */}
          {peakPoint && (
            <g>
              <circle cx={peakPoint.x} cy={peakPoint.y} r={7} fill="none" stroke="#f59e0b" strokeWidth="1.5" opacity="0.7" />
              <circle cx={peakPoint.x} cy={peakPoint.y} r={4} fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
              <text
                x={peakPoint.x}
                y={Math.max(12, peakPoint.y - 7)}
                textAnchor={peakPoint.x > width - 70 ? 'end' : peakPoint.x < paddingLeft + 70 ? 'start' : 'middle'}
                fontSize="9"
                fontWeight="bold"
                fill="#d97706"
              >
                🔥 {peakPoint.month} ({peakPoint.value})
              </text>
            </g>
          )}

          {/* X-axis year ticks */}
          {yearMarkers.map((m, idx) => (
            <text key={idx} x={m.x} y={height - 4} textAnchor="middle" fontSize="9.5" fontWeight="600" fill="#64748b">
              {m.label}
            </text>
          ))}
        </svg>
      </div>
    );
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
              onClick={handlePurgeIndianStores}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 transition cursor-pointer"
              title="Quét & Xóa tất cả các dự án Ấn Độ / Nam Á (INR, PKR, BDT, LKR, NPR, .in)"
            >
              <Trash2 size={13} />
              <span>Xóa Store Ấn Độ</span>
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

        {/* BACKGROUND TRAFFIC WORKER WIDGET */}
        <section className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-indigo-800/50 rounded-2xl p-4 shadow-lg text-white">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl border ${trafficWorkerStatus?.is_running ? 'bg-indigo-600/30 border-indigo-500/50 text-indigo-400' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
                <BarChart2 size={20} className={trafficWorkerStatus?.is_running && !trafficWorkerStatus.is_paused ? 'animate-pulse' : ''} />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-bold text-white">Quét Traffic & Google Trends Tự Động</h3>
                  {trafficWorkerStatus?.is_running ? (
                    trafficWorkerStatus.is_paused ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        ⏸️ Tạm dừng
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                        Đang quét: {trafficWorkerStatus.current_store || '...'}
                      </span>
                    )
                  ) : (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                      ⚪ Sẵn sàng
                    </span>
                  )}
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">
                    🎯 Ưu tiên Cookie ≥ 14 ngày
                  </span>
                  {trafficWorkerStatus?.gt_cooldown_seconds && trafficWorkerStatus.gt_cooldown_seconds > 0 ? (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
                      ⏳ Google Trends tạm nghỉ {trafficWorkerStatus.gt_cooldown_seconds}s (Tránh ban IP)
                    </span>
                  ) : null}
                  <span className="text-[10px] font-medium text-slate-400">
                    (Chỉ lưu dữ liệu thật, không bịa số)
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Tự động tra cứu Domain Rank (Tranco Top 1M) và Google Trends 5 năm cho các store chất lượng cao
                </p>
              </div>
            </div>

            {/* Control Buttons */}
            <div className="flex items-center gap-2">
              {trafficWorkerStatus?.is_running ? (
                <>
                  {trafficWorkerStatus.is_paused ? (
                    <button
                      onClick={handleResumeTrafficWorker}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition cursor-pointer shadow-sm"
                    >
                      <Play size={13} fill="currentColor" />
                      <span>Tiếp tục</span>
                    </button>
                  ) : (
                    <button
                      onClick={handlePauseTrafficWorker}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition cursor-pointer shadow-sm"
                    >
                      <Pause size={13} />
                      <span>Tạm dừng</span>
                    </button>
                  )}
                  <button
                    onClick={handleStopTrafficWorker}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-rose-600/80 hover:bg-rose-600 text-white transition cursor-pointer shadow-sm"
                  >
                    <X size={13} />
                    <span>Dừng hẳn</span>
                  </button>
                </>
              ) : (
                <button
                  onClick={handleStartTrafficWorker}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-400 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/25 transition cursor-pointer"
                >
                  <Play size={13} fill="currentColor" />
                  <span>Chạy Quét Traffic (Cookie ≥ 14d)</span>
                </button>
              )}
            </div>
          </div>

          {/* Progress Bar & Real-time Stats */}
          <div className="mt-3 pt-3 border-t border-indigo-900/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <div className="w-full sm:w-1/2">
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                <span>Tiến độ các store Cookie ≥ 14 ngày:</span>
                <span className="font-mono text-indigo-300 font-semibold">
                  {trafficWorkerStatus ? `${trafficWorkerStatus.checked_cookie_14_plus} / ${trafficWorkerStatus.total_cookie_14_plus} (${trafficWorkerStatus.total_cookie_14_plus > 0 ? ((trafficWorkerStatus.checked_cookie_14_plus / trafficWorkerStatus.total_cookie_14_plus) * 100).toFixed(1) : 0}%)` : '0 / 0'}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-500 rounded-full"
                  style={{
                    width: trafficWorkerStatus && trafficWorkerStatus.total_cookie_14_plus > 0
                      ? `${Math.min(100, (trafficWorkerStatus.checked_cookie_14_plus / trafficWorkerStatus.total_cookie_14_plus) * 100)}%`
                      : '0%'
                  }}
                />
              </div>
            </div>

            <div className="flex items-center gap-3 text-[11px] flex-wrap">
              <span className="inline-flex items-center gap-1 text-emerald-400 font-medium bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
                <CheckCircle2 size={11} /> Có Data: {trafficWorkerStatus?.with_data ?? stats?.traffic?.with_data ?? 0}
              </span>
              <span className="inline-flex items-center gap-1 text-slate-400 font-medium bg-slate-800/60 px-2 py-0.5 rounded border border-slate-700">
                ⚪ Chưa có data: {trafficWorkerStatus?.no_data ?? stats?.traffic?.no_data ?? 0}
              </span>
              <span className="inline-flex items-center gap-1 text-amber-400 font-medium bg-amber-950/50 px-2 py-0.5 rounded border border-amber-800/40">
                🔥 ≥ 10K visits: {trafficWorkerStatus?.above_10k ?? stats?.traffic?.above_10k ?? 0}
              </span>
              {(trafficWorkerStatus?.errors || 0) > 0 && (
                <span className="inline-flex items-center gap-1 text-rose-400 font-medium bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800/40">
                  <AlertCircle size={11} /> Lỗi: {trafficWorkerStatus?.errors}
                </span>
              )}
            </div>
          </div>
        </section>

        {/* SEARCH & FILTERS BAR */}
        <section className="bg-white border border-slate-200 rounded-2xl p-3 shadow-sm flex flex-col gap-2.5">
          <div className="flex items-center gap-2.5 flex-wrap">
            <div className="relative flex-1 min-w-[260px]">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search store name, website, notes, description..."
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

            {/* Category Dropdown */}
            <select
              value={selectedCategory}
              onChange={e => {
                setSelectedCategory(e.target.value);
                setPage(1);
              }}
              className={`text-xs font-semibold py-2.5 px-3 rounded-xl border focus:outline-none transition cursor-pointer ${
                selectedCategory !== 'all'
                  ? 'bg-purple-50 border-purple-300 text-purple-900'
                  : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300'
              }`}
              title="Lọc theo ngành hàng"
            >
              <option value="all">🏷️ Tất cả ngành hàng</option>
              {stats?.categories && stats.categories.length > 0 ? (
                stats.categories.map(c => (
                  <option key={c.category} value={c.category}>
                    {c.category} ({c.count.toLocaleString()})
                  </option>
                ))
              ) : (
                <option value="General">General</option>
              )}
            </select>

            {/* 18+ Adult Filter */}
            <select
              value={adultFilter}
              onChange={e => {
                setAdultFilter(e.target.value);
                setPage(1);
              }}
              className={`text-xs font-semibold py-2.5 px-3 rounded-xl border focus:outline-none transition cursor-pointer ${
                adultFilter === 'hide'
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                  : adultFilter === 'only_adult'
                  ? 'bg-rose-50 border-rose-300 text-rose-800'
                  : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300'
              }`}
              title="Bộ lọc nội dung 18+ / Đồ chơi người lớn"
            >
              <option value="hide">🛡️ Ẩn 18+ (Sạch)</option>
              <option value="show_all">👁️ Hiện tất cả ({stats?.adult_count ? `gồm ${stats.adult_count} web 18+` : 'tất cả'})</option>
              <option value="only_adult">🔞 Chỉ xem 18+ ({stats?.adult_count || 0})</option>
            </select>

            <span className="text-xs text-slate-500 font-medium px-1 whitespace-nowrap">
              Hiển thị {stores.length} / {totalCount.toLocaleString()} stores
            </span>
          </div>

          {/* GOOGLE TRENDS & MONTHLY FILTER */}
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 bg-amber-50 border border-amber-200/80 px-2.5 py-1.5 rounded-lg">
                <Flame size={13} className="text-amber-500 fill-amber-500" />
                <span>Google Trends Theo Tháng:</span>
              </span>

              {/* Month Selector: Tháng 1 -> Tháng 12 */}
              <select
                value={trendMonthFilter}
                onChange={e => {
                  setTrendMonthFilter(e.target.value);
                  setPage(1);
                }}
                className={`text-xs font-medium py-1.5 px-3 rounded-lg border focus:outline-none transition cursor-pointer ${
                  trendMonthFilter !== 'all'
                    ? 'bg-amber-50 border-amber-300 text-amber-900 font-bold'
                    : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                }`}
              >
                <option value="all">🗓️ Tất cả các tháng (T1 - T12)</option>
                <option value="1">Tháng 1</option>
                <option value="2">Tháng 2</option>
                <option value="3">Tháng 3</option>
                <option value="4">Tháng 4</option>
                <option value="5">Tháng 5</option>
                <option value="6">Tháng 6</option>
                <option value="7">Tháng 7</option>
                <option value="8">Tháng 8</option>
                <option value="9">Tháng 9</option>
                <option value="10">Tháng 10</option>
                <option value="11">Tháng 11</option>
                <option value="12">Tháng 12</option>
              </select>

              {/* Tiêu Chí Xu Hướng (Đón sóng, Đỉnh cao, Thương hiệu lớn) */}
              <select
                value={trendScoreFilter}
                onChange={e => {
                  setTrendScoreFilter(e.target.value);
                  setPage(1);
                }}
                className={`text-xs font-medium py-1.5 px-3 rounded-lg border focus:outline-none transition cursor-pointer ${
                  trendScoreFilter === 'growth'
                    ? 'bg-emerald-50 border-emerald-400 text-emerald-900 font-bold'
                    : trendScoreFilter !== 'all'
                    ? 'bg-amber-50 border-amber-300 text-amber-900 font-bold'
                    : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                }`}
              >
                <option value="all">🌊 Tất cả (Có tìm kiếm trong tháng)</option>
                <option value="growth">↗️ Đón sóng tăng trưởng (Đang vào mùa - Tăng so với tháng trước)</option>
                <option value="peak">🏔️ Bùng nổ đạt đỉnh (Mùa bán chạy nhất của store)</option>
                <option value="high">🔥 Lượng tìm kiếm cao (Thương hiệu lớn)</option>
              </select>
            </div>

            {trendMonthFilter !== 'all' && (
              <span className="text-[11px] text-amber-800 font-medium bg-amber-50/80 border border-amber-200 px-2.5 py-1 rounded-md">
                Đang dò store hot vào <strong>Tháng {trendMonthFilter}</strong> {
                  trendScoreFilter === 'growth'
                    ? '(↗️ Đón sóng tăng trưởng)'
                    : trendScoreFilter === 'peak'
                    ? '(🏔️ Đạt đỉnh cao nhất)'
                    : trendScoreFilter === 'high'
                    ? '(🔥 Lượng tìm kiếm lớn)'
                    : ''
                }
              </span>
            )}
          </div>

          {/* Active filters bar if any filter is active */}
          {(selectedCategory !== 'all' || adultFilter !== 'hide' || currencyFilter !== 'all' || commissionFilter !== 'all' || cookieFilter !== 'all' || trafficFilter !== 'all' || trendMonthFilter !== 'all' || trendScoreFilter !== 'all' || notesFilter !== 'all' || search.trim() !== '') && (
            <div className="flex items-center gap-2 pt-1 border-t border-slate-100 flex-wrap text-xs">
              <span className="text-[11px] font-semibold text-indigo-600 flex items-center gap-1">
                <Filter size={12} /> Đang lọc:
              </span>
              {selectedCategory !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-purple-50 text-purple-800 px-2 py-0.5 rounded-md border border-purple-300 font-medium">
                  Ngành: <strong>{selectedCategory}</strong>
                  <button onClick={() => { setSelectedCategory('all'); setPage(1); }} className="hover:text-purple-950 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {adultFilter !== 'hide' && (
                <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md border font-medium ${
                  adultFilter === 'only_adult' ? 'bg-rose-50 text-rose-800 border-rose-300' : 'bg-slate-100 text-slate-800 border-slate-300'
                }`}>
                  18+: <strong>{adultFilter === 'only_adult' ? 'Chỉ xem 18+' : 'Hiện cả 18+'}</strong>
                  <button onClick={() => { setAdultFilter('hide'); setPage(1); }} className="hover:opacity-75 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {trendMonthFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-amber-50 text-amber-800 px-2 py-0.5 rounded-md border border-amber-200 font-medium">
                  Google Trends: <strong>Tháng {trendMonthFilter}</strong>
                  <button onClick={() => { setTrendMonthFilter('all'); setPage(1); }} className="hover:text-amber-950 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {trendScoreFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded-md border border-emerald-300 font-medium">
                  Xu hướng: <strong>{
                    trendScoreFilter === 'growth'
                      ? '↗️ Đón sóng tăng trưởng'
                      : trendScoreFilter === 'peak'
                      ? '🏔️ Bùng nổ đạt đỉnh'
                      : '🔥 Lượng tìm kiếm lớn'
                  }</strong>
                  <button onClick={() => { setTrendScoreFilter('all'); setPage(1); }} className="hover:text-emerald-950 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
              {trafficFilter !== 'all' && (
                <span className="inline-flex items-center gap-1 text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-200 font-medium">
                  Traffic: <strong>{trafficFilter === 'has_data' ? 'Đã có data' : trafficFilter === 'no_data' ? 'Chưa có data' : `≥ ${Number(trafficFilter) / 1000}K`}</strong>
                  <button onClick={() => { setTrafficFilter('all'); setPage(1); }} className="hover:text-indigo-900 ml-0.5">
                    <X size={11} />
                  </button>
                </span>
              )}
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
                  setTrafficFilter('all');
                  setTrendMonthFilter('all');
                  setTrendScoreFilter('all');
                  setTrendPeakOnly(false);
                  setTrendGrowthOnly(false);
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

                  {/* TRAFFIC & TRENDS COLUMN */}
                  <th className="py-2.5 px-3 w-36">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleSort('traffic_raw_value')}
                        className="flex items-center justify-between hover:text-indigo-600 transition cursor-pointer w-full"
                        title="Bấm để sắp xếp traffic Cao nhất / Thấp nhất"
                      >
                        <span>Traffic</span>
                        {sortBy === 'traffic_raw_value' ? (
                          sortOrder === 'asc' ? <ArrowUp size={12} className="text-indigo-600" /> : <ArrowDown size={12} className="text-indigo-600" />
                        ) : (
                          <ArrowUpDown size={11} className="text-slate-400" />
                        )}
                      </button>
                      <select
                        value={trafficFilter}
                        onChange={e => {
                          setTrafficFilter(e.target.value);
                          setPage(1);
                        }}
                        className={`text-[11px] font-normal py-1 px-1.5 rounded-lg border focus:outline-none transition cursor-pointer ${
                          trafficFilter !== 'all'
                            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <option value="all">Tất cả Traffic</option>
                        <option value="10000">≥ 10K / tháng</option>
                        <option value="20000">≥ 20K / tháng</option>
                        <option value="50000">≥ 50K / tháng</option>
                        <option value="100000">≥ 100K / tháng</option>
                        <option value="has_data">Đã có data (Real)</option>
                        <option value="no_data">Chưa có data (Store nhỏ/mới)</option>
                      </select>
                    </div>
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
                    <React.Fragment key={store.store_id}>
                      <tr
                        onClick={() => setExpandedStoreId(prev => prev === store.store_id ? null : store.store_id)}
                        className={`transition cursor-pointer group ${
                          expandedStoreId === store.store_id ? 'bg-indigo-50/70 border-b border-indigo-200' : 'hover:bg-slate-200/40'
                        }`}
                      >
                        {/* Favorite Button */}
                        <td className="py-3 px-3 text-center">
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

                            <div className="min-w-0 max-w-[150px]">
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
                                  className="text-[11px] text-slate-500 hover:text-indigo-500 inline-flex items-center gap-1 truncate max-w-[140px]"
                                  title={store.website_url}
                                >
                                  <Globe size={10} className="flex-shrink-0" />
                                  <span className="truncate">{store.website_url.replace(/^https?:\/\//, '')}</span>
                                  <ExternalLink size={9} className="flex-shrink-0" />
                                </a>
                              )}
                              <div className="flex items-center gap-1 flex-wrap mt-0.5">
                                {store.is_adult === 1 && (
                                  <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                    🔞 18+
                                  </span>
                                )}
                                {(() => {
                                  let tags: string[] = [];
                                  if (store.categories_json) {
                                    try { tags = JSON.parse(store.categories_json); } catch (e) {}
                                  }
                                  if (tags.length === 0 && store.category && store.category !== 'General') {
                                    tags = [store.category];
                                  }
                                  return tags.slice(0, 2).map((t, idx) => (
                                    <span
                                      key={idx}
                                      className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-medium bg-slate-100 text-slate-700 border border-slate-200"
                                      title={t}
                                    >
                                      {t.split(' & ')[0]}
                                    </span>
                                  ));
                                })()}
                              </div>
                            </div>

                            <ChevronDown
                              size={14}
                              className={`ml-auto text-slate-400 transition-transform duration-200 flex-shrink-0 ${
                                expandedStoreId === store.store_id ? 'rotate-180 text-indigo-600' : 'group-hover:text-slate-600'
                              }`}
                            />
                          </div>
                        </td>

                        {/* Traffic & Trends */}
                        <td className="py-3 px-3 w-36">
                          {(() => {
                            let seasonalScore: number | null = null;
                            let prevScore: number | null = null;
                            let isSeasonalPeak = false;

                            if (trendMonthFilter !== 'all') {
                              const m = parseInt(trendMonthFilter);
                              const targetSuffix = `-${m.toString().padStart(2, '0')}`;
                              const prevM = m === 1 ? 12 : m - 1;
                              const prevSuffix = `-${prevM.toString().padStart(2, '0')}`;

                              if (store.trend_peak_month && store.trend_peak_month.includes(targetSuffix)) {
                                isSeasonalPeak = true;
                              }
                              if (store.trend_timeline_json) {
                                try {
                                  const tl = JSON.parse(store.trend_timeline_json);
                                  const match = tl.filter((t: any) => t.month && t.month.endsWith(targetSuffix));
                                  if (match.length > 0) {
                                    seasonalScore = match[match.length - 1].value;
                                  }
                                  const matchPrev = tl.filter((t: any) => t.month && t.month.endsWith(prevSuffix));
                                  if (matchPrev.length > 0) {
                                    prevScore = matchPrev[matchPrev.length - 1].value;
                                  }
                                } catch (e) {}
                              }
                            }

                            const isGrowing = seasonalScore !== null && prevScore !== null && seasonalScore > prevScore;
                            const growthPct = isGrowing ? (prevScore! > 0 ? Math.round(((seasonalScore! - prevScore!) / prevScore!) * 100) : null) : null;

                            return (
                              <div className="flex flex-col gap-0.5">
                                {store.traffic_status === 'success' && store.traffic_raw_value && store.traffic_raw_value > 0 ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 w-fit">
                                    <Eye size={11} className="text-emerald-600" />
                                    {store.traffic_visits || `${(store.traffic_raw_value / 1000).toFixed(0)}K`}
                                  </span>
                                ) : store.traffic_status === 'no_data' || (store.traffic_status !== 'pending' && store.trend_status === 'no_data') ? (
                                  <span className="text-[11px] text-slate-400 italic" title="Chưa có dữ liệu (Store nhỏ/mới)">
                                    Store nhỏ/mới
                                  </span>
                                ) : store.traffic_status === 'error' || store.trend_status === 'error' ? (
                                  <span className="text-[11px] text-amber-600 font-medium" title="Lỗi kết nối khi tra cứu">
                                    Lỗi tải
                                  </span>
                                ) : (
                                  <button
                                    onClick={(e) => handleRefreshSingleStore(store.store_id, e)}
                                    className="text-[10px] text-indigo-600 hover:text-indigo-800 hover:underline font-medium cursor-pointer"
                                  >
                                    Kiểm tra ngay
                                  </button>
                                )}

                                {/* Seasonal month score or peak badge */}
                                {trendMonthFilter !== 'all' ? (
                                  isSeasonalPeak ? (
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300 w-fit">
                                      🏔️ Đỉnh T{trendMonthFilter}
                                    </span>
                                  ) : isGrowing ? (
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 w-fit">
                                      ↗️ T{trendMonthFilter}: {seasonalScore}đ {growthPct !== null ? `(+${growthPct}%)` : '(Bùng nổ)'}
                                    </span>
                                  ) : seasonalScore !== null ? (
                                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold w-fit ${
                                      seasonalScore >= 70
                                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                        : seasonalScore >= 50
                                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                        : 'bg-slate-100 text-slate-600 border border-slate-200'
                                    }`}>
                                      🔥 T{trendMonthFilter}: {seasonalScore}đ
                                    </span>
                                  ) : (
                                    <span className="text-[10px] text-slate-400">T{trendMonthFilter}: 0đ</span>
                                  )
                                ) : store.trend_peak_month ? (
                                  <span className="text-[10px] text-amber-600 font-semibold truncate max-w-[120px]">
                                    🔥 {store.trend_peak_month.split(' ')[0]}
                                  </span>
                                ) : null}
                              </div>
                            );
                          })()}
                        </td>

                        {/* Currency */}
                        <td className="py-3 px-3 w-24">
                          <span className="text-slate-700 font-mono text-xs font-semibold">
                            {store.currency || 'USD'}
                          </span>
                        </td>

                        {/* Commission */}
                        <td className="py-3 px-3 w-32">
                          {(() => {
                            const rawComm = (store.commission_rate || `${store.commission_value}%`).trim();
                            const isFlatCash = rawComm.includes('$') || rawComm.includes('€') || rawComm.includes('£') || rawComm.includes('₹') || (!rawComm.includes('%') && store.commission_value >= 100);

                            return (
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-bold font-mono border ${
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
                        <td className="py-3 px-3 w-28 whitespace-nowrap">
                          <span className="text-slate-600 inline-flex items-center gap-1 font-mono text-xs">
                            <Clock size={12} className="text-slate-500" />
                            {store.cookie_days} days
                          </span>
                        </td>

                        {/* Notes */}
                        <td className="py-3 px-4">
                          {store.notes ? (
                            <span className="text-[11px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 inline-block max-w-[240px] truncate font-medium">
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
                              onClick={e => {
                                e.stopPropagation();
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

                      {/* EXPANDABLE ACCORDION ROW */}
                      {expandedStoreId === store.store_id && (
                        <tr className="bg-gradient-to-b from-indigo-50/50 via-slate-50 to-indigo-50/30 border-b border-indigo-200 animate-in fade-in duration-200">
                          <td colSpan={8} className="p-4 sm:p-5">
                            <div className="bg-white rounded-2xl border border-indigo-100 shadow-sm p-4 sm:p-5 space-y-4">
                              {/* Accordion Header */}
                              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
                                <div className="flex items-center gap-3">
                                  <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
                                    <BarChart2 size={18} />
                                  </div>
                                  <div>
                                    <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2 flex-wrap">
                                      <span>{store.name} — Phân Tích Lưu Lượng & Google Trends</span>
                                      {store.traffic_status === 'success' && (
                                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                          Dữ liệu thực tế
                                        </span>
                                      )}
                                    </h4>
                                    <span className="text-[11px] text-slate-500">
                                      Chi tiết lượng truy cập ước tính từ Domain Rank và xu hướng tìm kiếm Google 2-5 năm
                                    </span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={(e) => handleRefreshSingleStore(store.store_id, e)}
                                    disabled={refreshingStoreId === store.store_id}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition cursor-pointer"
                                    title="Làm mới traffic và Google Trends cho cửa hàng này"
                                  >
                                    <RefreshCw size={12} className={refreshingStoreId === store.store_id ? 'animate-spin' : ''} />
                                    <span>{refreshingStoreId === store.store_id ? 'Đang phân tích...' : 'Làm Mới Traffic'}</span>
                                  </button>

                                  <button
                                    onClick={() => setExpandedStoreId(null)}
                                    className="p-1.5 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition cursor-pointer"
                                    title="Thu gọn dòng"
                                  >
                                    <X size={15} />
                                  </button>
                                </div>
                              </div>

                              {/* 3 Summary Cards */}
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {/* Card 1: Traffic Visits */}
                                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
                                  <div className="flex items-center justify-between text-slate-500 text-[11px] font-medium mb-1">
                                    <span className="flex items-center gap-1">
                                      <Eye size={12} className="text-slate-400" />
                                      Lượng truy cập ước tính (Monthly Visits)
                                    </span>
                                    <span className="text-[10px] uppercase font-bold text-slate-400">{store.traffic_top_country || 'Global'}</span>
                                  </div>
                                  <div className="text-lg font-bold text-slate-900 font-mono">
                                    {store.traffic_status === 'success' && store.traffic_visits ? (
                                      <span className="text-emerald-600">{store.traffic_visits} <span className="text-xs font-normal text-slate-500">lượt/tháng</span></span>
                                    ) : store.traffic_status === 'no_data' ? (
                                      <span className="text-xs font-medium text-slate-400">Chưa có dữ liệu (Store nhỏ/mới)</span>
                                    ) : store.traffic_status === 'error' ? (
                                      <span className="text-xs font-medium text-rose-500">Lỗi kết nối</span>
                                    ) : (
                                      <span className="text-xs font-medium text-slate-400">Chưa kiểm tra</span>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-slate-400 mt-1">
                                    {store.traffic_status === 'success' ? 'Xác thực từ bảng xếp hạng tên miền toàn cầu Tranco' : 'Cửa hàng chưa có tên miền xếp hạng trong top 1M'}
                                  </div>
                                </div>

                                {/* Card 2: Peak Season */}
                                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
                                  <div className="flex items-center justify-between text-slate-500 text-[11px] font-medium mb-1">
                                    <span className="flex items-center gap-1">
                                      <Flame size={12} className="text-amber-500" />
                                      Mùa tìm kiếm đỉnh cao (Peak Month)
                                    </span>
                                    <span className="text-[10px] font-semibold text-indigo-600">Google Trends</span>
                                  </div>
                                  <div className="text-lg font-bold text-slate-900">
                                    {store.trend_peak_month ? (
                                      <span className="text-amber-600 inline-flex items-center gap-1">
                                        🔥 {store.trend_peak_month}
                                      </span>
                                    ) : store.trend_status === 'no_data' ? (
                                      <span className="text-xs font-medium text-slate-400">Chưa đủ dữ liệu</span>
                                    ) : (
                                      <span className="text-xs font-medium text-slate-400">Chưa có số liệu</span>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-slate-400 mt-1">
                                    {store.trend_peak_month ? 'Tháng có lượng quan tâm mua sắm và tìm kiếm cao nhất 2-5 năm' : 'Thương hiệu chưa đủ lượng tìm kiếm tối thiểu của Google Trends'}
                                  </div>
                                </div>

                                {/* Card 3: External Research Links */}
                                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between">
                                  <span className="text-slate-500 text-[11px] font-medium mb-1">Tra cứu mở rộng</span>
                                  <div className="flex flex-wrap gap-1.5 mt-1">
                                    {(() => {
                                      const brand = store.name.split(' - ')[0].replace(/^https?:\/\//, '').replace(/^www\./, '').split('.')[0];
                                      const domain = store.website_url.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
                                      return (
                                        <>
                                          <a
                                            href={`https://trends.google.com/trends/explore?q=${encodeURIComponent(brand)}`}
                                            target="_blank"
                                            rel="noreferrer"
                                            onClick={e => e.stopPropagation()}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-indigo-50 text-indigo-700 border border-slate-200 hover:border-indigo-200 transition"
                                          >
                                            <span>Google Trends</span>
                                            <ExternalLink size={10} />
                                          </a>
                                          {domain && (
                                            <a
                                              href={`https://www.similarweb.com/website/${domain}`}
                                              target="_blank"
                                              rel="noreferrer"
                                              onClick={e => e.stopPropagation()}
                                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-indigo-50 text-indigo-700 border border-slate-200 hover:border-indigo-200 transition"
                                            >
                                              <span>Similarweb</span>
                                              <ExternalLink size={10} />
                                            </a>
                                          )}
                                          {store.portal_url && (
                                            <a
                                              href={store.portal_url}
                                              target="_blank"
                                              rel="noreferrer"
                                              onClick={e => e.stopPropagation()}
                                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-indigo-50 text-indigo-700 border border-slate-200 hover:border-indigo-200 transition"
                                            >
                                              <span>Portal</span>
                                              <ExternalLink size={10} />
                                            </a>
                                          )}
                                        </>
                                      );
                                    })()}
                                  </div>
                                  <div className="text-[10px] text-slate-400 mt-2">
                                    Mở trực tiếp trang phân tích chuyên sâu của Google & Similarweb
                                  </div>
                                </div>
                              </div>

                              {/* 2-5 Year Google Trends Timeline Chart */}
                              <div className="p-4 rounded-xl bg-slate-50/80 border border-slate-200/80">
                                <div className="flex items-center justify-between mb-3">
                                  <div className="flex items-center gap-2">
                                    <TrendingUp size={15} className="text-indigo-600" />
                                    <h5 className="text-xs font-bold text-slate-800">
                                      Biểu đồ xu hướng tìm kiếm Google 2-5 năm (Search Interest 0 - 100)
                                    </h5>
                                  </div>
                                  {store.trend_peak_month && (
                                    <span className="text-[11px] font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                                      🔥 Tháng cao điểm: {store.trend_peak_month}
                                    </span>
                                  )}
                                </div>

                                {renderTrendsChart(store)}
                              </div>

                              {/* Website Overview & Products Section */}
                              {(store.site_title || store.site_description || store.category) && (
                                <div className="p-3.5 rounded-xl bg-purple-50/60 border border-purple-200/80 flex flex-col gap-2">
                                  <div className="flex items-center justify-between flex-wrap gap-2">
                                    <div className="flex items-center gap-2">
                                      <Tag size={14} className="text-purple-600" />
                                      <span className="text-xs font-bold text-purple-950">
                                        Sản Phẩm & Ngành Hàng Website Cung Cấp
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      {store.is_adult === 1 && (
                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
                                          🔞 Adult 18+
                                        </span>
                                      )}
                                      {(() => {
                                        let tags: string[] = [];
                                        if (store.categories_json) {
                                          try { tags = JSON.parse(store.categories_json); } catch (e) {}
                                        }
                                        if (tags.length === 0 && store.category && store.category !== 'General') {
                                          tags = [store.category];
                                        }
                                        return tags.map((t, idx) => (
                                          <span
                                            key={idx}
                                            className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-white text-purple-700 border border-purple-200 shadow-2xs"
                                          >
                                            🏷️ {t}
                                          </span>
                                        ));
                                      })()}
                                    </div>
                                  </div>
                                  {store.site_title && (
                                    <div className="text-xs font-semibold text-slate-800">
                                      {store.site_title}
                                    </div>
                                  )}
                                  {store.site_description ? (
                                    <div className="text-xs text-slate-600 leading-relaxed italic bg-white/70 p-2.5 rounded-lg border border-purple-100">
                                      "{store.site_description}"
                                    </div>
                                  ) : (
                                    <div className="text-[11px] text-slate-400 italic">
                                      (Tiến trình cào ngầm sẽ tự động tải tóm tắt sản phẩm khi duyệt qua website này)
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Inline Quick CRM Notes */}
                              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2 border-t border-slate-100" onClick={e => e.stopPropagation()}>
                                <span className="text-xs font-semibold text-slate-600 whitespace-nowrap">Ghi chú nhanh:</span>
                                <input
                                  type="text"
                                  value={quickNoteEdit[store.store_id] ?? (store.notes || '')}
                                  onChange={(e) => setQuickNoteEdit(prev => ({ ...prev, [store.store_id]: e.target.value }))}
                                  placeholder="Ví dụ: Hoa hồng 30%, đã liên hệ xin coupon riêng..."
                                  className="flex-1 bg-white border border-slate-300 rounded-xl px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:border-indigo-500"
                                />
                                <button
                                  onClick={() => handleSaveQuickNote(store.store_id)}
                                  className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition cursor-pointer shadow-sm"
                                >
                                  Lưu
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
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
