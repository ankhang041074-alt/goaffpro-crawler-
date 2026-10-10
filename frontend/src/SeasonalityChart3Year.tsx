import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  Flame,
  Calendar,
  Sparkles,
  Info,
  Clock,
  Layers,
  Award,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  CheckCircle2,
  BarChart3,
  Zap,
  ShieldCheck,
  Crown,
  Check,
  XCircle,
  Sun,
  Target
} from 'lucide-react';

export interface TimelinePoint {
  month: string; // "YYYY-MM"
  value: number; // 0 - 100
}

export interface SeasonalityChart3YearProps {
  timelineJson?: string;
  peakMonth?: string;
  isSteady?: boolean | number;
  storeName?: string;
  compact?: boolean;
}

/**
 * Color generator according to requirements:
 * 0-19: Xám/Thấp
 * 20-39: Xanh nhạt/Vừa
 * 40-59: Xanh chàm đậm/Cao
 * 60-79: Vàng cam/Rất cao
 * 80-100: Đỏ cam lửa/Đỉnh
 */
export const getSeasonalityColor = (value: number, isFuture: boolean = false) => {
  if (isFuture) {
    return {
      bg: 'bg-slate-50 border-dashed border-slate-300 text-slate-300',
      barBg: 'bg-slate-200/50',
      text: 'text-slate-300',
      label: 'Chưa tới',
      hex: '#e2e8f0'
    };
  }
  if (value === 0) {
    return {
      bg: 'bg-slate-100 border-slate-200 text-slate-400',
      barBg: 'bg-slate-200',
      text: 'text-slate-400',
      label: 'Rất thấp (0-19)',
      hex: '#cbd5e1'
    };
  }
  if (value >= 80) {
    return {
      bg: 'bg-gradient-to-br from-amber-500 via-orange-500 to-rose-600 border-orange-400 text-white shadow-xs',
      barBg: 'bg-gradient-to-t from-orange-500 to-rose-600',
      text: 'text-white font-bold',
      label: 'Đỉnh cao (80-100)',
      hex: '#e11d48',
      isPeak: true
    };
  }
  if (value >= 60) {
    return {
      bg: 'bg-amber-400 border-amber-500 text-amber-950 font-bold',
      barBg: 'bg-amber-400',
      text: 'text-amber-950 font-bold',
      label: 'Rất cao (60-79)',
      hex: '#f59e0b'
    };
  }
  if (value >= 40) {
    return {
      bg: 'bg-indigo-500 border-indigo-600 text-white font-semibold',
      barBg: 'bg-indigo-500',
      text: 'text-white font-semibold',
      label: 'Cao (40-59)',
      hex: '#6366f1'
    };
  }
  if (value >= 20) {
    return {
      bg: 'bg-sky-200 border-sky-300 text-sky-900',
      barBg: 'bg-sky-300',
      text: 'text-sky-900',
      label: 'Vừa (20-39)',
      hex: '#38bdf8'
    };
  }
  return {
    bg: 'bg-slate-200 border-slate-300 text-slate-700',
    barBg: 'bg-slate-300',
    text: 'text-slate-700',
    label: 'Thấp (0-19)',
    hex: '#94a3b8'
  };
};

/**
 * Extracts month number (1-12) from string like "2025-11 (100 pts)", "2026-05", or "Tháng 11".
 */
export const extractMonthNumber = (str?: string): number | null => {
  if (!str) return null;
  const matchDash = str.match(/-\s*(\d{2})/);
  if (matchDash) {
    const num = parseInt(matchDash[1], 10);
    if (num >= 1 && num <= 12) return num;
  }
  const matchThang = str.match(/Tháng\s*(\d+)/i);
  if (matchThang) {
    const num = parseInt(matchThang[1], 10);
    if (num >= 1 && num <= 12) return num;
  }
  return null;
};

export interface MonthStatus {
  month: number;
  value: number;
  isFuture: boolean;
  isActive: boolean; // value >= 20
  isPeak: boolean;
  isDormant: boolean; // value < 20 and not future
}

export interface YearSeasonalityVerdict {
  year: number;
  isCurrentYear: boolean;
  recordedMonths: number;
  activeMonthsCount: number;
  dormantMonthsCount: number;
  peakMonth: number;
  peakValue: number;
  avgValue: number;
  pattern: 'full_season' | 'seasonal' | 'dormant';
  badgeTitle: string; // e.g. "CHẠY FULL MÙA" | "CHẠY THEO MÙA" | "ÍT HOẠT ĐỘNG"
  badgeSubtitle: string; // e.g. "Quanh Năm (12/12 Tháng)" | "Tháng 10 - Tháng 12 (Q4)"
  badgeTone: 'green' | 'amber' | 'slate';
  seasonWindow: string;
  seasonName: string;
  verdictSentence: string;
  detailPoints: string[];
  strategyAdvice: string;
  monthlyStatuses: MonthStatus[];
}

export interface MultiYearAnalysisResult {
  years: YearSeasonalityVerdict[];
  overallVerdict: {
    title: string;
    badge: string;
    badgeTone: 'green' | 'amber' | 'sky';
    summary: string;
    strategy: string;
  };
}

/**
 * Calculates per-year seasonality verdict (Chạy Full Mùa vs Chạy Theo Mùa)
 * for each of the 3 years (2024, 2025, 2026).
 */
export function analyzeSeasonality3Years(
  timeline: TimelinePoint[],
  targetYears: number[],
  currentYear: number,
  currentMonth: number,
  isSteadyProp?: boolean | number,
  peakMonthProp?: string
): MultiYearAnalysisResult {
  const map = new Map<string, number>();
  timeline.forEach(p => {
    if (p && typeof p.month === 'string' && typeof p.value === 'number') {
      map.set(p.month, p.value);
    }
  });

  const propPeakMonth = extractMonthNumber(peakMonthProp);

  const years: YearSeasonalityVerdict[] = targetYears.map(year => {
    const isCurrentYear = year === currentYear;
    const recordedMonths = isCurrentYear ? Math.max(1, Math.min(12, currentMonth)) : 12;

    const monthlyStatuses: MonthStatus[] = [];
    for (let m = 1; m <= 12; m++) {
      const key = `${year}-${m.toString().padStart(2, '0')}`;
      const val = map.get(key) ?? 0;
      const isFuture = isCurrentYear && m > currentMonth;
      monthlyStatuses.push({
        month: m,
        value: val,
        isFuture,
        isActive: !isFuture && val >= 20,
        isDormant: !isFuture && val < 20,
        isPeak: false
      });
    }

    const recordedList = monthlyStatuses.filter(s => !s.isFuture);
    let peakValue = 0;
    let peakMonth = 1;

    recordedList.forEach(s => {
      if (s.value > peakValue) {
        peakValue = s.value;
        peakMonth = s.month;
      }
    });

    if (peakValue <= 0 && propPeakMonth && propPeakMonth <= recordedMonths) {
      peakMonth = propPeakMonth;
    }

    // Mark peak month
    monthlyStatuses.forEach(s => {
      if (!s.isFuture && s.month === peakMonth && peakValue > 0) {
        s.isPeak = true;
      }
    });

    const activeMonthsCount = recordedList.filter(s => s.isActive).length;
    const dormantMonthsCount = recordedMonths - activeMonthsCount;
    const sumVal = recordedList.reduce((acc, s) => acc + s.value, 0);
    const avgValue = recordedMonths > 0 ? Math.round(sumVal / recordedMonths) : 0;

    // Pattern determination
    const fullSeasonThreshold = Math.max(2, Math.round(recordedMonths * 0.65));
    let pattern: 'full_season' | 'seasonal' | 'dormant';
    let badgeTitle = '';
    let badgeSubtitle = '';
    let badgeTone: 'green' | 'amber' | 'slate' = 'slate';
    let seasonWindow = '';
    let seasonName = '';
    let verdictSentence = '';
    const detailPoints: string[] = [];
    let strategyAdvice = '';

    const activeMList = recordedList.filter(s => s.isActive).map(s => s.month);

    if (activeMonthsCount >= fullSeasonThreshold || (Boolean(isSteadyProp) && activeMonthsCount >= Math.round(recordedMonths * 0.5))) {
      pattern = 'full_season';
      badgeTone = 'green';
      badgeTitle = 'CHẠY FULL MÙA';
      badgeSubtitle = isCurrentYear
        ? `Duy Trì Đến Nay (${activeMonthsCount}/${recordedMonths}T)`
        : `Quanh Năm (${activeMonthsCount}/${recordedMonths}T)`;
      seasonWindow = isCurrentYear
        ? `Liên tục ${activeMonthsCount}/${recordedMonths} tháng đầu năm`
        : 'Cả 12 tháng quanh năm';
      seasonName = 'Evergreen Quanh Năm';
      verdictSentence = isCurrentYear
        ? `Năm ${year}: Chạy full mùa liên tục từ đầu năm đến nay (${activeMonthsCount}/${recordedMonths} tháng đều có khách tìm kiếm ổn định).`
        : `Năm ${year}: Chạy full mùa quanh năm. Sức mua và lưu lượng duy trì đều đặn suốt cả 12 tháng, không bị tắt đơn hay đứt gãy.`;

      if (peakValue >= 60 && peakValue >= avgValue * 1.35) {
        detailPoints.push(`Đạt đỉnh bùng nổ vào Tháng ${peakMonth} (${peakValue}đ), nhưng các tháng khác vẫn bán đều (${avgValue}đ TB).`);
      } else {
        detailPoints.push(`Lưu lượng rất đồng đều suốt cả năm (trung bình ${avgValue}đ/tháng), nhu cầu không bị phụ thuộc vào mùa vụ.`);
      }
      detailPoints.push(`${activeMonthsCount}/${recordedMonths} tháng hoạt động tích cực (≥20 điểm); ${dormantMonthsCount} tháng thấp.`);
      strategyAdvice = 'Rất thích hợp cho Affiliate setup Google Search Ads hoặc SEO dài hạn vì lúc nào cũng có đơn hàng, dòng tiền ổn định.';
    } else if (activeMonthsCount > 0 && peakValue >= 20) {
      pattern = 'seasonal';
      badgeTone = 'amber';

      const minM = Math.min(...activeMList);
      const maxM = Math.max(...activeMList);

      if (activeMList.length === 1) {
        seasonWindow = `Tháng ${activeMList[0]}`;
        if (activeMList[0] === 11) {
          seasonName = 'Vụ Mua Sắm Black Friday / Cyber Monday (T11)';
        } else if (activeMList[0] === 12) {
          seasonName = 'Mùa Giáng Sinh & Năm Mới (T12)';
        } else if (activeMList[0] >= 5 && activeMList[0] <= 8) {
          seasonName = `Mùa Hè & Du Lịch (Tháng ${activeMList[0]})`;
        } else if (activeMList[0] <= 3) {
          seasonName = `Đầu Năm & Tết (Tháng ${activeMList[0]})`;
        } else {
          seasonName = `Đỉnh Cao Điểm Tháng ${activeMList[0]}`;
        }
      } else {
        seasonWindow = `Tháng ${minM} - Tháng ${maxM}`;
        if (minM >= 9 || maxM >= 10) {
          seasonName = 'Mùa Vàng Mua Sắm Cuối Năm & BFCM (Q4)';
        } else if (minM >= 4 && maxM <= 8) {
          seasonName = 'Mùa Hè & Du Lịch (Q2 - Q3)';
        } else if (maxM <= 4) {
          seasonName = 'Đầu Năm & Mùa Xuân (Q1)';
        } else {
          seasonName = `Mùa Cao Điểm (Tập trung T${minM} - T${maxM})`;
        }
      }

      badgeTitle = 'CHẠY THEO MÙA';
      badgeSubtitle = seasonWindow;
      verdictSentence = `Năm ${year}: Chạy theo mùa vụ. Nhu cầu chỉ tập trung vào ${seasonWindow} (${seasonName}), đạt đỉnh ${peakValue}đ tại Tháng ${peakMonth}.`;
      detailPoints.push(`Chỉ có ${activeMonthsCount}/${recordedMonths} tháng vào vụ mua sắm chính; có tới ${dormantMonthsCount} tháng ngoài mùa ngủ đông / hạ nhiệt (<20đ).`);
      detailPoints.push(`Điểm số trung bình cả năm chỉ đạt ${avgValue}đ/tháng do phần lớn thời gian không có nhu cầu.`);
      strategyAdvice = `Affiliate chỉ nên dồn ngân sách ads và kéo traffic mạnh vào ${seasonWindow} để đón sóng chốt đơn. Tránh chạy ngoài mùa tốn chi phí.`;
    } else {
      pattern = 'dormant';
      badgeTone = 'slate';
      badgeTitle = 'ÍT HOẠT ĐỘNG';
      badgeSubtitle = 'Ngủ Đông / Chưa Rõ Mùa';
      seasonWindow = 'Dưới ngưỡng ghi nhận (<20đ)';
      seasonName = 'Nhu cầu thấp';
      verdictSentence = `Năm ${year}: Ít hoạt động / Chưa vào sóng (đỉnh cao nhất chỉ đạt ${peakValue}đ). Store chưa có lượt tìm kiếm đáng kể trên Google trong năm này.`;
      detailPoints.push(`Cả ${recordedMonths} tháng đều dưới 20 điểm tìm kiếm (ngủ đông).`);
      strategyAdvice = 'Cần kiểm tra thêm độ phủ trên các kênh Ads Spy bên dưới trước khi quyết định đầu tư traffic.';
    }

    return {
      year,
      isCurrentYear,
      recordedMonths,
      activeMonthsCount,
      dormantMonthsCount,
      peakMonth,
      peakValue,
      avgValue,
      pattern,
      badgeTitle,
      badgeSubtitle,
      badgeTone,
      seasonWindow,
      seasonName,
      verdictSentence,
      detailPoints,
      strategyAdvice,
      monthlyStatuses
    };
  });

  const fullCount = years.filter(y => y.pattern === 'full_season').length;
  const seasonalCount = years.filter(y => y.pattern === 'seasonal').length;

  let overallBadge = '🟢 EVERGREEN QUANH NĂM (3 NĂM)';
  let overallBadgeTone: 'green' | 'amber' | 'sky' = 'green';
  let overallTitle = 'Thương hiệu bán full mùa ổn định xuyên suốt 3 năm';
  let overallSummary = 'Dữ liệu 3 năm chứng minh đây là store Evergreen: Khách hàng mua sắm đều đặn cả 12 tháng mỗi năm, không phụ thuộc mùa vụ.';
  let overallStrategy = 'Khuyên dùng cho Affiliate: Thích hợp setup chiến dịch dài hạn, chạy Google Search Ads theo tên thương hiệu hoặc SEO/Content, doanh thu ổn định quanh năm.';

  if (fullCount >= 2 || (fullCount === 2 && seasonalCount <= 1)) {
    overallBadge = '🟢 EVERGREEN QUANH NĂM (3 NĂM)';
    overallBadgeTone = 'green';
    overallTitle = 'Thương hiệu bán full mùa ổn định xuyên suốt 3 năm';
    overallSummary = 'Dữ liệu 3 năm chứng minh đây là store Evergreen: Khách hàng mua sắm đều đặn các tháng trong năm, không phụ thuộc mùa vụ.';
    overallStrategy = 'Khuyên dùng cho Affiliate: Thích hợp setup chiến dịch dài hạn, chạy Google Search Ads theo tên thương hiệu hoặc SEO/Content, doanh thu ổn định quanh năm.';
  } else if (seasonalCount >= 2 || (seasonalCount === 1 && fullCount === 0)) {
    overallBadge = '🔥 THEO MÙA VỤ LẶP LẠI (SEASONAL)';
    overallBadgeTone = 'amber';
    overallTitle = 'Thương hiệu phụ thuộc mùa vụ cao điểm lặp lại';
    overallSummary = 'Dữ liệu 3 năm cho thấy chu kỳ mùa vụ lặp đi lặp lại rất rõ rệt: Store chỉ bùng nổ doanh số vào các tháng vụ mùa cố định trong năm, các tháng còn lại ngủ đông.';
    overallStrategy = 'Khuyên dùng cho Affiliate: Đừng duy trì ngân sách lớn quanh năm. Hãy xin mã coupon độc quyền trước 3-4 tuần, sau đó bung mạnh ngân sách vào đúng tháng cao điểm.';
  } else if (fullCount >= 1 && seasonalCount >= 1) {
    overallBadge = '⚡ CHUYỂN DỊCH: TỪ MÙA VỤ SANG QUANH NĂM';
    overallBadgeTone = 'sky';
    overallTitle = 'Mô hình chuyển dịch mở rộng độ phủ quanh năm';
    overallSummary = 'Store đang có bước chuyển dịch: Từ việc chỉ tập trung bán hàng theo vụ mùa sang mở rộng dòng sản phẩm bán đều các tháng trong năm.';
    overallStrategy = 'Khuyên dùng cho Affiliate: Test linh hoạt theo từng quý và theo dõi sát các mẫu quảng cáo mới được tung ra.';
  } else {
    overallBadge = '⚪ LƯU LƯỢNG MỚI KHỞI ĐỘNG';
    overallBadgeTone = 'sky';
    overallTitle = 'Thương hiệu mới hoặc lưu lượng đang tích lũy';
    overallSummary = 'Store chưa có chu kỳ tìm kiếm rõ nét trong 3 năm qua trên Google Trends.';
    overallStrategy = 'Khuyên dùng cho Affiliate: Đối chiếu thêm lịch sử quảng cáo Google Ads Spy bên cạnh để kiểm tra các kênh trả phí.';
  }

  return {
    years,
    overallVerdict: {
      title: overallTitle,
      badge: overallBadge,
      badgeTone: overallBadgeTone,
      summary: overallSummary,
      strategy: overallStrategy
    }
  };
}

/**
 * 3-Year Verdict Grid Component:
 * Directly answers the user question:
 * "sao đọc khó hiểu vậy 3 năm mỗi năm họ chạy theo mùa hay chạy full mùa đâu rồi"
 * Displays 3 clear cards for 2024, 2025, 2026 with visual dot strips, badges, and plain language summaries.
 */
export interface Seasonality3YearVerdictGridProps {
  timeline: TimelinePoint[];
  targetYears: number[];
  currentYear: number;
  currentMonth: number;
  isSteady?: boolean | number;
  peakMonth?: string;
  peakBadge?: string;
  bestQuarter?: string;
}

export const Seasonality3YearVerdictGrid: React.FC<Seasonality3YearVerdictGridProps> = ({
  timeline,
  targetYears,
  currentYear,
  currentMonth,
  isSteady,
  peakMonth,
  peakBadge,
  bestQuarter
}) => {
  const [hoveredDot, setHoveredDot] = useState<{
    year: number;
    month: number;
    value: number;
    statusText: string;
  } | null>(null);

  const analysis = useMemo(() => {
    return analyzeSeasonality3Years(
      timeline,
      targetYears,
      currentYear,
      currentMonth,
      isSteady,
      peakMonth
    );
  }, [timeline, targetYears, currentYear, currentMonth, isSteady, peakMonth]);

  if (analysis.years.length === 0) return null;

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 text-white rounded-2xl p-3.5 sm:p-4 border border-indigo-900/80 shadow-md flex flex-col gap-3">
      {/* 1. Header Banner: Main Title & Multi-Year synthesized badge */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2.5 border-b border-indigo-800/60">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-amber-500 via-rose-500 to-indigo-600 text-white shadow-xs flex-shrink-0">
            <Sparkles size={16} />
          </div>
          <div>
            <h4 className="text-xs sm:text-sm font-black text-white flex items-center gap-2 flex-wrap leading-tight">
              <span>ĐÁNH GIÁ 3 NĂM: MỖI NĂM CHẠY THEO MÙA HAY FULL MÙA?</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/25 text-indigo-300 border border-indigo-500/50">
                {targetYears.join(' • ')}
              </span>
            </h4>
            <p className="text-[11px] text-slate-300 mt-0.5">
              Đọc vị trực tiếp từ Google Trends từng năm: Phân biệt rõ ràng giữa <strong>Chạy Full Mùa (Evergreen quanh năm)</strong> và <strong>Chạy Theo Mùa (Thời vụ vụ mùa)</strong>.
            </p>
          </div>
        </div>

        {/* Synthesis Multi-Year Badge & Key KPIs */}
        <div className="flex items-center gap-2 flex-wrap self-start sm:self-center">
          <span
            className={`px-3 py-1 rounded-xl text-xs font-black border flex items-center gap-1.5 shadow-xs ${
              analysis.overallVerdict.badgeTone === 'green'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 ring-1 ring-emerald-500/30'
                : analysis.overallVerdict.badgeTone === 'amber'
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 ring-1 ring-amber-500/30'
                : 'bg-sky-500/20 text-sky-300 border-sky-500/40'
            }`}
          >
            <Award size={13} />
            <span>{analysis.overallVerdict.badge}</span>
          </span>

          {peakMonth && (
            <span className="px-2.5 py-1 rounded-xl text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">
              <Flame size={12} className="text-amber-400" />
              <span>Đỉnh: {peakMonth.split(' ')[0]}</span>
            </span>
          )}

          {bestQuarter && (
            <span className="px-2.5 py-1 rounded-xl text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1">
              <Target size={12} className="text-indigo-400" />
              <span>Quý Đỉnh: {bestQuarter}</span>
            </span>
          )}
        </div>
      </div>

      {/* 2. Three Dedicated Year Breakdown Cards (2024, 2025, 2026) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {analysis.years.map(yr => {
          const isGreen = yr.badgeTone === 'green';
          const isAmber = yr.badgeTone === 'amber';

          return (
            <div
              key={yr.year}
              className={`rounded-xl p-3 border flex flex-col justify-between gap-2.5 transition duration-200 relative overflow-hidden ${
                isGreen
                  ? 'bg-slate-900/90 border-emerald-500/50 hover:border-emerald-400'
                  : isAmber
                  ? 'bg-slate-900/90 border-amber-500/50 hover:border-amber-400'
                  : 'bg-slate-900/90 border-slate-700/80'
              }`}
            >
              {/* Subtle accent glow in top-right */}
              <div
                className={`absolute top-0 right-0 w-24 h-24 rounded-full blur-2xl opacity-15 pointer-events-none ${
                  isGreen ? 'bg-emerald-400' : isAmber ? 'bg-amber-400' : 'bg-slate-400'
                }`}
              />

              {/* Card Top: Year Header & Active/Dormant counter pill */}
              <div className="flex items-center justify-between gap-1 border-b border-slate-800 pb-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-base font-black text-white tracking-wide">
                    {yr.year}
                  </span>
                  {yr.isCurrentYear && (
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-indigo-500/30 text-indigo-200 border border-indigo-500/40 animate-pulse">
                      Hiện tại
                    </span>
                  )}
                </div>

                <span
                  className={`px-2 py-0.5 rounded-lg text-[10px] font-mono font-bold border ${
                    isGreen
                      ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                      : isAmber
                      ? 'bg-amber-950/60 text-amber-300 border-amber-700/60'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}
                  title={`${yr.activeMonthsCount} tháng có lượt tìm kiếm ≥20đ, ${yr.dormantMonthsCount} tháng thấp`}
                >
                  {yr.activeMonthsCount}/{yr.recordedMonths} Tháng Hoạt Động
                </span>
              </div>

              {/* Card Main Hero Badge: Big Bold Answer */}
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black tracking-wide border shadow-xs ${
                      isGreen
                        ? 'bg-gradient-to-r from-emerald-600 to-teal-700 text-white border-emerald-400'
                        : isAmber
                        ? 'bg-gradient-to-r from-amber-500 via-orange-600 to-rose-600 text-white border-orange-400'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}
                  >
                    {isGreen && <CheckCircle2 size={13} className="text-emerald-200" />}
                    {isAmber && <Flame size={13} className="text-amber-200" />}
                    {!isGreen && !isAmber && <Clock size={13} className="text-slate-400" />}
                    <span>{yr.badgeTitle}</span>
                  </span>
                </div>
                <div className="text-[11px] font-bold text-slate-300 flex items-center gap-1 pl-0.5">
                  <span>Mùa vụ:</span>
                  <span className={isGreen ? 'text-emerald-300' : isAmber ? 'text-amber-300' : 'text-slate-400'}>
                    {yr.badgeSubtitle}
                  </span>
                </div>
              </div>

              {/* 12-Month Mini Status Strip for this specific year */}
              <div className="bg-slate-950/70 rounded-xl p-2 border border-slate-800/80 flex flex-col gap-1">
                <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
                  <span>Chu kỳ 12 Tháng:</span>
                  <span className="font-mono text-slate-500">
                    Đỉnh: T{yr.peakMonth} ({yr.peakValue}đ)
                  </span>
                </div>

                <div className="grid grid-cols-12 gap-1 pt-0.5">
                  {yr.monthlyStatuses.map(st => {
                    const isFut = st.isFuture;
                    const isPk = st.isPeak;
                    const isAct = st.isActive;
                    const val = st.value;

                    let dotClass = 'bg-slate-800 text-slate-500 border-slate-700/60';
                    if (isFut) {
                      dotClass = 'border-dashed border-slate-700 text-slate-600 bg-transparent';
                    } else if (isPk) {
                      dotClass = 'bg-gradient-to-t from-orange-500 to-rose-600 text-white font-bold ring-1 ring-amber-300 shadow-2xs';
                    } else if (val >= 60) {
                      dotClass = 'bg-amber-400 text-slate-950 font-bold';
                    } else if (isAct) {
                      dotClass = 'bg-indigo-500 text-white font-semibold';
                    }

                    return (
                      <div
                        key={st.month}
                        onMouseEnter={() => {
                          if (!isFut) {
                            setHoveredDot({
                              year: yr.year,
                              month: st.month,
                              value: val,
                              statusText: isPk
                                ? 'Đỉnh cao nhất năm'
                                : isAct
                                ? 'Tháng hoạt động tốt'
                                : 'Tháng ngủ đông / thấp'
                            });
                          }
                        }}
                        onMouseLeave={() => setHoveredDot(null)}
                        className={`flex flex-col items-center justify-center py-1 rounded-md text-[9px] font-mono cursor-pointer transition transform hover:scale-110 relative ${dotClass}`}
                        title={`T${st.month}/${yr.year}: ${isFut ? 'Chưa tới' : `${val}đ ${isPk ? '(Đỉnh năm)' : isAct ? '(Hoạt động)' : '(Thấp)'}`}`}
                      >
                        <span className="leading-none text-[8px] opacity-75">T{st.month}</span>
                        <span className="leading-tight font-bold mt-0.5 text-[8.5px]">
                          {isFut ? '·' : val}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Direct Plain-Language Breakdown & Rationale */}
              <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1 text-[11px] leading-relaxed">
                <div className="text-slate-200">
                  <strong className={isGreen ? 'text-emerald-300' : isAmber ? 'text-amber-300' : 'text-slate-300'}>
                    👉 Kết luận {yr.year}:{' '}
                  </strong>
                  <span>{yr.verdictSentence}</span>
                </div>
                <div className="text-[10.5px] text-slate-400 border-t border-slate-800/80 pt-1 mt-0.5 flex flex-col gap-0.5">
                  {yr.detailPoints.map((pt, idx) => (
                    <div key={idx} className="flex items-start gap-1">
                      <span className="text-slate-500">•</span>
                      <span>{pt}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom Micro Strategy Advice */}
              <div className="text-[10px] text-indigo-200/90 bg-indigo-950/50 p-1.5 rounded-lg border border-indigo-800/40 flex items-start gap-1 leading-snug">
                <Zap size={11} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <span>{yr.strategyAdvice}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Hover Inspection Banner for 12-month dot strip */}
      {hoveredDot && (
        <div className="px-3 py-1.5 rounded-xl bg-indigo-950/90 border border-indigo-700/60 text-xs flex items-center justify-between text-indigo-200 animate-in fade-in duration-100">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">
              Tháng {hoveredDot.month}/{hoveredDot.year}:
            </span>
            <span className="font-mono font-bold text-amber-300">
              {hoveredDot.value} / 100 điểm tìm kiếm
            </span>
            <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-indigo-800 text-indigo-100 border border-indigo-600">
              {hoveredDot.statusText}
            </span>
          </div>
          <span className="text-[10px] text-slate-400">
            Dữ liệu đối chiếu chuẩn từ Google Trends
          </span>
        </div>
      )}

      {/* 3. Multi-Year Synthesized Actionable Advice Banner */}
      <div className="p-2.5 sm:p-3 rounded-xl bg-indigo-950/70 border border-indigo-700/60 flex items-start gap-2.5 text-xs text-indigo-100">
        <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
        <div className="flex flex-col gap-0.5">
          <div>
            <strong className="text-amber-300 font-bold mr-1">Tóm Lược Chiến Lược 3 Năm:</strong>
            <span className="text-slate-200">{analysis.overallVerdict.summary}</span>
          </div>
          <div className="text-[11px] text-indigo-300/90 mt-0.5">
            💡 {analysis.overallVerdict.strategy}
          </div>
        </div>
      </div>
    </div>
  );
};

export interface AdYearVerdict {
  year: number;
  pattern: 'full_season' | 'seasonal' | 'not_running';
  badgeTitle: string;
  badgeTone: 'green' | 'amber' | 'slate';
  quarterRange: string;
  monthRange: string;
  explanation: string;
}

export function analyzeCampaign3YearRun(
  durationDays: number,
  firstSeen?: string,
  lastShown?: string,
  peakSeasonMonth?: string
): {
  years: AdYearVerdict[];
  overallVerdictText: string;
  isEvergreenAll3Years: boolean;
} {
  const now = new Date();
  const currentYear = now.getFullYear(); // 2026
  const currentMonth = now.getMonth() + 1; // 10
  const currentQuarter = Math.floor((currentMonth - 1) / 3) + 1; // 4

  let end = lastShown ? new Date(lastShown) : now;
  if (isNaN(end.getTime())) end = now;

  let start: Date;
  if (firstSeen && firstSeen !== lastShown) {
    const parsedStart = new Date(firstSeen);
    start = !isNaN(parsedStart.getTime()) ? parsedStart : new Date(end.getTime() - durationDays * 86400000);
  } else {
    start = new Date(end.getTime() - durationDays * 86400000);
  }

  const targetYears = [2024, 2025, 2026];

  const years: AdYearVerdict[] = targetYears.map(y => {
    const yStart = new Date(y, 0, 1);
    const yEnd = new Date(y, 11, 31, 23, 59, 59);
    const effEnd = y === currentYear ? end : yEnd;

    // Check overlap
    if (start > effEnd) {
      return {
        year: y,
        pattern: 'not_running',
        badgeTitle: 'Chưa Chạy Ads',
        badgeTone: 'slate',
        quarterRange: '0/4 Quý',
        monthRange: 'Chưa chạy',
        explanation: `Chiến dịch ads chưa khởi động trong năm ${y}.`
      };
    }

    if (end < yStart) {
      return {
        year: y,
        pattern: 'not_running',
        badgeTitle: 'Đã Dừng Ads',
        badgeTone: 'slate',
        quarterRange: '0/4 Quý',
        monthRange: 'Đã dừng',
        explanation: `Chiến dịch ads đã kết thúc trước khi bước sang năm ${y}.`
      };
    }

    // Overlapping in year y
    const overlapStart = new Date(Math.max(start.getTime(), yStart.getTime()));
    const overlapEnd = new Date(Math.min(end.getTime(), effEnd.getTime()));

    const startM = overlapStart.getMonth() + 1;
    const endM = overlapEnd.getMonth() + 1;

    // Active quarters in year y
    const q1 = overlapStart <= new Date(y, 2, 31) && overlapEnd >= new Date(y, 0, 1);
    const q2 = overlapStart <= new Date(y, 5, 30) && overlapEnd >= new Date(y, 3, 1);
    const q3 = overlapStart <= new Date(y, 8, 30) && overlapEnd >= new Date(y, 6, 1);
    const q4 = overlapStart <= new Date(y, 11, 31) && overlapEnd >= new Date(y, 9, 1);

    const activeQList = [q1 && 'Q1', q2 && 'Q2', q3 && 'Q3', q4 && 'Q4'].filter(Boolean) as string[];
    const activeQCount = activeQList.length;

    const maxQInYear = y === currentYear ? currentQuarter : 4;
    const startedEarlier = start < yStart;
    const continuesLater = end > effEnd || (y === currentYear && durationDays >= 180);
    const daysInYear = Math.round((overlapEnd.getTime() - overlapStart.getTime()) / 86400000) + 1;

    if (startedEarlier && (end >= effEnd || daysInYear >= 240 || activeQCount >= maxQInYear)) {
      return {
        year: y,
        pattern: 'full_season',
        badgeTitle: y === currentYear ? 'Chạy Full Mùa (Đến nay)' : 'Chạy Full Mùa',
        badgeTone: 'green',
        quarterRange: `${activeQCount}/${maxQInYear} Quý (Evergreen)`,
        monthRange: `T${startM} - T${endM}`,
        explanation: y === currentYear
          ? `Duy trì liên tục từ đầu năm đến nay (${activeQCount}/${maxQInYear} Quý), ads đang phân phối ổn định.`
          : `Duy trì liên tục cả năm ${y} (Evergreen quanh năm), ads phân phối không ngừng nghỉ.`
      };
    } else if (activeQCount >= 4 || daysInYear >= 270) {
      return {
        year: y,
        pattern: 'full_season',
        badgeTitle: 'Chạy Full Mùa (Cả năm)',
        badgeTone: 'green',
        quarterRange: '4/4 Quý (Evergreen)',
        monthRange: `T${startM} - T${endM}`,
        explanation: `Chạy liên tục cả 4/4 Quý năm ${y} (Evergreen quanh năm), ads không tắt.`
      };
    } else if (startedEarlier && y === currentYear && activeQCount >= Math.max(1, maxQInYear - 1)) {
      return {
        year: y,
        pattern: 'full_season',
        badgeTitle: 'Chạy Full Mùa (Đến nay)',
        badgeTone: 'green',
        quarterRange: `${activeQCount}/${maxQInYear} Quý`,
        monthRange: `T${startM} - T${endM}`,
        explanation: `Chiến dịch duy trì liên tục từ các năm trước đến nay (${activeQCount} Quý năm ${y}).`
      };
    } else if (!startedEarlier && continuesLater && daysInYear >= 120) {
      return {
        year: y,
        pattern: 'full_season',
        badgeTitle: `Khởi Động & Chạy Đều (T${startM}-T${endM})`,
        badgeTone: 'green',
        quarterRange: `${activeQCount}/4 Quý (${activeQList.join(' - ')})`,
        monthRange: `T${startM} - T${endM}`,
        explanation: `Bắt đầu khởi động từ Tháng ${startM} (${activeQList[0]}) và duy trì liên tục không nghỉ sang các năm tiếp theo.`
      };
    } else {
      const qNames = activeQList.join(' - ');
      return {
        year: y,
        pattern: 'seasonal',
        badgeTitle: `Chạy Theo Mùa (${qNames})`,
        badgeTone: 'amber',
        quarterRange: `${activeQCount}/4 Quý (${qNames})`,
        monthRange: `Tháng ${startM} - Tháng ${endM}`,
        explanation: `Chạy theo mùa vụ: Tập trung vào ${activeQCount} Quý (${qNames}, từ T${startM} đến T${endM}).`
      };
    }
  });

  const fullCount = years.filter(y => y.pattern === 'full_season').length;
  const isEvergreenAll3Years = fullCount >= 3 || (fullCount >= 2 && durationDays >= 500);

  let overallVerdictText = '🟢 Super Evergreen: Chạy full mùa cả 3 năm liên tục!';
  if (fullCount >= 2) {
    overallVerdictText = '🟢 Bán full mùa quanh năm (>2 năm liên tục)';
  } else if (fullCount === 1) {
    overallVerdictText = '⚡ Chiến dịch dài hạn: Có năm chạy full mùa';
  } else if (durationDays < 30) {
    overallVerdictText = '⚡ Chiến dịch mới khởi động gần đây';
  } else {
    overallVerdictText = '🔥 Chiến dịch theo mùa vụ cao điểm';
  }

  return {
    years,
    overallVerdictText,
    isEvergreenAll3Years
  };
}

export const SeasonalityChart3Year: React.FC<SeasonalityChart3YearProps> = ({
  timelineJson,
  peakMonth,
  isSteady,
  storeName,
  compact = false
}) => {
  // 3 View Modes: 'bars' (Default: 3-Year Visual Comparison Bar Chart), 'matrix' (Heatmap Table), 'timeline' (2-5 Year Line Chart)
  const [viewMode, setViewMode] = useState<'bars' | 'matrix' | 'timeline'>('bars');
  const [hoveredMonth, setHoveredMonth] = useState<number | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{
    year: number;
    month: number;
    value: number;
    isPeakOfYear: boolean;
    isPeakOverall: boolean;
  } | null>(null);

  // Parse raw timeline data safely
  const timeline: TimelinePoint[] = useMemo(() => {
    if (!timelineJson) return [];
    try {
      const parsed = JSON.parse(timelineJson);
      if (Array.isArray(parsed)) {
        return parsed.filter(p => p && typeof p.month === 'string' && typeof p.value === 'number');
      }
      return [];
    } catch {
      return [];
    }
  }, [timelineJson]);

  // Current calendar boundary (system time: 2026-10)
  const now = new Date();
  const currentYear = now.getFullYear(); // 2026
  const currentMonth = now.getMonth() + 1; // 10

  // Determine the 3 target years to display: e.g. [2024, 2025, 2026]
  const targetYears = useMemo(() => {
    if (timeline.length === 0) return [currentYear - 2, currentYear - 1, currentYear];
    const availableYears = Array.from(new Set(timeline.map(p => parseInt(p.month.slice(0, 4)))))
      .filter(y => !isNaN(y))
      .sort((a, b) => a - b);

    if (availableYears.length >= 3) {
      // Pick last 3 years available, up to currentYear
      const valid = availableYears.filter(y => y <= currentYear);
      if (valid.length >= 3) return valid.slice(-3);
      return availableYears.slice(-3);
    }
    if (availableYears.length > 0) {
      // If we have 1 or 2 years, prioritize existing years and pad nicely around them
      const maxYear = Math.max(...availableYears);
      return [maxYear - 2, maxYear - 1, maxYear];
    }
    return [currentYear - 2, currentYear - 1, currentYear];
  }, [timeline, currentYear]);

  // Build 3-Year Matrix map: year -> month (1-12) -> value
  const matrixData = useMemo(() => {
    const map = new Map<string, number>();
    timeline.forEach(p => {
      map.set(p.month, p.value);
    });

    let overallMax = 0;
    const yearMaxMap = new Map<number, number>();

    targetYears.forEach(year => {
      let yMax = 0;
      for (let m = 1; m <= 12; m++) {
        const key = `${year}-${m.toString().padStart(2, '0')}`;
        const val = map.get(key) ?? 0;
        if (val > yMax) yMax = val;
        if (val > overallMax) overallMax = val;
      }
      yearMaxMap.set(year, yMax);
    });

    return { map, overallMax, yearMaxMap };
  }, [timeline, targetYears]);

  // Compute 3-Year Seasonal Averages per month (T1 -> T12)
  const monthAverages = useMemo(() => {
    const averages: { month: number; avg: number; count: number; max: number; values: { year: number; val: number; isFuture: boolean }[] }[] = [];
    for (let m = 1; m <= 12; m++) {
      let sum = 0;
      let count = 0;
      let maxVal = 0;
      const values: { year: number; val: number; isFuture: boolean }[] = [];

      targetYears.forEach(year => {
        const isFuture = year === currentYear && m > currentMonth;
        const key = `${year}-${m.toString().padStart(2, '0')}`;
        const val = matrixData.map.get(key) ?? 0;
        values.push({ year, val, isFuture });

        // Skip future unrecorded months in current year to not skew average downwards
        if (!isFuture && matrixData.map.has(key)) {
          sum += val;
          count++;
          if (val > maxVal) maxVal = val;
        }
      });

      averages.push({
        month: m,
        avg: count > 0 ? Math.round(sum / count) : 0,
        count,
        max: maxVal,
        values
      });
    }
    return averages;
  }, [targetYears, matrixData, currentYear, currentMonth]);

  // Find Peak Seasonal Month & Best Quarter
  const seasonalSummary = useMemo(() => {
    if (timeline.length === 0) return null;

    let highestAvgMonth = 1;
    let highestAvg = -1;
    monthAverages.forEach(item => {
      if (item.avg > highestAvg) {
        highestAvg = item.avg;
        highestAvgMonth = item.month;
      }
    });

    // Also check if peakMonth prop gives a specific known peak
    const propMonth = extractMonthNumber(peakMonth);
    const finalPeakMonth = (highestAvg <= 0 && propMonth) ? propMonth : highestAvgMonth;

    // Quarter averages
    const q1Avg = Math.round((monthAverages[0].avg + monthAverages[1].avg + monthAverages[2].avg) / 3);
    const q2Avg = Math.round((monthAverages[3].avg + monthAverages[4].avg + monthAverages[5].avg) / 3);
    const q3Avg = Math.round((monthAverages[6].avg + monthAverages[7].avg + monthAverages[8].avg) / 3);
    const q4Avg = Math.round((monthAverages[9].avg + monthAverages[10].avg + monthAverages[11].avg) / 3);

    const quarters = [
      { q: 'Q1 (T1 - T3)', avg: q1Avg, label: 'Đầu Năm / Tết & Xuân', id: 1, months: [1, 2, 3] },
      { q: 'Q2 (T4 - T6)', avg: q2Avg, label: 'Mùa Hè & Du Lịch', id: 2, months: [4, 5, 6] },
      { q: 'Q3 (T7 - T9)', avg: q3Avg, label: 'Thu / Tựu Trường', id: 3, months: [7, 8, 9] },
      { q: 'Q4 (T10 - T12)', avg: q4Avg, label: 'Mùa Vàng Mua Sắm (BFCM, Noel)', id: 4, months: [10, 11, 12] }
    ];
    quarters.sort((a, b) => b.avg - a.avg);
    const bestQuarter = quarters[0];

    // Marketer Plain-Language Insights
    let peakBadge = `🏔️ Đỉnh Cao Nhất: Tháng ${finalPeakMonth}`;
    let patternLabel = '🔥 Mùa Vụ Cao Điểm';
    let advice = '';

    if (isSteady) {
      peakBadge = '🟢 Evergreen: Đều Quanh Năm';
      patternLabel = '🟢 Evergreen Ổn Định';
      advice = 'Lưu lượng tìm kiếm và sức mua duy trì đồng đều suốt 12 tháng. Rất lý tưởng cho affiliate chạy Google Ads, SEO hoặc đặt banner dài hạn với dòng tiền ổn định quanh năm.';
    } else if (finalPeakMonth >= 10 && finalPeakMonth <= 12) {
      peakBadge = `🔥 Đỉnh Q4: Tháng ${finalPeakMonth} (Black Friday / Cyber Monday)`;
      patternLabel = '🔥 Mùa Vàng BFCM / Cuối Năm';
      advice = `Ngành hàng bùng nổ mạnh nhất vào dịp lễ hội mua sắm cuối năm (Quý 4 đạt trung bình ${q4Avg}đ/tháng). Lời khuyên: Hãy xin mã coupon độc quyền và setup chiến dịch từ đầu Tháng 10, bung mạnh ngân sách vào Tháng 11 & 12!`;
    } else if (finalPeakMonth >= 5 && finalPeakMonth <= 8) {
      peakBadge = `☀️ Đỉnh Hè: Tháng ${finalPeakMonth} (Summer Peak)`;
      patternLabel = '☀️ Mùa Hè & Du Lịch';
      advice = `Sản phẩm có nhu cầu tăng vọt vào mùa hè (Quý 2 - Quý 3). Affiliate nên bắt đầu đẩy mạnh traffic và kéo khách từ cuối Tháng 4, duy trì cao điểm xuyên suốt Tháng 6 đến Tháng 8!`;
    } else if (finalPeakMonth >= 1 && finalPeakMonth <= 3) {
      peakBadge = `🌸 Đỉnh Đầu Năm: Tháng ${finalPeakMonth} (New Year / Spring)`;
      patternLabel = '🌸 Đầu Năm / Mục Tiêu Mới';
      advice = `Nhu cầu khách hàng tăng vọt vào dịp đầu năm (lối sống mới, sức khỏe, phong cách hoặc chuẩn bị Tết). Thích hợp kéo traffic từ trước Tết và gặt hái doanh số trọn Quý 1!`;
    } else {
      advice = `Tháng ${finalPeakMonth} ghi nhận lượng tìm kiếm trung bình cao nhất (${highestAvg}đ). Quý bận rộn nhất là ${bestQuarter.q} (${bestQuarter.avg}đ).`;
    }

    return {
      highestAvgMonth: finalPeakMonth,
      highestAvg,
      bestQuarter,
      peakBadge,
      patternLabel,
      advice,
      quarterAverages: { q1Avg, q2Avg, q3Avg, q4Avg }
    };
  }, [timeline, monthAverages, isSteady, peakMonth]);

  if (timeline.length === 0) {
    return (
      <div className="py-6 px-4 rounded-2xl bg-slate-50 border border-slate-200 text-center flex flex-col items-center justify-center gap-1.5 text-slate-500">
        <Info size={18} className="text-slate-400" />
        <p className="text-xs font-semibold text-slate-600">Chưa có đủ dữ liệu Google Trends đa năm</p>
        <p className="text-[11px] text-slate-400 max-w-md">
          Hệ thống tuân thủ nguyên tắc đo lường thực tế từ Google Trends. Bấm nút &ldquo;Làm Mới Traffic & Trends&rdquo; để hệ thống quét dữ liệu chi tiết cho store này.
        </p>
      </div>
    );
  }

  // Quarters definitions for rendering
  const quarterDefs = [
    { name: 'Quý 1 (Q1)', months: [1, 2, 3], subtitle: 'Đầu Năm / Tết', id: 'Q1' },
    { name: 'Quý 2 (Q2)', months: [4, 5, 6], subtitle: 'Xuân - Hè', id: 'Q2' },
    { name: 'Quý 3 (Q3)', months: [7, 8, 9], subtitle: 'Thu / Tựu Trường', id: 'Q3' },
    { name: 'Quý 4 (Q4)', months: [10, 11, 12], subtitle: 'Mùa Vàng Mua Sắm', isGold: true, id: 'Q4' }
  ];

  return (
    <div className="flex flex-col gap-3 select-none animate-in fade-in duration-200">
      {/* 1. THE DIRECT 3-YEAR VERDICT BREAKDOWN (CHẠY THEO MÙA HAY FULL MÙA CHO TỪNG NĂM 2024, 2025, 2026) */}
      <Seasonality3YearVerdictGrid
        timeline={timeline}
        targetYears={targetYears}
        currentYear={currentYear}
        currentMonth={currentMonth}
        isSteady={isSteady}
        peakMonth={peakMonth}
        peakBadge={seasonalSummary?.peakBadge}
        bestQuarter={seasonalSummary?.bestQuarter.q}
      />

      {/* 2. VIEW SWITCHER TABS (Directly controls the charts/tables below) */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-1 pt-1">
        <div className="flex items-center gap-2">
          <BarChart3 size={15} className="text-indigo-600" />
          <h5 className="font-bold text-xs text-slate-800">
            Số Liệu & Biểu Đồ Đối Chiếu 12 Tháng Qua 3 Năm ({targetYears.join(' • ')})
          </h5>
        </div>

        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button
            onClick={() => setViewMode('bars')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              viewMode === 'bars'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
            title="Biểu đồ cột so sánh chu kỳ 12 tháng qua 3 năm (Trực quan nhất)"
          >
            <BarChart3 size={13} />
            <span>Biểu Đồ Cột 3 Năm</span>
          </button>

          <button
            onClick={() => setViewMode('matrix')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              viewMode === 'matrix'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
            title="Ma trận nhiệt dạng bảng số chi tiết"
          >
            <Calendar size={13} />
            <span>Ma Trận Nhiệt</span>
          </button>

          <button
            onClick={() => setViewMode('timeline')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              viewMode === 'timeline'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
            title="Biểu đồ đường liên tục 2-5 năm"
          >
            <TrendingUp size={13} />
            <span>Đường 2-5 Năm</span>
          </button>
        </div>
      </div>

      {/* 3. MODE 1: 3-YEAR SEASONAL BAR COMPARISON (DEFAULT & MOST INTUITIVE) */}
      {viewMode === 'bars' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Header Bar */}
          <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2">
              <BarChart3 size={15} className="text-indigo-600" />
              <h5 className="font-bold text-slate-800">
                So Sánh Cường Độ Tìm Kiếm 12 Tháng Qua 3 Năm ({targetYears.join(' • ')})
              </h5>
            </div>

            {/* Year Legend */}
            <div className="flex items-center gap-3 text-[11px] font-semibold text-slate-600">
              <div className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-sky-400"></span>
                <span>{targetYears[0]}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500"></span>
                <span>{targetYears[1]}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-rose-500"></span>
                <span>{targetYears[2]} (Hiện tại)</span>
              </div>
              <div className="flex items-center gap-1 pl-2 border-l border-slate-300 text-slate-400 font-normal">
                <Crown size={12} className="text-amber-500" />
                <span>Tháng Đỉnh</span>
              </div>
            </div>
          </div>

          {/* 12-Month Grouped Bar Canvas */}
          <div className="p-3 sm:p-4 overflow-x-auto">
            {/* Quarter Bands Header */}
            <div className="grid grid-cols-12 gap-1.5 sm:gap-2 min-w-[620px] mb-2 text-center">
              {quarterDefs.map(q => (
                <div
                  key={q.id}
                  className={`col-span-3 py-1 px-1.5 rounded-xl border text-[11px] font-bold flex items-center justify-center gap-1.5 ${
                    q.isGold
                      ? 'bg-amber-50 text-amber-900 border-amber-300'
                      : 'bg-slate-50 text-slate-600 border-slate-200'
                  }`}
                >
                  <span>{q.name}</span>
                  {q.isGold && <Flame size={12} className="text-amber-500" />}
                  <span className="text-[10px] font-normal text-slate-400 hidden md:inline">({q.subtitle})</span>
                </div>
              ))}
            </div>

            {/* Grouped Month Bars Columns */}
            <div className="grid grid-cols-12 gap-1.5 sm:gap-2 min-w-[620px] pt-1">
              {monthAverages.map(mItem => {
                const isPeak = seasonalSummary && mItem.month === seasonalSummary.highestAvgMonth;
                const isHovered = hoveredMonth === mItem.month;
                const isQ4 = mItem.month >= 10;

                return (
                  <div
                    key={mItem.month}
                    onMouseEnter={() => setHoveredMonth(mItem.month)}
                    onMouseLeave={() => setHoveredMonth(null)}
                    className={`flex flex-col items-center rounded-xl p-1.5 transition-all cursor-pointer ${
                      isHovered
                        ? 'bg-indigo-50/80 ring-2 ring-indigo-400 scale-[1.02]'
                        : isPeak
                        ? 'bg-amber-50/50 ring-1 ring-amber-300'
                        : isQ4
                        ? 'bg-amber-50/20'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    {/* Top: Peak crown or Average score */}
                    <div className="h-5 flex items-center justify-center">
                      {isPeak ? (
                        <span className="inline-flex items-center gap-0.5 px-1 rounded text-[9px] font-bold bg-amber-500 text-white animate-bounce shadow-2xs">
                          <Crown size={9} />
                          <span>ĐỈNH</span>
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] font-bold text-slate-500">
                          {mItem.avg > 0 ? `${mItem.avg}đ` : '—'}
                        </span>
                      )}
                    </div>

                    {/* Bar Area: 110px height */}
                    <div className="w-full h-28 bg-slate-100/70 rounded-lg p-1 flex items-end justify-center gap-1 border border-slate-200/80 relative overflow-hidden">
                      {/* Gridline at 50% and 80% */}
                      <div className="absolute inset-x-0 bottom-1/2 border-b border-dashed border-slate-200 pointer-events-none" />
                      <div className="absolute inset-x-0 bottom-[80%] border-b border-dashed border-rose-200 pointer-events-none" />

                      {/* 3 Bars for 3 Target Years */}
                      {mItem.values.map((v, vIdx) => {
                        const heightPct = v.isFuture ? 0 : Math.max(4, Math.min(100, v.val));
                        const styles = getSeasonalityColor(v.val, v.isFuture);
                        const isYearPeak = v.val === matrixData.yearMaxMap.get(v.year) && v.val > 0;

                        return (
                          <div
                            key={v.year}
                            className="flex-1 flex flex-col items-center justify-end h-full relative group/bar"
                            title={`${v.year}-T${mItem.month}: ${v.isFuture ? 'Chưa tới' : `${v.val} điểm`}`}
                          >
                            <div
                              style={{ height: `${heightPct}%` }}
                              className={`w-full max-w-[12px] rounded-t-sm transition-all duration-300 ${
                                v.isFuture
                                  ? 'border-t-2 border-dashed border-slate-300 bg-transparent'
                                  : styles.barBg
                              } ${isYearPeak ? 'ring-1 ring-amber-300' : ''}`}
                            />
                            {/* Tiny hover tip */}
                            <div className="absolute -top-6 bg-slate-900 text-white text-[9px] px-1 py-0.5 rounded font-mono font-bold opacity-0 group-hover/bar:opacity-100 transition pointer-events-none z-20 whitespace-nowrap">
                              {v.isFuture ? '—' : `${v.val}đ`}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Bottom: Month Label */}
                    <div className="mt-1.5 text-center">
                      <span className={`font-mono text-xs font-black ${
                        isPeak ? 'text-amber-600' : isHovered ? 'text-indigo-600' : 'text-slate-800'
                      }`}>
                        T{mItem.month}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Interactive Inspection Banner for Hovered Month */}
          <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between text-xs text-slate-600 gap-2">
            {hoveredMonth !== null ? (
              (() => {
                const item = monthAverages[hoveredMonth - 1];
                const isPeak = seasonalSummary && item.month === seasonalSummary.highestAvgMonth;
                const quarterName = item.month <= 3 ? 'Quý 1 (Đầu Năm)' : item.month <= 6 ? 'Quý 2 (Xuân - Hè)' : item.month <= 9 ? 'Quý 3 (Thu)' : 'Quý 4 (Mùa Vàng Mua Sắm)';

                return (
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-bold text-slate-900">
                      📌 Chi Tiết Tháng {item.month} ({quarterName}):
                    </span>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      {item.values.map(v => (
                        <span key={v.year} className="px-1.5 py-0.5 rounded bg-white border border-slate-200">
                          {v.year}: <strong className="text-slate-800">{v.isFuture ? '—' : `${v.val}đ`}</strong>
                        </span>
                      ))}
                      <span className="px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold">
                        TB 3 Năm: {item.avg}đ
                      </span>
                      {isPeak && (
                        <span className="px-2 py-0.5 rounded bg-rose-500 text-white font-bold animate-pulse">
                          🔥 Tháng Cao Điểm Nhất
                        </span>
                      )}
                    </div>
                  </div>
                );
              })()
            ) : (
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                <Info size={13} />
                <span>Rê chuột vào từng cột tháng để đối chiếu điểm số chi tiết từng năm và trung bình 3 năm.</span>
              </div>
            )}

            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="font-medium">Thang điểm: 0 (không tìm kiếm) ➔ 100 (đạt đỉnh toàn chu kỳ)</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. MODE 2: 3-YEAR SEASONAL HEATMAP MATRIX */}
      {viewMode === 'matrix' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Header Explanation Bar */}
          <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Calendar size={15} className="text-indigo-600" />
              <h5 className="font-bold text-xs text-slate-800">
                Ma Trận Điểm Số Theo Từng Tháng & Quý (Thang Điểm 0 - 100)
              </h5>
            </div>

            {/* Color Legend */}
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 flex-wrap">
              <span className="font-semibold text-slate-600 mr-1">Cường độ:</span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
                0-19 Thấp
              </span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-100 text-sky-800 border border-sky-200">
                20-39 Vừa
              </span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-900 border border-indigo-200 font-semibold">
                40-59 Cao
              </span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-200 text-amber-950 border border-amber-300 font-bold">
                60-79 Rất cao
              </span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gradient-to-r from-orange-500 to-rose-500 text-white font-bold">
                🔥 80-100 Đỉnh
              </span>
            </div>
          </div>

          {/* Heatmap Table */}
          <div className="overflow-x-auto p-3 sm:p-4">
            <table className="w-full border-collapse text-center min-w-[580px]">
              {/* Top Quarter Super-Headers */}
              <thead>
                <tr>
                  <th className="w-20 pb-2 text-left text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    Năm
                  </th>
                  {quarterDefs.map(q => (
                    <th
                      key={q.name}
                      colSpan={3}
                      className={`pb-2 px-1 text-center font-bold text-[11px] border-b-2 ${
                        q.isGold
                          ? 'border-amber-500 text-amber-800 bg-amber-50/50 rounded-t-lg'
                          : 'border-slate-200 text-slate-600'
                      }`}
                    >
                      <div className="flex items-center justify-center gap-1">
                        <span>{q.name}</span>
                        {q.isGold && <Flame size={12} className="text-amber-500 inline" />}
                      </div>
                      <span className="text-[9px] font-normal text-slate-400 block">{q.subtitle}</span>
                    </th>
                  ))}
                  <th className="w-20 pb-2 text-center text-[11px] font-bold text-slate-600 border-b-2 border-slate-200">
                    Đỉnh Năm
                  </th>
                </tr>

                {/* Month Sub-Headers (T1 -> T12) */}
                <tr className="border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                  <th className="py-2 text-left font-bold text-slate-400 text-xs"></th>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(m => {
                    const isCurrentM = m === currentMonth;
                    return (
                      <th
                        key={m}
                        className={`py-2 px-1 text-center font-mono ${
                          isCurrentM ? 'text-indigo-600 font-bold bg-indigo-50/40' : ''
                        } ${m >= 10 ? 'bg-amber-50/30' : ''}`}
                      >
                        <span className="inline-block">T{m}</span>
                        {isCurrentM && (
                          <span className="block text-[8px] font-sans font-bold text-indigo-500 leading-none">
                            Hiện tại
                          </span>
                        )}
                      </th>
                    );
                  })}
                  <th className="py-2 text-center font-mono text-[10px] text-slate-400">
                    Max / Năm
                  </th>
                </tr>
              </thead>

              {/* Data Rows for the 3 Years */}
              <tbody className="divide-y divide-slate-100">
                {targetYears.map(year => {
                  const yMax = matrixData.yearMaxMap.get(year) ?? 0;

                  return (
                    <tr key={year} className="hover:bg-slate-50/60 transition">
                      {/* Year Label */}
                      <td className="py-2.5 pr-2 text-left font-black text-xs font-mono text-slate-800 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="px-2 py-0.5 rounded-lg bg-slate-100 text-slate-800 border border-slate-200 font-bold">
                            {year}
                          </span>
                          {year === currentYear && (
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" title="Năm hiện tại"></span>
                          )}
                        </div>
                      </td>

                      {/* 12 Months Cells */}
                      {Array.from({ length: 12 }, (_, i) => i + 1).map(m => {
                        const key = `${year}-${m.toString().padStart(2, '0')}`;
                        const hasData = matrixData.map.has(key);
                        const val = matrixData.map.get(key) ?? 0;
                        const isFuture = year === currentYear && m > currentMonth;
                        const isOverallPeak = val === matrixData.overallMax && val > 0;
                        const isYearPeak = val === yMax && yMax > 0;
                        const styles = getSeasonalityColor(val, isFuture);

                        return (
                          <td
                            key={m}
                            className={`p-1 align-middle transition ${m >= 10 ? 'bg-amber-50/20' : ''}`}
                            onMouseEnter={() => {
                              if (!isFuture && hasData) {
                                setHoveredCell({
                                  year,
                                  month: m,
                                  value: val,
                                  isPeakOfYear: isYearPeak,
                                  isPeakOverall: isOverallPeak
                                });
                              }
                            }}
                            onMouseLeave={() => setHoveredCell(null)}
                          >
                            <div
                              className={`h-9 rounded-xl border flex flex-col items-center justify-center transition-all cursor-pointer transform hover:scale-105 hover:z-10 relative ${
                                styles.bg
                              }`}
                              title={`${year}-${m.toString().padStart(2, '0')}: ${isFuture ? 'Chưa tới' : `${val} điểm`}`}
                            >
                              <span className={`font-mono text-xs ${styles.text}`}>
                                {isFuture ? '—' : val}
                              </span>
                              {isOverallPeak && (
                                <span className="absolute -top-1 -right-1 text-[9px] leading-none" title="Đỉnh cao nhất toàn chu kỳ">
                                  🔥
                                </span>
                              )}
                              {!isOverallPeak && isYearPeak && val >= 50 && (
                                <span className="absolute -top-1 -right-1 text-[8px] leading-none" title="Đỉnh của năm">
                                  ⭐
                                </span>
                              )}
                            </div>
                          </td>
                        );
                      })}

                      {/* Year Peak summary column */}
                      <td className="py-2.5 px-1 align-middle">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">
                          {yMax > 0 ? `${yMax}đ` : '—'}
                        </span>
                      </td>
                    </tr>
                  );
                })}

                {/* 3-YEAR AVERAGE SEASONAL ROW (Chỉ Số Mùa Vụ Chu Kỳ) */}
                <tr className="bg-gradient-to-r from-indigo-50/60 via-purple-50/40 to-indigo-50/60 font-bold border-t-2 border-indigo-200">
                  <td className="py-3 pr-2 text-left font-bold text-xs text-indigo-900 whitespace-nowrap">
                    <div className="flex flex-col">
                      <span>TB 3 Năm</span>
                      <span className="text-[9px] font-normal text-indigo-600">Seasonality</span>
                    </div>
                  </td>

                  {monthAverages.map(item => {
                    const isPeakAvg = seasonalSummary && item.month === seasonalSummary.highestAvgMonth;
                    return (
                      <td key={item.month} className="p-1 align-middle">
                        <div
                          className={`h-9 rounded-xl border flex flex-col items-center justify-center ${
                            isPeakAvg
                              ? 'bg-gradient-to-br from-indigo-600 to-violet-700 text-white border-indigo-700 shadow-xs ring-1 ring-indigo-400'
                              : item.avg >= 50
                              ? 'bg-indigo-100 border-indigo-200 text-indigo-900'
                              : 'bg-white border-slate-200 text-slate-700'
                          }`}
                        >
                          <span className="font-mono text-xs font-bold leading-tight">
                            {item.avg}đ
                          </span>
                          {isPeakAvg && (
                            <span className="text-[8px] font-sans font-bold leading-none text-amber-300">
                              Đỉnh TB
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}

                  {/* Overall Peak Avg */}
                  <td className="py-3 px-1 align-middle">
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-mono font-bold bg-indigo-600 text-white shadow-2xs">
                      🏆 T{seasonalSummary?.highestAvgMonth}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Cell Hover Detail Tooltip Banner */}
          <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 flex-wrap gap-2">
            {hoveredCell ? (
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">
                  📌 Tháng {hoveredCell.month}/{hoveredCell.year}:
                </span>
                <span className="font-mono font-bold text-indigo-600">
                  {hoveredCell.value} / 100 điểm tìm kiếm
                </span>
                {hoveredCell.isPeakOverall && (
                  <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-rose-500 text-white">
                    🔥 Đỉnh Cao Nhất 3 Năm
                  </span>
                )}
                {hoveredCell.isPeakOfYear && !hoveredCell.isPeakOverall && (
                  <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                    ⭐ Đỉnh Của Năm {hoveredCell.year}
                  </span>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                <Info size={13} />
                <span>Rê chuột vào từng ô tháng để xem chi tiết điểm số và độ bứt phá doanh số.</span>
              </div>
            )}

            <div className="flex items-center gap-2 text-[11px] text-slate-500 font-medium">
              <span>Quý mạnh nhất: <strong className="text-indigo-700">{seasonalSummary?.bestQuarter.q}</strong></span>
              <span>•</span>
              <span>Đỉnh chu kỳ: <strong className="text-amber-600">{seasonalSummary?.peakBadge}</strong></span>
            </div>
          </div>
        </div>
      )}

      {/* 4. MODE 3: CONTINUOUS TIMELINE LINE CHART (MACRO 2-5 YEAR VIEW) */}
      {viewMode === 'timeline' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp size={15} className="text-indigo-600" />
              <h5 className="font-bold text-xs text-slate-800">
                Biểu Đồ Xu Hướng Tìm Kiếm Toàn Thời Gian (2-5 Năm Liên Tục)
              </h5>
            </div>
            {peakMonth && (
              <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                🔥 Tháng cao điểm: {peakMonth}
              </span>
            )}
          </div>

          {/* Responsive SVG Chart */}
          {(() => {
            const height = 130;
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
              <div className="w-full overflow-x-auto">
                <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto min-w-[540px] select-none">
                  <defs>
                    <linearGradient id={`timeline-grad-${storeName || 'trends'}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Grid Lines */}
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

                  {/* Area fill */}
                  <path d={areaD} fill={`url(#timeline-grad-${storeName || 'trends'})`} />

                  {/* Line stroke */}
                  <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />

                  {/* Dots */}
                  {points.map((p, idx) => (
                    <g key={idx} className="cursor-pointer">
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r={p.value === peakVal && peakVal > 0 ? 4 : 2}
                        fill={p.value === peakVal && peakVal > 0 ? '#f59e0b' : '#6366f1'}
                      />
                      <title>{`${p.month}: ${p.value} pts`}</title>
                    </g>
                  ))}

                  {/* Peak Point label */}
                  {peakPoint && (
                    <g>
                      <circle cx={peakPoint.x} cy={peakPoint.y} r={7} fill="none" stroke="#f59e0b" strokeWidth="1.5" opacity="0.8" />
                      <text
                        x={peakPoint.x}
                        y={Math.max(12, peakPoint.y - 8)}
                        textAnchor="middle"
                        fontSize="9.5"
                        fontWeight="bold"
                        fill="#d97706"
                      >
                        🔥 {peakPoint.month} ({peakPoint.value}đ)
                      </text>
                    </g>
                  )}

                  {/* Year X-axis ticks */}
                  {yearMarkers.map((m, idx) => (
                    <text key={idx} x={m.x} y={height - 4} textAnchor="middle" fontSize="9.5" fontWeight="bold" fill="#64748b">
                      {m.label}
                    </text>
                  ))}
                </svg>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};

/**
 * Compact 12-Month Seasonality Mini Strip
 * Designed for quick inline placement (e.g. accordion headers or spy tab overview)
 * so marketers see the full year curve in 1 second without clicking to expand!
 */
export interface SeasonalityMiniStripProps {
  timelineJson?: string;
  peakMonth?: string;
  isSteady?: boolean | number;
  showVerdictPills?: boolean;
}

export const SeasonalityMiniStrip: React.FC<SeasonalityMiniStripProps> = ({
  timelineJson,
  peakMonth,
  isSteady,
  showVerdictPills = true
}) => {
  const points = useMemo(() => {
    if (!timelineJson) return [];
    try {
      const parsed = JSON.parse(timelineJson);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [timelineJson]);

  const monthAverages = useMemo(() => {
    const avgs: number[] = new Array(12).fill(0);
    const counts: number[] = new Array(12).fill(0);
    points.forEach((p: any) => {
      if (p && typeof p.month === 'string' && typeof p.value === 'number') {
        const m = parseInt(p.month.slice(5, 7), 10) - 1;
        if (m >= 0 && m < 12) {
          avgs[m] += p.value;
          counts[m] += 1;
        }
      }
    });
    return avgs.map((sum, idx) => (counts[idx] > 0 ? Math.round(sum / counts[idx]) : 0));
  }, [points]);

  const maxVal = Math.max(...monthAverages, 1);
  const peakM = extractMonthNumber(peakMonth) || (monthAverages.indexOf(Math.max(...monthAverages)) + 1);

  const miniAnalysis = useMemo(() => {
    if (!showVerdictPills || points.length === 0) return null;
    const now = new Date();
    return analyzeSeasonality3Years(
      points,
      [2024, 2025, 2026],
      now.getFullYear(),
      now.getMonth() + 1,
      isSteady,
      peakMonth
    );
  }, [showVerdictPills, points, isSteady, peakMonth]);

  if (points.length === 0) return null;

  return (
    <div className="flex items-center gap-2 bg-white/95 border border-slate-200/90 rounded-xl px-2.5 py-1.5 shadow-2xs flex-wrap">
      {/* 12-Month Mini Curve */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-bold text-slate-500 whitespace-nowrap">
          Chu kỳ 12T:
        </span>
        <div className="flex items-end gap-1 h-5">
          {monthAverages.map((val, idx) => {
            const m = idx + 1;
            const isPeak = m === peakM && val >= 50;
            const heightPct = Math.max(15, Math.min(100, Math.round((val / maxVal) * 100)));

            return (
              <div
                key={m}
                className="group/mini relative flex flex-col items-center justify-end h-full"
                title={`Tháng ${m}: ${val} điểm TB ${isPeak ? '(Đỉnh cao điểm)' : ''}`}
              >
                <div
                  style={{ height: `${heightPct}%` }}
                  className={`w-1.5 sm:w-2 rounded-t-xs transition-all ${
                    isPeak
                      ? 'bg-rose-500 ring-1 ring-amber-300'
                      : val >= 60
                      ? 'bg-amber-400'
                      : val >= 35
                      ? 'bg-indigo-500'
                      : 'bg-slate-300'
                  }`}
                />
                {/* Tooltip */}
                <div className="absolute -top-7 bg-slate-900 text-white text-[9px] px-1 py-0.5 rounded font-mono font-bold opacity-0 group-hover/mini:opacity-100 transition pointer-events-none z-30 whitespace-nowrap shadow-xs">
                  T{m}: {val}đ
                </div>
              </div>
            );
          })}
        </div>
        <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">
          🔥 Đỉnh: T{peakM}
        </span>
      </div>

      {/* 3-Year Instant Verdict Pills */}
      {showVerdictPills && miniAnalysis && miniAnalysis.years.length > 0 && (
        <div className="flex items-center gap-1 pl-2 border-l border-slate-200 flex-wrap">
          <span className="text-[10px] font-bold text-slate-400">3 Năm:</span>
          {miniAnalysis.years.map(yr => (
            <span
              key={yr.year}
              className={`px-1.5 py-0.2 rounded-md text-[9.5px] font-bold border transition ${
                yr.badgeTone === 'green'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                  : yr.badgeTone === 'amber'
                  ? 'bg-amber-50 text-amber-900 border-amber-300'
                  : 'bg-slate-100 text-slate-600 border-slate-200'
              }`}
              title={`${yr.year}: ${yr.verdictSentence}`}
            >
              <span>{yr.year}: </span>
              {yr.pattern === 'full_season' ? (
                <span className="text-emerald-700">Full Mùa 🟢</span>
              ) : yr.pattern === 'seasonal' ? (
                <span className="text-amber-800">Theo Mùa 🔥 ({yr.seasonWindow})</span>
              ) : (
                <span className="text-slate-500">Ít Chạy ⚪</span>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * 12-Month Strip Visualizer & Tripartite Classifier (R2, R3)
 * Re-exported from Campaign12MonthTimeline for seamless backward compatibility.
 */
export {
  Campaign12MonthTimeline,
  CampaignLongevityTimeline,
  getTripartiteClassification,
  computeMonthlyActivityFallback,
  type Campaign12MonthTimelineProps,
  type TripartiteBadgeInfo,
  type TripartiteType
} from './Campaign12MonthTimeline';

