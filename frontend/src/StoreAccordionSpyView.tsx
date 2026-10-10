import React, { useState, useEffect } from 'react';
import {
  ExternalLink,
  Flame,
  CheckCircle2,
  RefreshCw,
  Video,
  FileText,
  Image as ImageIcon,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  AlertCircle
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

interface StoreAccordionSpyViewProps {
  domain: string;
  storeName: string;
  storeWebsiteUrl?: string;
  storeId?: string;
}

export const StoreAccordionSpyView: React.FC<StoreAccordionSpyViewProps> = ({
  domain,
  storeName,
  storeWebsiteUrl,
  storeId
}) => {
  const [data, setData] = useState<SpyData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [crawling, setCrawling] = useState<boolean>(false);
  const [filterScale, setFilterScale] = useState<string>('all');
  const [filterFormat, setFilterFormat] = useState<string>('all');
  const [expandedAdvId, setExpandedAdvId] = useState<string | null>(null);

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

  const getScaleBadge = (count: number) => {
    if (count >= 10) {
      return {
        label: `🔥 Quy mô lớn (≥10 mẫu ads)`,
        detail: `${count} mẫu quảng cáo`,
        badgeClass: 'bg-orange-500/15 text-orange-400 border-orange-500/30'
      };
    }
    if (count >= 2) {
      return {
        label: `🟢 Đang chạy đều (2 - 9 ads)`,
        detail: `${count} mẫu quảng cáo`,
        badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
      };
    }
    return {
      label: `🟡 Mới thử nghiệm (1 ad)`,
      detail: `1 mẫu quảng cáo`,
      badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    };
  };

  // Filter out DOM icon texts from headlines and descriptions
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

  // Clean advertiser name to avoid icon ligature text
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

  const filteredAdvertisers = (data?.advertisers || []).filter(adv => {
    if (filterScale === 'super_scale' && adv.ad_count < 10) return false;
    if (filterScale === 'win_ads' && (adv.ad_count < 2 || adv.ad_count >= 10)) return false;
    if (filterScale === 'test' && adv.ad_count !== 1) return false;
    if (filterFormat !== 'all' && !adv.formats.includes(filterFormat)) return false;
    return true;
  });

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

  return (
    <div className="flex flex-col gap-4 text-xs animate-in fade-in duration-200">
      {/* SPY HEADER BAR */}
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
                  {data.advertisers.length} Nhà Quảng Cáo • {data.total_ads} Ads Đang Chạy
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
              Tra cứu minh bạch từ Google Ads Transparency Center: các nhà quảng cáo đang chạy kéo traffic về store, định dạng và mẫu ads thực tế
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

      {/* METRIC OVERVIEW IF ADS EXIST */}
      {data && data.advertisers && data.advertisers.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-0.5">
                Tổng Nhà Quảng Cáo
              </span>
              <span className="text-base font-black text-slate-900 font-mono">
                {data.total_advertisers} Đơn Vị
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">{data.total_ads} mẫu ads</span>
            </div>

            <div className="p-3 rounded-xl bg-orange-50/60 border border-orange-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-orange-700 block mb-0.5">
                🔥 Quy mô lớn (≥10 ads)
              </span>
              <span className="text-base font-black text-orange-600 font-mono">
                {superScaleCount} Đơn Vị
              </span>
              <span className="text-[10px] text-orange-600/80 block mt-0.5">Độ phủ lớn & ngân sách cao</span>
            </div>

            <div className="p-3 rounded-xl bg-emerald-50/60 border border-emerald-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 block mb-0.5">
                🟢 Đang chạy đều (2-9 ads)
              </span>
              <span className="text-base font-black text-emerald-600 font-mono">
                {winAdsCount} Đơn Vị
              </span>
              <span className="text-[10px] text-emerald-600/80 block mt-0.5">Chiến dịch duy trì ổn định</span>
            </div>

            <div className="p-3 rounded-xl bg-amber-50/60 border border-amber-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 block mb-0.5">
                🟡 Mới thử nghiệm (1 ad)
              </span>
              <span className="text-base font-black text-amber-600 font-mono">
                {testAdsCount} Đơn Vị
              </span>
              <span className="text-[10px] text-amber-600/80 block mt-0.5">Vừa bắt đầu triển khai</span>
            </div>
          </div>

          {/* FILTERS */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-bold text-slate-500 mr-1">Lọc Quy Mô:</span>
              <button
                onClick={() => setFilterScale('all')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                  filterScale === 'all' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Tất Cả ({data.advertisers.length})
              </button>
              <button
                onClick={() => setFilterScale('super_scale')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                  filterScale === 'super_scale' ? 'bg-orange-600 text-white' : 'bg-orange-50 text-orange-700 hover:bg-orange-100 border border-orange-200'
                }`}
              >
                🔥 Quy mô lớn ({superScaleCount})
              </button>
              <button
                onClick={() => setFilterScale('win_ads')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                  filterScale === 'win_ads' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                }`}
              >
                🟢 Đang chạy đều ({winAdsCount})
              </button>
              <button
                onClick={() => setFilterScale('test')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                  filterScale === 'test' ? 'bg-amber-600 text-white' : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
                }`}
              >
                🟡 Mới thử nghiệm ({testAdsCount})
              </button>
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-bold text-slate-500 mr-1">Định Dạng:</span>
              <button
                onClick={() => setFilterFormat('all')}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition cursor-pointer ${
                  filterFormat === 'all' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Tất Cả
              </button>
              <button
                onClick={() => setFilterFormat('search')}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition cursor-pointer ${
                  filterFormat === 'search' ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                }`}
              >
                Search Text
              </button>
              <button
                onClick={() => setFilterFormat('image')}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition cursor-pointer ${
                  filterFormat === 'image' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                }`}
              >
                Display Banner
              </button>
              <button
                onClick={() => setFilterFormat('video')}
                className={`px-2 py-0.5 rounded text-[10px] font-semibold transition cursor-pointer ${
                  filterFormat === 'video' ? 'bg-rose-600 text-white' : 'bg-rose-50 text-rose-700 hover:bg-rose-100'
                }`}
              >
                YouTube Video
              </button>
            </div>
          </div>

          {/* ADVERTISERS TABLE */}
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 font-bold border-b border-slate-200 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Nhà Quảng Cáo (Advertiser)</th>
                  <th className="py-2.5 px-3">Quy Mô Chiến Dịch</th>
                  <th className="py-2.5 px-3">Định Dạng Quảng Cáo</th>
                  <th className="py-2.5 px-3 text-center">Creatives Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredAdvertisers.map(adv => {
                  const isExpanded = expandedAdvId === adv.id;
                  const scale = getScaleBadge(adv.ad_count);
                  const displayName = cleanAdvName(adv.name);

                  return (
                    <React.Fragment key={adv.id}>
                      <tr className={`hover:bg-indigo-50/30 transition ${isExpanded ? 'bg-indigo-50/50' : ''}`}>
                        {/* Col 1: Advertiser */}
                        <td className="py-3 px-3 align-top">
                          <div className="flex items-start gap-2.5">
                            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white font-black flex items-center justify-center text-xs flex-shrink-0">
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
                                <span>{adv.country_flag} {adv.country}</span> • <span className="font-mono text-slate-400">{adv.ad_count} ads</span>
                              </div>
                              {adv.legal_name && adv.legal_name !== adv.name && (
                                <div className="text-[9px] text-slate-400 mt-0.5 truncate max-w-[200px]" title={adv.legal_name}>
                                  Pháp lý: {adv.legal_name}
                                </div>
                              )}
                              <a
                                href={adv.advertiser_url}
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

                        {/* Col 2: Scale Badge */}
                        <td className="py-3 px-3 align-top">
                          <div>
                            <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold border ${scale.badgeClass}`}>
                              {scale.label}
                            </span>
                            <span className="text-[10px] text-slate-400 block mt-1">
                              Tổng cộng: <strong className="text-slate-700 font-mono">{adv.ad_count}</strong> mẫu đang phân phối
                            </span>
                          </div>
                        </td>

                        {/* Col 3: Ad Formats */}
                        <td className="py-3 px-3 align-top">
                          <div className="flex flex-wrap gap-1">
                            {adv.formats.map(fmt => (
                              <span
                                key={fmt}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200"
                              >
                                {fmt === 'search' && <FileText size={10} className="text-blue-600" />}
                                {fmt === 'image' && <ImageIcon size={10} className="text-emerald-600" />}
                                {fmt === 'video' && <Video size={10} className="text-rose-600" />}
                                <span>
                                  {fmt === 'search' ? 'Search Text' : fmt === 'image' ? 'Display Banner' : 'YouTube Video'}
                                </span>
                              </span>
                            ))}
                          </div>
                        </td>

                        {/* Col 4: Action */}
                        <td className="py-3 px-3 align-top text-center">
                          <button
                            onClick={() => setExpandedAdvId(isExpanded ? null : adv.id)}
                            className={`px-3 py-1.5 rounded-xl text-[11px] font-bold cursor-pointer transition flex items-center gap-1 mx-auto ${
                              isExpanded ? 'bg-slate-900 text-white' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
                            }`}
                          >
                            <span>{adv.creatives.length} Ads</span>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>
                        </td>
                      </tr>

                      {/* EXPANDED CREATIVES */}
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
                                            {scale.label}
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
