import React, { useMemo } from 'react';
import {
  Clock,
  Calendar,
  Flame,
  CheckCircle2
} from 'lucide-react';

export interface Campaign12MonthTimelineProps {
  durationDays: number;
  firstSeen?: string;
  lastShown?: string;
  monthlyActivity?: {
    [year: string]: boolean[];
  };
  classification?: 'evergreen' | 'seasonal' | 'new_test' | string;
  classificationLabel?: string;
  peakSeasonMonth?: string;
  compact?: boolean;
  mode?: '3year' | '12m'; // '3year' is default: all 3 years stacked in 1 matrix, '12m' is 1 row summary
  showMultiYearSelector?: boolean; // deprecated, kept for backwards compatibility
  initialYear?: string;
}

export type TripartiteType = 'evergreen' | 'seasonal' | 'new_test';

export interface TripartiteBadgeInfo {
  key: TripartiteType;
  label: string;
  shortLabel: string;
  badgeClass: string;
  icon: string;
  description: string;
}

/**
 * Standardized Tripartite Classification:
 * - 🌲 Chạy Quanh Năm (Evergreen): Chạy liên tục đa số các tháng, tuổi thọ dài
 * - 🍂 Chạy Theo Mùa (Seasonal): Tập trung chạy vào các tháng/quý cao điểm cố định (VD: Q4 T10-T12)
 * - 🟡 Mới Chạy (New Test): Mới khởi chạy trong vòng 30 ngày
 */
export function getTripartiteClassification(
  durationDays: number,
  monthlyActivity?: { [year: string]: boolean[] },
  explicitKey?: string,
  explicitLabel?: string
): TripartiteBadgeInfo {
  const labelStr = (explicitLabel || '').toLowerCase();
  const keyStr = (explicitKey || '').toLowerCase();

  if (keyStr === 'new_test' || labelStr.includes('mới chạy') || labelStr.includes('new test') || keyStr === 'test') {
    return {
      key: 'new_test',
      label: '🟡 Mới Chạy (New Test)',
      shortLabel: 'Mới Chạy',
      badgeClass: 'text-amber-700 bg-amber-50 border-amber-200',
      icon: '🟡',
      description: 'Mới khởi chạy trong vòng 30 ngày gần đây'
    };
  }

  if (keyStr === 'evergreen' || labelStr.includes('quanh năm') || labelStr.includes('evergreen') || keyStr === 'super_scale') {
    return {
      key: 'evergreen',
      label: '🌲 Chạy Quanh Năm (Evergreen)',
      shortLabel: 'Evergreen',
      badgeClass: 'text-emerald-800 bg-emerald-50 border-emerald-200',
      icon: '🌲',
      description: 'Chạy liên tục xuyên suốt các quý, tuổi thọ bền vững'
    };
  }

  if (keyStr === 'seasonal' || labelStr.includes('theo mùa') || labelStr.includes('seasonal')) {
    return {
      key: 'seasonal',
      label: '🍂 Chạy Theo Mùa (Seasonal)',
      shortLabel: 'Theo Mùa',
      badgeClass: 'text-amber-800 bg-amber-50 border-amber-200',
      icon: '🍂',
      description: 'Tập trung chạy dồn vào các tháng cao điểm hoặc theo mùa trong năm'
    };
  }

  // Dynamic heuristic
  if (durationDays <= 30) {
    return {
      key: 'new_test',
      label: '🟡 Mới Chạy (New Test)',
      shortLabel: 'Mới Chạy',
      badgeClass: 'text-amber-700 bg-amber-50 border-amber-200',
      icon: '🟡',
      description: 'Mới khởi chạy trong vòng 30 ngày gần đây'
    };
  }

  let totalActiveMonths = 0;
  let maxYearActive = 0;
  let yearsWithActivity = 0;

  if (monthlyActivity) {
    for (const flags of Object.values(monthlyActivity)) {
      if (Array.isArray(flags)) {
        const cnt = flags.filter(Boolean).length;
        if (cnt > 0) yearsWithActivity++;
        totalActiveMonths += cnt;
        if (cnt > maxYearActive) maxYearActive = cnt;
      }
    }
  }

  if (totalActiveMonths === 0) {
    if (durationDays >= 90) {
      return {
        key: 'evergreen',
        label: '🌲 Chạy Quanh Năm (Evergreen)',
        shortLabel: 'Evergreen',
        badgeClass: 'text-emerald-800 bg-emerald-50 border-emerald-200',
        icon: '🌲',
        description: 'Chạy liên tục xuyên suốt các quý, tuổi thọ bền vững'
      };
    }
    return {
      key: 'seasonal',
      label: '🍂 Chạy Theo Mùa (Seasonal)',
      shortLabel: 'Theo Mùa',
      badgeClass: 'text-amber-800 bg-amber-50 border-amber-200',
      icon: '🍂',
      description: 'Tập trung chạy dồn vào các tháng cao điểm'
    };
  }

  if (maxYearActive >= 7 || totalActiveMonths >= 8 || durationDays >= 180) {
    return {
      key: 'evergreen',
      label: '🌲 Chạy Quanh Năm (Evergreen)',
      shortLabel: 'Evergreen',
      badgeClass: 'text-emerald-800 bg-emerald-50 border-emerald-200',
      icon: '🌲',
      description: 'Chạy liên tục xuyên suốt các quý, tuổi thọ bền vững'
    };
  }

  return {
    key: 'seasonal',
    label: '🍂 Chạy Theo Mùa (Seasonal)',
    shortLabel: 'Theo Mùa',
    badgeClass: 'text-amber-800 bg-amber-50 border-amber-200',
    icon: '🍂',
    description: 'Tập trung chạy dồn vào các tháng cao điểm'
  };
}

/**
 * Computes calendar month overlap across 2024, 2025, 2026 as a fallback
 */
export function computeMonthlyActivityFallback(
  firstSeen?: string,
  lastShown?: string,
  durationDays: number = 1,
  years: number[] = [2024, 2025, 2026]
): { [year: string]: boolean[] } {
  const today = new Date();
  let end: Date = lastShown ? new Date(lastShown) : today;
  if (isNaN(end.getTime())) end = today;

  let start: Date;
  if (firstSeen && firstSeen !== lastShown) {
    const parsedStart = new Date(firstSeen);
    start = !isNaN(parsedStart.getTime()) ? parsedStart : new Date(end.getTime() - Math.max(0, durationDays - 1) * 86400000);
  } else {
    start = new Date(end.getTime() - Math.max(0, durationDays - 1) * 86400000);
  }

  if (start > end) {
    const tmp = start;
    start = end;
    end = tmp;
  }

  const result: { [year: string]: boolean[] } = {};
  for (const y of years) {
    const months: boolean[] = [];
    for (let m = 0; m < 12; m++) {
      const mStart = new Date(Date.UTC(y, m, 1));
      const mEnd = new Date(Date.UTC(y, m + 1, 0, 23, 59, 59));
      const isActive = start <= mEnd && end >= mStart;
      months.push(isActive);
    }
    result[String(y)] = months;
  }
  return result;
}

const MONTH_NAMES = [
  'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4',
  'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8',
  'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'
];

/**
 * Ma Trận Mùa Vụ 3 Năm (2024 - 2026) - Giao diện gốc chuẩn xác theo screenshot
 * Hiển thị 3 hàng năm trực tiếp (2024, 2025, 2026) trong cùng 1 bảng gọn gàng, không tách tab!
 */
export const Campaign12MonthTimeline: React.FC<Campaign12MonthTimelineProps> = ({
  durationDays,
  firstSeen,
  lastShown,
  monthlyActivity: propMonthlyActivity,
  classification,
  classificationLabel,
  compact = false,
  mode = '3year',
  showMultiYearSelector = false
}) => {
  // Resolve monthly activity
  const activityMap = useMemo(() => {
    if (propMonthlyActivity && Object.keys(propMonthlyActivity).length > 0) {
      const hasArrays = Object.values(propMonthlyActivity).some(v => Array.isArray(v) && v.length === 12);
      if (hasArrays) {
        return propMonthlyActivity;
      }
    }
    return computeMonthlyActivityFallback(firstSeen, lastShown, durationDays, [2024, 2025, 2026]);
  }, [propMonthlyActivity, firstSeen, lastShown, durationDays]);

  // Classification info
  const classificationInfo = useMemo(() => {
    return getTripartiteClassification(
      durationDays,
      activityMap,
      classification,
      classificationLabel
    );
  }, [durationDays, activityMap, classification, classificationLabel]);

  const years = ['2024', '2025', '2026'];

  // 12-Month Summary Aggregated row across 3 years
  const summary12M = useMemo(() => {
    const flags = new Array(12).fill(false);
    for (let m = 0; m < 12; m++) {
      if (activityMap['2024']?.[m] || activityMap['2025']?.[m] || activityMap['2026']?.[m]) {
        flags[m] = true;
      }
    }
    return flags;
  }, [activityMap]);

  // Total active months across 3 years
  const totalActiveMonths = useMemo(() => {
    let count = 0;
    for (const y of years) {
      if (activityMap[y]) {
        count += activityMap[y].filter(Boolean).length;
      }
    }
    return count;
  }, [activityMap]);

  // Humanized duration
  const humanizedDuration = useMemo(() => {
    if (durationDays >= 365) {
      return `~${(durationDays / 365).toFixed(1)} năm liên tục`;
    }
    if (durationDays >= 60) {
      return `~${Math.round(durationDays / 30)} tháng liên tục`;
    }
    return `${durationDays} ngày`;
  }, [durationDays]);

  // Compact Mode (used in minimal table cells or mobile)
  if (compact) {
    return (
      <div className="flex items-center gap-1.5 p-1 bg-slate-50/95 border border-slate-200 rounded-lg text-xs w-full max-w-[340px]">
        <span className="font-mono font-bold text-slate-700 text-[10px] whitespace-nowrap">
          {durationDays}d
        </span>
        <span className={`px-1.5 py-0.2 rounded text-[9.5px] font-bold whitespace-nowrap ${classificationInfo.badgeClass}`}>
          {classificationInfo.shortLabel}
        </span>
        <div className="grid grid-cols-12 gap-0.5 flex-1">
          {summary12M.map((isActive, mIdx) => (
            <span
              key={mIdx}
              className={`text-[8px] font-mono text-center rounded-xs px-0.5 leading-tight ${
                isActive
                  ? mIdx >= 9
                    ? 'bg-gradient-to-r from-amber-600 to-rose-400 text-white font-bold'
                    : 'bg-emerald-500 text-white font-bold'
                  : 'text-slate-400 bg-slate-200/70'
              }`}
            >
              T{mIdx + 1}
            </span>
          ))}
        </div>
      </div>
    );
  }

  // Mode: 12-Month Summary (1 row)
  if (mode === '12m') {
    return (
      <div className="flex flex-col gap-1 w-full max-w-[340px]">
        {/* Season badge & Duration */}
        <div className="flex items-center justify-between gap-1 text-[11px] font-bold">
          <div className="flex items-center gap-1">
            <span>{classificationInfo.icon}</span>
            <span className={classificationInfo.key === 'evergreen' ? 'text-emerald-700' : 'text-amber-800'}>
              {classificationInfo.label}
            </span>
          </div>
          <div className="flex items-center gap-1 font-mono text-[10px] text-slate-500 font-semibold">
            <span>{durationDays.toLocaleString()} ngày</span>
          </div>
        </div>

        {/* 1 Row: T1 -> T12 */}
        <div className="bg-slate-50/90 rounded-xl p-1.5 border border-slate-200/80">
          <div className="grid grid-cols-12 gap-0.5">
            {summary12M.map((isActive, mIdx) => {
              const monthNum = mIdx + 1;
              const isQ4 = monthNum >= 10;
              return (
                <div
                  key={monthNum}
                  title={`T${monthNum}: ${isActive ? (isQ4 ? '🔥 Đón mùa Q4 cao điểm' : '🟢 Có ads chạy') : '⚪ Không chạy'}`}
                  className={`h-4.5 rounded-xs flex items-center justify-center text-[8.5px] font-mono font-bold transition-all ${
                    isActive
                      ? isQ4
                        ? 'bg-gradient-to-r from-amber-600 to-rose-400 text-white shadow-2xs'
                        : 'bg-emerald-500 text-white'
                      : 'bg-slate-200/70 text-slate-400'
                  }`}
                >
                  T{monthNum}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // Default Mode: MA TRẬN 3 NĂM (2024 - 2026) - 3 rows stacked in 1 compact grid
  return (
    <div className="flex flex-col gap-1 w-full max-w-[340px]">
      {/* Top: Seasonality Badge (e.g. 🍂 Đón mùa Q4) & Duration */}
      <div className="flex items-center justify-between gap-1 text-[11px] font-bold">
        <div className="flex items-center gap-1">
          <span>{classificationInfo.icon}</span>
          <span className={classificationInfo.key === 'evergreen' ? 'text-emerald-700' : 'text-amber-800'}>
            {classificationInfo.label}
          </span>
        </div>
        <div className="flex items-center gap-1 font-mono text-[10px] text-slate-500 font-semibold">
          <span>{durationDays.toLocaleString()} ngày</span>
          {durationDays >= 365 && (
            <span className="text-slate-400 text-[9.5px]">({humanizedDuration})</span>
          )}
        </div>
      </div>

      {/* Multi-Year Selector Tabs & Coverage Summary (when enabled) */}
      {showMultiYearSelector && (
        <div className="flex items-center justify-between gap-1 text-[10px] border-b border-slate-200/80 pb-1">
          <div className="flex items-center gap-1 font-mono">
            {years.map(yr => (
              <span key={yr} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-bold border border-slate-200">
                {yr}
              </span>
            ))}
            <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
              Cả 3 Năm
            </span>
          </div>
          <span className="text-slate-500 font-medium">
            Phủ sóng: {totalActiveMonths}/36 tháng
          </span>
        </div>
      )}

      {/* The 3-Year Matrix: 3 stacked rows directly in 1 table! */}
      <div className="bg-slate-50/90 rounded-xl p-1.5 border border-slate-200/80 flex flex-col gap-1 w-full">
        {/* Month column headers: T1 through T12 */}
        <div className="flex items-center gap-1">
          <span className="font-mono text-[9px] text-slate-400 font-bold w-9 text-right select-none flex-shrink-0" />
          <div className="grid grid-cols-12 gap-0.5 flex-1">
            {Array.from({ length: 12 }, (_, i) => (
              <span key={i + 1} className="font-mono text-[8.5px] text-slate-400 font-semibold text-center select-none">
                T{i + 1}
              </span>
            ))}
          </div>
        </div>

        {years.map(year => {
          const flags = activityMap[year] || new Array(12).fill(false);
          return (
            <div key={year} className="flex items-center gap-1">
              <span className="font-mono text-[10px] text-slate-400 font-bold w-9 text-right select-none flex-shrink-0">
                {year}:
              </span>
              <div className="grid grid-cols-12 gap-0.5 flex-1">
                {flags.map((isActive, mIdx) => {
                  const monthNum = mIdx + 1;
                  const isQ4 = monthNum >= 10;
                  return (
                    <div
                      key={monthNum}
                      title={`T${monthNum}/${year} (${MONTH_NAMES[mIdx]}): ${
                        isActive
                          ? isQ4
                            ? '🔥 Đón mùa Q4 cao điểm (Black Friday / Noel)'
                            : '🟢 Có ads đang chạy'
                          : '⚪ Không chạy ads'
                      }`}
                      className={`h-3.5 rounded-xs transition-all ${
                        isActive
                          ? isQ4
                            ? 'bg-gradient-to-r from-amber-600 to-rose-400 shadow-2xs'
                            : 'bg-emerald-500 shadow-2xs'
                          : 'bg-slate-200/70 text-slate-400 hover:bg-slate-300'
                      }`}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Re-export with backward compatibility
export const CampaignLongevityTimeline = Campaign12MonthTimeline;
export default Campaign12MonthTimeline;
