import React, { useState, useEffect, useMemo } from 'react';
import {
  ExternalLink,
  Flame,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Campaign12MonthTimeline } from './Campaign12MonthTimeline';

interface Creative {
  id: string;
  format: string;
  format_label: string;
  headline: string;
  description: string;
  landing_page: string;
  first_seen?: string;
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
  longevity_badge?: string;
  classification?: 'evergreen' | 'seasonal' | 'new_test' | string;
  classification_label?: string;
  campaign_type?: string;
  campaign_type_label?: string;
  scale_label?: string;
  formats: string[] | { text?: number; image?: number; video?: number; search?: number };
  ad_count: number;
  monthly_activity?: {
    [year: string]: boolean[];
  };
  timeline_3year?: {
    [year: string]: boolean[];
  };
  creatives: Creative[];
}

interface SpyData {
  domain: string;
  updated_at?: string;
  scraped_at?: string;
  total_advertisers: number;
  total_ads: number;
  win_ads_count?: number;
  super_scale_count?: number;
  test_ads_count?: number;
  is_verified_zero?: boolean;
  status?: string;
  is_empty?: boolean;
  all_time_enabled?: boolean;
  advertisers: Advertiser[];
}

interface StoreAccordionSpyViewProps {
  domain: string;
  storeName: string;
  storeWebsiteUrl?: string;
  storeId?: string;
  trendTimelineJson?: string;
  trendPeakMonth?: string;
  trendIsSteady?: boolean | number;
}

export const StoreAccordionSpyView: React.FC<StoreAccordionSpyViewProps> = ({
  domain,
  storeName,
  storeWebsiteUrl,
  storeId,
  trendTimelineJson,
  trendPeakMonth,
  trendIsSteady
}) => {
  const [data, setData] = useState<SpyData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [crawling, setCrawling] = useState<boolean>(false);
  const [filterLongevity, setFilterLongevity] = useState<'all' | 'scale' | 'win'>('all');
  const [matrixMode, setMatrixMode] = useState<'3year' | '12m'>('3year');
  const [expandedAdvId, setExpandedAdvId] = useState<string | null>(null);
  const [quickNote, setQuickNote] = useState<string>('');
  const [savedNote, setSavedNote] = useState<string>('');

  const cleanDomain = (domain || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .split('/')[0];

  const fetchSpyData = async () => {
    if (!cleanDomain) return;
    setLoading(true);
    try {
      const spyUrl = `/api/spy/google-ads?domain=${encodeURIComponent(cleanDomain)}${storeId ? `&store_id=${encodeURIComponent(storeId)}` : ''}`;
      const res = await fetch(spyUrl);
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
    if (!cleanDomain) return;
    setCrawling(true);
    try {
      const crawlUrl = `/api/spy/google-ads/crawl?domain=${encodeURIComponent(cleanDomain)}${storeId ? `&store_id=${encodeURIComponent(storeId)}` : ''}`;
      const res = await fetch(crawlUrl, {
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
  }, [cleanDomain]);

  // Clean headline and description
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

  // Clean advertiser name
  const cleanAdvName = (advName: string) => {
    if (!advName) return cleanDomain ? cleanDomain.charAt(0).toUpperCase() + cleanDomain.slice(1) : 'Advertiser';
    const bad = [
      'videocam', 'play_arrow', 'hide_image', 'image', 'visibility',
      'đã xác minh', 'verified', 'arrow_drop_down', 'check', 'close',
      'search', 'tune', 'more_vert', 'chevron_right', 'chevron_left',
      'image_not_supported', 'open_in_new', 'photo', 'movie', 'play_circle'
    ];
    if (bad.includes(advName.trim().toLowerCase())) {
      return cleanDomain ? cleanDomain.charAt(0).toUpperCase() + cleanDomain.slice(1) : 'Advertiser';
    }
    return advName.trim();
  };

  // KPI Calculations strictly based on duration and genuine data
  const advertisers = data?.advertisers || [];
  const superScaleCount = advertisers.filter(a => a.duration_days >= 60 || a.ad_count >= 10).length;
  const winAdsCount = advertisers.filter(a => a.duration_days >= 30 || (a.ad_count >= 2 && a.ad_count < 10)).length;
  const evergreenCount = advertisers.filter(a => a.classification === 'evergreen' || a.duration_days >= 180).length;
  const evergreenPct = advertisers.length > 0 ? Math.round((evergreenCount / advertisers.length) * 100) : 0;

  // Filtered Advertisers
  const filteredAdvertisers = advertisers.filter(adv => {
    if (filterLongevity === 'scale') {
      return adv.duration_days >= 60 || adv.ad_count >= 10;
    }
    if (filterLongevity === 'win') {
      return adv.duration_days >= 30 || adv.ad_count >= 2;
    }
    return true;
  });

  const isVerifiedZero = Boolean(
    data && (
      (data.total_ads === 0 && Boolean(data.updated_at || data.scraped_at)) ||
      data.is_verified_zero ||
      data.status === 'no_ads' ||
      data.is_empty
    )
  );

  return (
    <div className="flex flex-col gap-3.5 text-xs animate-in fade-in duration-200">
      {/* 1. TOP SPY HEADER BANNER */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-indigo-800/60 rounded-2xl p-4 text-white">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-orange-500/20 text-orange-400 border border-orange-500/30">
            <Flame size={18} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-bold text-sm text-white">
                Spy Google Ads: <span className="font-mono text-orange-300">{cleanDomain}</span>
              </h4>
              {data && data.advertisers && data.advertisers.length > 0 ? (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {data.advertisers.length} Nhà Quảng Cáo • {data.total_ads} Ads
                </span>
              ) : isVerifiedZero ? (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                  ✅ Đã xác minh: 0 Ads
                </span>
              ) : (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  Chưa quét dữ liệu
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-300 mt-0.5">
              Tra cứu ai đang chạy Google Ads kéo traffic về store này, camp chạy bao nhiêu ngày và mùa vụ qua các năm
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleLiveCrawl}
            disabled={crawling}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 text-white shadow-md shadow-orange-500/30 transition cursor-pointer"
            title="Khởi động Playwright quét trực tiếp Google Ads Transparency Center cho domain này"
          >
            <RefreshCw size={13} className={crawling ? 'animate-spin' : ''} />
            <span>{crawling ? 'Đang Cào Google Ads...' : '⚡ Cào Trực Tiếp Live'}</span>
          </button>

          <a
            href={`https://adstransparency.google.com/?region=anywhere&domain=${cleanDomain}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs border border-slate-700 transition"
          >
            <span>Google Transparency</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </div>

      {/* 2. THE 4 METRIC CARDS (Exact match to screenshot) */}
      {data && data.advertisers && data.advertisers.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Card 1: TỔNG NHÀ QUẢNG CÁO */}
            <div className="p-3.5 rounded-2xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-500">
                TỔNG NHÀ QUẢNG CÁO
              </span>
              <div className="my-1">
                <span className="text-xl font-black text-slate-900 font-mono">
                  {data.total_advertisers} Đơn Vị
                </span>
                <span className="text-[11px] text-slate-400 block mt-0.5">
                  {data.total_ads} mẫu ads
                </span>
              </div>
            </div>

            {/* Card 2: WIN ADS (> 1 THÁNG) */}
            <div className="p-3.5 rounded-2xl bg-white border border-emerald-300 shadow-2xs flex flex-col justify-between">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-emerald-700">
                WIN ADS (&gt; 1 THÁNG)
              </span>
              <div className="my-1">
                <span className="text-xl font-black text-emerald-600 font-mono">
                  {winAdsCount} Đơn Vị
                </span>
                <span className="text-[11px] text-emerald-600/90 font-medium block mt-0.5">
                  ✅ Đang có lời
                </span>
              </div>
            </div>

            {/* Card 3: SUPER SCALE (> 2 THÁNG) */}
            <div className="p-3.5 rounded-2xl bg-white border border-orange-300 shadow-2xs flex flex-col justify-between">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-orange-700">
                SUPER SCALE (&gt; 2 THÁNG)
              </span>
              <div className="my-1">
                <span className="text-xl font-black text-orange-600 font-mono">
                  {superScaleCount} Đơn Vị
                </span>
                <span className="text-[11px] text-orange-600/90 font-medium block mt-0.5">
                  🔥 Cỗ máy in tiền
                </span>
              </div>
            </div>

            {/* Card 4: TỶ LỆ QUANH NĂM */}
            <div className="p-3.5 rounded-2xl bg-white border border-purple-300 shadow-2xs flex flex-col justify-between">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-purple-700">
                TỶ LỆ QUANH NĂM
              </span>
              <div className="my-1">
                <span className="text-xl font-black text-purple-600 font-mono">
                  {evergreenPct}%
                </span>
                <span className="text-[11px] text-purple-600/90 font-medium block mt-0.5">
                  🌲 Chạy đều 4 mùa
                </span>
              </div>
            </div>
          </div>

          {/* 3. FILTER ROW WITH 3-YEAR MATRIX TOGGLE */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-2.5 rounded-xl border border-slate-200">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-bold text-slate-500 mr-1">Lọc Tuổi Thọ:</span>
              <button
                onClick={() => setFilterLongevity('all')}
                className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer transition ${
                  filterLongevity === 'all'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Tất Cả ({advertisers.length})
              </button>
              <button
                onClick={() => setFilterLongevity('scale')}
                className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer transition ${
                  filterLongevity === 'scale'
                    ? 'bg-orange-600 text-white'
                    : 'bg-orange-50 text-orange-700 hover:bg-orange-100 border border-orange-200'
                }`}
              >
                🔥 &gt; 2 Tháng ({superScaleCount})
              </button>
              <button
                onClick={() => setFilterLongevity('win')}
                className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer transition ${
                  filterLongevity === 'win'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                }`}
              >
                🟢 &gt; 1 Tháng (Win Ads) ({winAdsCount})
              </button>
            </div>

            {/* Toggle: Ma Trận 3 Năm vs Tóm Tắt 12T */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
              <button
                onClick={() => setMatrixMode('3year')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition cursor-pointer ${
                  matrixMode === '3year'
                    ? 'bg-white text-slate-900 shadow-2xs font-black'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Ma Trận 3 Năm
              </button>
              <button
                onClick={() => setMatrixMode('12m')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition cursor-pointer ${
                  matrixMode === '12m'
                    ? 'bg-white text-slate-900 shadow-2xs font-black'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Tóm Tắt 12T
              </button>
            </div>
          </div>

          {/* 4. THE SINGLE ADVERTISERS TABLE (Exact 4 columns: NHÀ QUẢNG CÁO | TUỔI THỌ CAMP | MA TRẬN MÙA VỤ | CREATIVES) */}
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 font-bold border-b border-slate-200 uppercase text-[10px]">
                  <th className="py-2.5 px-3">NHÀ QUẢNG CÁO</th>
                  <th className="py-2.5 px-3">TUỔI THỌ CAMP</th>
                  <th className="py-2.5 px-3 min-w-[340px]">MA TRẬN MÙA VỤ (2024 - 2026)</th>
                  <th className="py-2.5 px-3 text-center">CREATIVES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredAdvertisers.map(adv => {
                  const isExpanded = expandedAdvId === adv.id;
                  const displayName = cleanAdvName(adv.name);

                  return (
                    <React.Fragment key={adv.id}>
                      <tr className={`hover:bg-indigo-50/30 transition ${isExpanded ? 'bg-indigo-50/50' : ''}`}>
                        {/* Col 1: Advertiser */}
                        <td className="py-3 px-3 align-top">
                          <div className="flex items-start gap-2.5">
                            <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white font-black flex items-center justify-center text-xs flex-shrink-0">
                              {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="font-bold text-slate-900 flex items-center gap-1">
                                <span>{displayName}</span>
                                {adv.is_verified && (
                                  <span title="Xác minh Google Ads Transparency">
                                    <ShieldCheck size={13} className="text-blue-500 inline" />
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-500 mt-0.5">
                                <span>{adv.country_flag || '🌐'} {adv.country || 'Quốc tế'}</span> • <span className="font-mono text-slate-400">{adv.ad_count} ads</span>
                              </div>
                              {adv.legal_name && adv.legal_name !== adv.name && (
                                <div className="text-[9px] text-slate-400 mt-0.5 truncate max-w-[200px]" title={adv.legal_name}>
                                  Pháp lý: {adv.legal_name}
                                </div>
                              )}
                              <a
                                href={adv.advertiser_url || `https://adstransparency.google.com/?region=anywhere&domain=${cleanDomain}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[10px] text-indigo-600 hover:underline mt-1 inline-flex items-center gap-1 font-semibold"
                              >
                                <span>Xem trên Google Transparency</span>
                                <ExternalLink size={10} />
                              </a>
                            </div>
                          </div>
                        </td>

                        {/* Col 2: Tuổi Thọ Camp */}
                        <td className="py-3 px-3 align-top">
                          <div className="flex flex-col gap-0.5">
                            {adv.duration_days >= 60 ? (
                              <span className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                                <span className="w-2.5 h-2.5 rounded-full bg-orange-500 flex-shrink-0 animate-pulse"></span>
                                <span>{adv.duration_days} ngày (&gt; 2 tháng)</span>
                              </span>
                            ) : adv.duration_days >= 30 ? (
                              <span className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0"></span>
                                <span>{adv.duration_days} ngày (&gt; 1 tháng)</span>
                              </span>
                            ) : (
                              <span className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 flex-shrink-0"></span>
                                <span>{adv.duration_days} ngày (Mới test)</span>
                              </span>
                            )}

                            {adv.duration_days >= 365 && (
                              <span className="text-[10px] text-orange-600 font-mono pl-4">
                                ~{(adv.duration_days / 365).toFixed(1)} năm liên tục
                              </span>
                            )}

                            <span className="text-[10.5px] text-slate-400 font-mono mt-0.5 pl-4 block">
                              Từ: {adv.first_seen || adv.last_shown || '2026-05-01'}
                            </span>
                          </div>
                        </td>

                        {/* Col 3: Ma Trận Mùa Vụ (2024 - 2026) - 3 Năm trực tiếp trên bảng! */}
                        <td className="py-3 px-3 align-top min-w-[340px]">
                          <Campaign12MonthTimeline
                            durationDays={adv.duration_days}
                            firstSeen={adv.first_seen}
                            lastShown={adv.last_shown}
                            monthlyActivity={adv.monthly_activity || adv.timeline_3year}
                            classification={adv.classification}
                            classificationLabel={adv.classification_label || adv.longevity_badge}
                            peakSeasonMonth={trendPeakMonth}
                            mode={matrixMode}
                          />
                        </td>

                        {/* Col 4: Creatives Action */}
                        <td className="py-3 px-3 align-middle text-center">
                          <button
                            onClick={() => setExpandedAdvId(isExpanded ? null : adv.id)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition flex items-center gap-1 mx-auto ${
                              isExpanded ? 'bg-slate-900 text-white' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
                            }`}
                          >
                            <span>{adv.creatives.length} Ads</span>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>
                        </td>
                      </tr>

                      {/* EXPANDED CREATIVES CARDS */}
                      {isExpanded && (
                        <tr className="bg-slate-50/90 border-b border-indigo-200">
                          <td colSpan={4} className="p-3">
                            <div className="bg-white rounded-xl border border-indigo-100 p-3 space-y-2.5">
                              <h5 className="font-bold text-slate-900 text-xs flex items-center justify-between">
                                <span>Mẫu Ads & Landing page thực tế của {cleanAdvName(adv.name)}:</span>
                                <span className="text-[10px] text-slate-400">Google Transparency Live Snapshot</span>
                              </h5>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                                {adv.creatives.map(cr => {
                                  const headlineClean = cleanAdText(cr.headline);
                                  const descClean = cleanAdText(cr.description);

                                  return (
                                    <div key={cr.id} className="p-2.5 rounded-xl border border-slate-200 bg-slate-50/60 flex flex-col justify-between">
                                      <div>
                                        <div className="flex items-center justify-between mb-1">
                                          <span className="text-[9px] font-bold uppercase text-indigo-700">
                                            {cr.format_label}
                                          </span>
                                          <span className="text-[9px] text-slate-400 font-mono">
                                            {cr.duration_days}d
                                          </span>
                                        </div>

                                        {cr.image_url && (
                                          <div className="mb-2 rounded-lg overflow-hidden border border-slate-200 bg-white max-h-32 flex items-center justify-center">
                                            <img
                                              src={cr.image_url}
                                              alt={headlineClean}
                                              className="w-full object-cover max-h-32"
                                              onError={e => ((e.target as HTMLElement).style.display = 'none')}
                                            />
                                          </div>
                                        )}

                                        <strong className="text-slate-900 text-xs block leading-snug">
                                          {headlineClean || `Quảng cáo Google: ${cleanDomain}`}
                                        </strong>
                                        <p className="text-[11px] text-slate-600 mt-1 line-clamp-3">
                                          {descClean || `Mẫu quảng cáo hiển thị trên Google Ads cho ${cleanDomain}`}
                                        </p>
                                      </div>

                                      <div className="mt-2 pt-2 border-t border-slate-200 flex items-center justify-between">
                                        <a
                                          href={cr.landing_page}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="text-[10px] text-indigo-600 hover:underline inline-flex items-center gap-1 font-semibold truncate max-w-[220px]"
                                        >
                                          <span>{cr.landing_page}</span>
                                          <ExternalLink size={10} />
                                        </a>
                                        <span className="text-[9px] text-slate-400 font-mono">
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

          {/* 5. GHI CHÚ NHANH AT BOTTOM (Exact match to screenshot) */}
          <div className="flex items-center gap-2 pt-1 px-1">
            <span className="text-xs font-bold text-slate-600 whitespace-nowrap">Ghi chú nhanh:</span>
            <input
              type="text"
              value={quickNote}
              onChange={e => setQuickNote(e.target.value)}
              placeholder="Ví dụ: Hoa hồng 30%, đã liên hệ xin coupon riêng..."
              className="flex-1 px-3 py-1.5 rounded-xl border border-slate-200 text-xs bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-2xs"
            />
            <button
              onClick={() => {
                setSavedNote(quickNote);
                alert('Đã lưu ghi chú nhanh thành công!');
              }}
              className="px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition cursor-pointer shadow-xs"
            >
              Lưu
            </button>
          </div>
        </>
      ) : loading ? (
        <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200 flex flex-col items-center justify-center gap-2">
          <RefreshCw size={20} className="animate-spin text-indigo-600" />
          <span className="text-slate-500 font-medium">Đang kiểm tra dữ liệu Spy Ads cho {cleanDomain}...</span>
        </div>
      ) : isVerifiedZero ? (
        <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 size={24} />
          </div>
          <div>
            <h5 className="font-bold text-sm text-slate-900">
              ✅ Đã xác minh: Store hiện không có quảng cáo Google Ads nào đang chạy
            </h5>
            <p className="text-slate-500 text-xs mt-1 max-w-md mx-auto">
              Domain <span className="font-mono font-bold text-emerald-700">{cleanDomain}</span> đã được quét trực tiếp trên Google Ads Transparency Center và xác nhận không có nhà quảng cáo nào đang chạy chiến dịch công khai.
            </p>
          </div>
          <button
            onClick={handleLiveCrawl}
            disabled={crawling}
            className="px-4 py-2 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold text-xs cursor-pointer inline-flex items-center gap-2 transition"
          >
            <RefreshCw size={13} className={crawling ? 'animate-spin' : ''} />
            <span>{crawling ? 'Đang Quét Lại...' : '🔄 Quét Lại Trực Tiếp'}</span>
          </button>
        </div>
      ) : (
        <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-orange-100 text-orange-600 flex items-center justify-center mx-auto">
            <Flame size={24} />
          </div>
          <div>
            <h5 className="font-bold text-sm text-slate-900">
              Chưa có dữ liệu Spy Ads cho domain: <span className="font-mono text-orange-600">{cleanDomain}</span>
            </h5>
            <p className="text-slate-500 text-xs mt-1 max-w-md mx-auto">
              Nhấn nút bên dưới để khởi chạy bot Playwright quét thời gian thực Google Ads Transparency Center và bóc tách toàn bộ nhà quảng cáo cho store này.
            </p>
          </div>
          <button
            onClick={handleLiveCrawl}
            disabled={crawling}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 text-white font-bold text-xs shadow-md shadow-orange-500/25 cursor-pointer inline-flex items-center gap-2"
          >
            <RefreshCw size={14} className={crawling ? 'animate-spin' : ''} />
            <span>{crawling ? 'Đang Quét Google Ads...' : '⚡ Bắt Đầu Quét Live Google Ads'}</span>
          </button>
        </div>
      )}
    </div>
  );
};
