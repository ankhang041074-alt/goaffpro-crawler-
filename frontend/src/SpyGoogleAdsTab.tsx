import React, { useState, useEffect } from 'react';
import {
  Search,
  ExternalLink,
  Flame,
  CheckCircle2,
  RefreshCw,
  Video,
  FileText,
  Image as ImageIcon,
  Sparkles,
  ShieldCheck,
  Globe2,
  ChevronDown,
  ChevronUp,
  Layers,
  Award
} from 'lucide-react';

interface Creative {
  id: string;
  format: string;
  format_label: string;
  headline: string;
  description: string;
  landing_page: string;
  last_shown: string;
  duration_days: number;
  image_url?: string;
  video_url?: string;
}

interface Advertiser {
  id: string;
  name: string;
  legal_name: string;
  country: string;
  country_flag: string;
  is_verified: boolean;
  advertiser_url: string;
  first_seen: string;
  last_shown: string;
  duration_days: number;
  longevity_badge: 'test' | 'stable' | 'win_ads' | 'super_scale';
  scale_label?: string;
  formats: string[];
  ad_count: number;
  creatives: Creative[];
}

interface SpyData {
  domain: string;
  updated_at: string;
  total_advertisers: number;
  total_ads: number;
  win_ads_count: number;
  super_scale_count: number;
  test_ads_count?: number;
  advertisers: Advertiser[];
}

export const SpyGoogleAdsTab: React.FC = () => {
  const [data, setData] = useState<SpyData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [crawling, setCrawling] = useState<boolean>(false);
  const [searchDomain, setSearchDomain] = useState<string>('binize.com');
  const [filterScale, setFilterScale] = useState<string>('all');
  const [filterFormat, setFilterFormat] = useState<string>('all');
  const [filterCountry, setFilterCountry] = useState<string>('all');
  const [expandedAdvId, setExpandedAdvId] = useState<string | null>(null);

  const getCleanDomain = (d: string) => {
    return (d || '')
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/^www\./, '')
      .split('/')[0]
      .split('?')[0];
  };

  const cleanAdvName = (advName: string) => {
    const cleanDomain = getCleanDomain(searchDomain);
    if (!advName) return cleanDomain ? cleanDomain.charAt(0).toUpperCase() + cleanDomain.slice(1) : 'Advertiser';
    const bad = [
      'videocam', 'play_arrow', 'hide_image', 'image', 'visibility',
      'đã xác minh', 'verified', 'arrow_drop_down', 'check', 'close',
      'search', 'tune', 'more_vert', 'chevron_right', 'chevron_left',
      'image_not_supported', 'open_in_new', 'photo', 'movie', 'play_circle',
      'help', 'info'
    ];
    if (bad.includes(advName.trim().toLowerCase())) {
      return cleanDomain ? cleanDomain.charAt(0).toUpperCase() + cleanDomain.slice(1) : 'Advertiser';
    }
    return advName.trim();
  };

  const fetchSpyData = async (domainOverride?: string) => {
    const target = getCleanDomain(domainOverride || searchDomain);
    if (!target) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/spy/google-ads?domain=${encodeURIComponent(target)}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error('Error fetching spy data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLiveCrawl = async () => {
    const target = getCleanDomain(searchDomain);
    if (!target) return;
    setCrawling(true);
    try {
      const res = await fetch(`/api/spy/google-ads/crawl?domain=${encodeURIComponent(target)}`, {
        method: 'POST'
      });
      if (res.ok) {
        const json = await res.json();
        if (json.data) {
          setData(json.data);
        }
      }
    } catch (err) {
      console.error('Error live crawling:', err);
    } finally {
      setCrawling(false);
    }
  };

  useEffect(() => {
    fetchSpyData();
  }, []);

  const getScaleBadge = (count: number) => {
    if (count >= 10) {
      return {
        label: `🔥 Quy mô lớn (≥10 mẫu ads)`,
        detail: `${count} mẫu quảng cáo`,
        badgeClass: 'bg-orange-50 text-orange-700 border-orange-200'
      };
    }
    if (count >= 2) {
      return {
        label: `🟢 Đang chạy đều (2 - 9 ads)`,
        detail: `${count} mẫu quảng cáo`,
        badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200'
      };
    }
    return {
      label: `🟡 Mới thử nghiệm (1 ad)`,
      detail: `1 mẫu quảng cáo`,
      badgeClass: 'bg-amber-50 text-amber-700 border-amber-200'
    };
  };

  // Clean DOM icon texts from headlines and descriptions
  const cleanAdText = (txt: string) => {
    if (!txt) return '';
    const badTerms = [
      'videocam', 'play_arrow', 'hide_image', 'image', 'visibility',
      'đã xác minh', 'verified', 'arrow_drop_down', 'check', 'close',
      'search', 'tune', 'more_vert', 'chevron_right', 'chevron_left'
    ];
    let cleaned = txt;
    for (const term of badTerms) {
      const reg = new RegExp(`^\\s*${term}\\s*\\|?\\s*`, 'i');
      cleaned = cleaned.replace(reg, '');
    }
    return cleaned.trim();
  };

  const superScaleCount = (data?.advertisers || []).filter(a => a.ad_count >= 10).length;
  const winAdsCount = (data?.advertisers || []).filter(a => a.ad_count >= 2 && a.ad_count < 10).length;
  const testAdsCount = (data?.advertisers || []).filter(a => a.ad_count === 1).length;
  const isVerifiedZero = Boolean(
    data && (
      (data.total_ads === 0 && Boolean(data.updated_at)) ||
      (data as any).is_verified_zero ||
      (data as any).status === 'no_ads'
    )
  );

  const filteredAdvertisers = (data?.advertisers || []).filter(adv => {
    if (filterScale === 'super_scale' && adv.ad_count < 10) return false;
    if (filterScale === 'win_ads' && (adv.ad_count < 2 || adv.ad_count >= 10)) return false;
    if (filterScale === 'test' && adv.ad_count !== 1) return false;

    if (filterFormat !== 'all' && !adv.formats.includes(filterFormat)) return false;
    if (filterCountry !== 'all' && adv.country !== filterCountry) return false;

    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* HERO BANNER & CONTROL */}
      <section className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-indigo-800/60 rounded-3xl p-6 shadow-xl text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="px-3 py-1 rounded-full text-xs font-black bg-indigo-500 text-white shadow-md shadow-indigo-500/30 flex items-center gap-1.5">
                <Sparkles size={13} />
                <span>SPY GOOGLE ADS PRO</span>
              </span>
              {isVerifiedZero ? (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                  <CheckCircle2 size={13} />
                  <span>✅ Đã xác minh: 0 Ads đang chạy</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                  <ShieldCheck size={13} />
                  <span>Google Ads Transparency Center • Bóc Tách 100% Dữ Liệu Thật</span>
                </span>
              )}
            </div>
            <h2 className="text-2xl font-black tracking-tight text-white flex items-center gap-3">
              <span>Đã Phát Hiện {data?.advertisers?.length || 0} Đơn Vị Đang Chạy Ads Cho:</span>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400 font-mono">
                {getCleanDomain(searchDomain) || searchDomain}
              </span>
            </h2>
            <p className="text-xs text-slate-300 mt-1 max-w-3xl leading-relaxed">
              Tra cứu minh bạch từ Google Ads Transparency Center: nhận diện các media buyers/affiliates đang chạy kéo traffic về store,
              phân tích quy mô chiến dịch và bóc tách tiêu đề Text Ads, ảnh banner và video thực tế.
            </p>

            {/* Quick Domain Selector Pills */}
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span className="text-[11px] text-slate-400 font-semibold">Dự án mẫu:</span>
              <button
                onClick={() => {
                  setSearchDomain('binize.com');
                  fetchSpyData('binize.com');
                }}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
                  searchDomain === 'binize.com'
                    ? 'bg-orange-500 text-white shadow-md shadow-orange-500/30 ring-2 ring-orange-300'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
                }`}
              >
                <span>🚗 binize.com</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 font-mono">16 Advs</span>
              </button>

              <button
                onClick={() => {
                  setSearchDomain('letbricks.com');
                  fetchSpyData('letbricks.com');
                }}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
                  searchDomain === 'letbricks.com'
                    ? 'bg-amber-500 text-white shadow-md shadow-amber-500/30 ring-2 ring-amber-300'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
                }`}
              >
                <span>🧱 letbricks.com</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 font-mono">30 Advs</span>
              </button>

              <button
                onClick={() => {
                  setSearchDomain('fafreesebike.com');
                  fetchSpyData('fafreesebike.com');
                }}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
                  searchDomain === 'fafreesebike.com' || searchDomain === 'fafreesbike.com'
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/30 ring-2 ring-emerald-300'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
                }`}
              >
                <span>🚲 fafreesebike.com</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 font-mono">45 Advs (320 Ads)</span>
              </button>
            </div>
          </div>

          {/* Quick Domain Search & Live Crawl */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <div className="flex items-center bg-slate-800/90 border border-slate-700 rounded-2xl px-3 py-1.5 focus-within:border-indigo-500">
              <Search size={15} className="text-slate-400 mr-2" />
              <input
                type="text"
                value={searchDomain}
                onChange={e => setSearchDomain(e.target.value)}
                placeholder="Nhập domain"
                className="bg-transparent text-sm text-white focus:outline-none w-36 font-mono"
              />
            </div>
            <button
              onClick={() => fetchSpyData()}
              disabled={loading}
              className="px-4 py-2 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition shadow-lg shadow-indigo-600/30 cursor-pointer"
            >
              Làm Mới
            </button>
            <button
              onClick={handleLiveCrawl}
              disabled={crawling}
              className="flex items-center gap-1.5 px-4 py-2 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white text-xs font-bold transition shadow-lg shadow-emerald-500/25 cursor-pointer"
              title="Khởi động Playwright cào trực tiếp Google Ads Transparency Center"
            >
              <RefreshCw size={14} className={crawling ? 'animate-spin' : ''} />
              <span>{crawling ? 'Đang Vét Sâu...' : 'Quét Live Google'}</span>
            </button>
            <a
              href={`https://adstransparency.google.com/?region=anywhere&domain=${searchDomain}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 px-3 py-2 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium border border-slate-700 transition"
              title="Mở Google Ads Transparency gốc"
            >
              <span>Xem Web Gốc</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </section>

      {/* METRIC OVERVIEW CARDS */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider">Tổng Nhà Quảng Cáo</span>
            <Globe2 size={16} className="text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-slate-900 font-mono">
            {data?.total_advertisers || 0} Đơn Vị
          </div>
          <span className="text-[11px] text-slate-500 mt-0.5 block">
            {data?.total_ads || 0} mẫu quảng cáo đang được phân phối
          </span>
        </div>

        {/* Card 2: Quy mô lớn */}
        <div className="bg-white border border-orange-200 rounded-2xl p-4 shadow-sm bg-gradient-to-br from-orange-50/50 to-white">
          <div className="flex items-center justify-between text-orange-700 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider">🔥 Quy Mô Lớn (≥10 Ads)</span>
            <Flame size={16} className="text-orange-500" />
          </div>
          <div className="text-2xl font-black text-orange-600 font-mono">
            {superScaleCount} Đơn Vị
          </div>
          <span className="text-[11px] text-orange-600/80 mt-0.5 block font-medium">
            Chiến dịch lớn, ngân sách cao
          </span>
        </div>

        {/* Card 3: Đang chạy đều */}
        <div className="bg-white border border-emerald-200 rounded-2xl p-4 shadow-sm bg-gradient-to-br from-emerald-50/50 to-white">
          <div className="flex items-center justify-between text-emerald-700 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider">🟢 Đang Chạy Đều (2 - 9 Ads)</span>
            <Award size={16} className="text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-600 font-mono">
            {winAdsCount} Đơn Vị
          </div>
          <span className="text-[11px] text-emerald-600/80 mt-0.5 block font-medium">
            Duy trì ổn định & hiệu quả
          </span>
        </div>

        {/* Card 4: Mới thử nghiệm */}
        <div className="bg-white border border-amber-200 rounded-2xl p-4 shadow-sm bg-gradient-to-br from-amber-50/50 to-white">
          <div className="flex items-center justify-between text-amber-700 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider">🟡 Mới Thử Nghiệm (1 Ad)</span>
            <Layers size={16} className="text-amber-500" />
          </div>
          <div className="text-2xl font-black text-amber-600 font-mono">
            {testAdsCount} Đơn Vị
          </div>
          <span className="text-[11px] text-amber-600/80 mt-0.5 block font-medium">
            Vừa bắt đầu triển khai
          </span>
        </div>
      </section>

      {/* FILTER CONTROL BAR */}
      <section className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
        {/* Scale Filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-slate-500 mr-1">Quy Mô Ads:</span>
          <button
            onClick={() => setFilterScale('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
              filterScale === 'all' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Tất Cả ({data?.advertisers?.length || 0})
          </button>
          <button
            onClick={() => setFilterScale('super_scale')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1 ${
              filterScale === 'super_scale' ? 'bg-orange-600 text-white' : 'bg-orange-50 text-orange-700 hover:bg-orange-100 border border-orange-200'
            }`}
          >
            <Flame size={12} />
            <span>🔥 Quy mô lớn (≥10 ads) ({superScaleCount})</span>
          </button>
          <button
            onClick={() => setFilterScale('win_ads')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1 ${
              filterScale === 'win_ads' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
            }`}
          >
            <CheckCircle2 size={12} />
            <span>🟢 Đang chạy đều (2-9 ads) ({winAdsCount})</span>
          </button>
          <button
            onClick={() => setFilterScale('test')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1 ${
              filterScale === 'test' ? 'bg-amber-600 text-white' : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
            }`}
          >
            <span>🟡 Mới thử nghiệm (1 ad) ({testAdsCount})</span>
          </button>
        </div>

        {/* Formats & Country */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-300">
            <button
              onClick={() => setFilterFormat('all')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition ${
                filterFormat === 'all' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Tất Cả Định Dạng
            </button>
            <button
              onClick={() => setFilterFormat('search')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition ${
                filterFormat === 'search' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Search Text
            </button>
            <button
              onClick={() => setFilterFormat('image')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition ${
                filterFormat === 'image' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Display Banner
            </button>
            <button
              onClick={() => setFilterFormat('video')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition ${
                filterFormat === 'video' ? 'bg-white text-rose-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              YouTube Video
            </button>
          </div>

          {/* Country filter */}
          <select
            value={filterCountry}
            onChange={e => setFilterCountry(e.target.value)}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 border border-slate-300 text-slate-700 focus:outline-none"
          >
            <option value="all">Tất cả quốc gia</option>
            <option value="Việt Nam">🇻🇳 Việt Nam</option>
            <option value="Hoa Kỳ">🇺🇸 Hoa Kỳ</option>
            <option value="Hồng Kông">🇭🇰 Hồng Kông</option>
            <option value="Vương Quốc Anh">🇬🇧 Vương Quốc Anh</option>
            <option value="Ấn Độ">🇮🇳 Ấn Độ</option>
            <option value="Các Tiểu vương quốc Ả Rập">🇦🇪 UAE</option>
            <option value="Pakistan">🇵🇰 Pakistan</option>
          </select>
        </div>
      </section>

      {/* ADVERTISERS LIST TABLE OR 0 ADS VERIFIED MESSAGE OR LOADING OR NOT SCANNED */}
      {loading ? (
        <section className="bg-white border border-slate-200/90 rounded-3xl p-12 text-center shadow-sm flex flex-col items-center justify-center gap-3">
          <RefreshCw size={24} className="animate-spin text-indigo-600" />
          <span className="text-slate-600 font-semibold text-sm">
            Đang tra cứu dữ liệu Spy Google Ads cho {getCleanDomain(searchDomain)}...
          </span>
        </section>
      ) : isVerifiedZero ? (
        <section className="bg-white border border-slate-200 rounded-3xl p-10 text-center shadow-sm space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 size={28} />
          </div>
          <h3 className="text-base font-bold text-slate-900">
            ✅ Đã xác minh: Store hiện không có quảng cáo Google Ads nào đang chạy
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Domain <span className="font-mono font-bold text-emerald-700">{getCleanDomain(searchDomain)}</span> đã được bot Playwright quét thời gian thực trên Google Ads Transparency Center và xác nhận không có nhà quảng cáo nào đang chạy quảng cáo công khai.
          </p>
          <button
            onClick={handleLiveCrawl}
            disabled={crawling}
            className="px-4 py-2 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold text-xs cursor-pointer inline-flex items-center gap-2 transition"
          >
            <RefreshCw size={13} className={crawling ? 'animate-spin' : ''} />
            <span>{crawling ? 'Đang Quét Lại...' : '🔄 Quét Lại Trực Tiếp'}</span>
          </button>
        </section>
      ) : (!data || !data.updated_at || !data.advertisers || data.advertisers.length === 0) ? (
        <section className="bg-white border border-slate-200 rounded-3xl p-10 text-center shadow-sm space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-orange-100 text-orange-600 flex items-center justify-center mx-auto">
            <Flame size={28} />
          </div>
          <h3 className="text-base font-bold text-slate-900">
            Chưa có dữ liệu Spy Ads cho domain: <span className="font-mono text-orange-600">{getCleanDomain(searchDomain)}</span>
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Domain này chưa được quét trên Google Ads Transparency Center. Nhấn nút bên dưới để khởi chạy bot Playwright quét thời gian thực và bóc tách dữ liệu ads.
          </p>
          <button
            onClick={handleLiveCrawl}
            disabled={crawling}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 text-white font-bold text-xs shadow-md shadow-orange-500/25 cursor-pointer inline-flex items-center gap-2"
          >
            <RefreshCw size={14} className={crawling ? 'animate-spin' : ''} />
            <span>{crawling ? 'Đang Quét Google Ads...' : '⚡ Bắt Đầu Quét Live Google Ads'}</span>
          </button>
        </section>
      ) : (
        <section className="bg-white border border-slate-200/90 rounded-3xl shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h3 className="font-black text-slate-900 text-base flex items-center gap-2">
                <span>Danh Sách Nhà Quảng Cáo Google Cho {getCleanDomain(searchDomain)}</span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-mono font-bold">
                  {filteredAdvertisers.length} Đơn Vị Phù Hợp
                </span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Bóc tách chi tiết media buyer, quy mô mẫu quảng cáo và định dạng phân phối thực tế
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/90 text-slate-500 font-bold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                  <th className="py-3.5 px-4 w-[280px]">Nhà Quảng Cáo (Advertiser)</th>
                  <th className="py-3.5 px-4 w-[220px]">Quy Mô Chiến Dịch</th>
                  <th className="py-3.5 px-4 min-w-[240px]">Định Dạng Quảng Cáo</th>
                  <th className="py-3.5 px-4 text-center w-[120px]">Creatives</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredAdvertisers.map(adv => {
                  const isExpanded = expandedAdvId === adv.id;
                  const scale = getScaleBadge(adv.ad_count);
                  const displayName = cleanAdvName(adv.name);

                  return (
                    <React.Fragment key={adv.id}>
                      <tr className={`hover:bg-indigo-50/40 transition ${isExpanded ? 'bg-indigo-50/60' : ''}`}>
                        {/* Column 1: Advertiser */}
                        <td className="py-4 px-4 align-top">
                          <div className="flex items-start gap-3">
                            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 text-white font-black flex items-center justify-center flex-shrink-0 text-sm shadow-sm">
                              {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="font-bold text-slate-900 flex items-center gap-1.5 text-sm leading-snug">
                                <span>{displayName}</span>
                                {adv.is_verified && (
                                  <span title="Nhà quảng cáo đã xác minh danh tính với Google">
                                    <ShieldCheck size={14} className="text-blue-500 inline fill-blue-50" />
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                                <span>{adv.country_flag} {adv.country}</span>
                                <span>•</span>
                                <span className="font-mono text-slate-400">{adv.ad_count} Ads</span>
                              </div>
                              {adv.legal_name && adv.legal_name !== displayName && (
                                <div className="text-[10px] text-slate-400 truncate max-w-[200px]" title={adv.legal_name}>
                                  Pháp lý: {adv.legal_name}
                                </div>
                              )}
                              <a
                                href={adv.advertiser_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-0.5 mt-1"
                              >
                                <span>Xem Google Transparency</span>
                                <ExternalLink size={10} />
                              </a>
                            </div>
                          </div>
                        </td>

                        {/* Column 2: Scale Badge */}
                        <td className="py-4 px-4 align-top">
                          <div>
                            <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-xl text-xs font-bold border ${scale.badgeClass}`}>
                              {scale.label}
                            </span>
                            <div className="text-[10px] text-slate-400 mt-1.5 flex flex-col gap-0.5">
                              <span>Tổng cộng: <strong className="text-slate-700 font-mono">{adv.ad_count}</strong> mẫu ads</span>
                              <span>Gần nhất: <strong className="text-slate-600 font-mono">{adv.last_shown}</strong></span>
                            </div>
                          </div>
                        </td>

                        {/* Column 3: Formats */}
                        <td className="py-4 px-4 align-top">
                          <div className="flex flex-wrap gap-1.5">
                            {adv.formats.map(fmt => (
                              <span
                                key={fmt}
                                className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200"
                              >
                                {fmt === 'search' && <FileText size={12} className="text-blue-600" />}
                                {fmt === 'image' && <ImageIcon size={12} className="text-emerald-600" />}
                                {fmt === 'video' && <Video size={12} className="text-rose-600" />}
                                <span>
                                  {fmt === 'search' ? 'Search Text' : fmt === 'image' ? 'Display Banner' : 'YouTube Video'}
                                </span>
                              </span>
                            ))}
                          </div>
                        </td>

                        {/* Column 4: Action Button */}
                        <td className="py-4 px-4 align-top text-center">
                          <button
                            onClick={() => setExpandedAdvId(isExpanded ? null : adv.id)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1 mx-auto cursor-pointer ${
                              isExpanded
                                ? 'bg-slate-900 text-white'
                                : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
                            }`}
                          >
                            <span>{adv.creatives.length} Ads</span>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>
                        </td>
                      </tr>

                      {/* EXPANDED CREATIVES DRAWER */}
                      {isExpanded && (
                        <tr className="bg-slate-50/90 border-b border-indigo-200">
                          <td colSpan={4} className="p-4">
                            <div className="bg-white rounded-2xl border border-indigo-100 p-4 shadow-sm">
                              <h4 className="font-bold text-slate-900 text-xs mb-3 flex items-center justify-between">
                                <span className="flex items-center gap-1.5">
                                  <Sparkles size={13} className="text-indigo-600" />
                                  <span>Chi tiết các mẫu quảng cáo thực tế của {displayName}:</span>
                                </span>
                                <span className="text-[11px] text-slate-500 font-normal">
                                  Google Transparency Live Snapshot
                                </span>
                              </h4>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {adv.creatives.map(cr => {
                                  const headlineClean = cleanAdText(cr.headline);
                                  const descClean = cleanAdText(cr.description);

                                  return (
                                    <div
                                      key={cr.id}
                                      className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 hover:border-indigo-300 transition flex flex-col justify-between"
                                    >
                                      <div>
                                        <div className="flex items-center justify-between mb-1.5">
                                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-700">
                                            {cr.format_label}
                                          </span>
                                          <span className="text-[10px] text-slate-400 font-mono">
                                            {scale.label}
                                          </span>
                                        </div>

                                        {cr.image_url && (
                                          <div className="mb-2 rounded-lg overflow-hidden border border-slate-200 bg-slate-100 max-h-36 flex items-center justify-center">
                                            <img
                                              src={cr.image_url}
                                              alt={headlineClean}
                                              className="w-full h-auto object-cover max-h-36"
                                              onError={e => {
                                                (e.target as HTMLElement).style.display = 'none';
                                              }}
                                            />
                                          </div>
                                        )}

                                        <h5 className="font-bold text-slate-900 text-xs leading-snug">
                                          {headlineClean || `Quảng cáo Google: ${searchDomain}`}
                                        </h5>
                                        <p className="text-[11px] text-slate-600 mt-1 line-clamp-3">
                                          {descClean || `Mẫu quảng cáo hiển thị trên Google Ads cho ${searchDomain}`}
                                        </p>
                                      </div>

                                      <div className="mt-2.5 pt-2 border-t border-slate-200 flex items-center justify-between text-[11px]">
                                        <a
                                          href={cr.landing_page}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="text-indigo-600 hover:text-indigo-800 font-semibold truncate max-w-[240px] inline-flex items-center gap-1"
                                          title={cr.landing_page}
                                        >
                                          <span>{cr.landing_page}</span>
                                          <ExternalLink size={10} className="flex-shrink-0" />
                                        </a>
                                        <span className="text-[10px] text-slate-400 font-mono">
                                          {cr.last_shown}
                                        </span>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
