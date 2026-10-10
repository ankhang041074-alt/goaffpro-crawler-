import assert from 'node:assert';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import React from '../frontend/node_modules/react/index.js';
import ReactDOMServer from '../frontend/node_modules/react-dom/server.node.js';
import { createServer } from '../frontend/node_modules/vite/dist/node/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(projectRoot, 'frontend');

console.log('================================================================');
console.log('  M2 EMPIRICAL CHALLENGE SUITE: FRONTEND UI & 12-MONTH TIMELINE  ');
console.log('================================================================');

async function runEmpiricalStressSuite() {
  const vite = await createServer({
    root: frontendRoot,
    server: { middlewareMode: true }
  });

  const timelineMod = await vite.ssrLoadModule('/src/Campaign12MonthTimeline.tsx');
  const seasonalityMod = await vite.ssrLoadModule('/src/SeasonalityChart3Year.tsx');
  const {
    Campaign12MonthTimeline,
    CampaignLongevityTimeline,
    getTripartiteClassification,
    computeMonthlyActivityFallback
  } = timelineMod;

  let passed = 0;
  let total = 0;

  function test(name, fn) {
    total++;
    try {
      fn();
      passed++;
      console.log(`  [PASS] Test ${total}: ${name}`);
    } catch (err) {
      console.error(`  [FAIL] Test ${total}: ${name}`);
      console.error(`         ${err.message}`);
      throw err;
    }
  }

  // -------------------------------------------------------------
  // SUITE 1: computeMonthlyActivityFallback Date Math & Edge Cases
  // -------------------------------------------------------------
  console.log('\n--- SUITE 1: computeMonthlyActivityFallback Date Math & Edge Cases ---');

  test('Single-day ad (same firstSeen and lastShown in 2025-05-15) lights only month 5 in 2025', () => {
    const res = computeMonthlyActivityFallback('2025-05-15', '2025-05-15', 1);
    assert.deepStrictEqual(res['2024'], new Array(12).fill(false));
    assert.deepStrictEqual(res['2026'], new Array(12).fill(false));
    const m2025 = res['2025'];
    assert.strictEqual(m2025.length, 12);
    // May is index 4 (0-based)
    for (let i = 0; i < 12; i++) {
      assert.strictEqual(m2025[i], i === 4, `Month index ${i} should be ${i === 4}`);
    }
  });

  test('Missing dates (null/undefined) with durationDays=1 computes safely without NaN or crash', () => {
    const res1 = computeMonthlyActivityFallback(undefined, undefined, 1);
    assert(res1['2024'] && res1['2024'].length === 12);
    assert(res1['2025'] && res1['2025'].length === 12);
    assert(res1['2026'] && res1['2026'].length === 12);
    // Exactly one active month overall for current year
    const activeCount = Object.values(res1).flatMap(arr => arr).filter(Boolean).length;
    assert.strictEqual(activeCount, 1, `Expected exactly 1 active month for 1-day fallback, got ${activeCount}`);

    const resNull = computeMonthlyActivityFallback(null, null, 1);
    assert(resNull['2026'] && resNull['2026'].length === 12);
  });

  test('Empty string dates ("") compute safely', () => {
    const res = computeMonthlyActivityFallback('', '', 1);
    assert.strictEqual(typeof res['2026'], 'object');
    assert.strictEqual(res['2026'].length, 12);
  });

  test('Malformed / garbage date strings fallback gracefully without throwing', () => {
    const res = computeMonthlyActivityFallback('not-a-real-date', 'gibberish-2025', 5);
    assert(res['2024'] && res['2025'] && res['2026']);
    assert.strictEqual(res['2026'].length, 12);
  });

  test('Reversed dates (firstSeen > lastShown) are swapped and handled correctly', () => {
    // start 2025-10-01 > end 2025-02-01
    const res = computeMonthlyActivityFallback('2025-10-01', '2025-02-01', 240);
    const m2025 = res['2025'];
    // Months Feb (idx 1) through Oct (idx 9) should be true
    for (let i = 1; i <= 9; i++) {
      assert.strictEqual(m2025[i], true, `Month idx ${i} should be active`);
    }
    assert.strictEqual(m2025[0], false, 'Jan should be false');
    assert.strictEqual(m2025[10], false, 'Nov should be false');
    assert.strictEqual(m2025[11], false, 'Dec should be false');
  });

  test('Multi-year span (871 days from 2024-01-15 to 2026-06-05) activates 2024(all), 2025(all), 2026(T1-T6)', () => {
    const res = computeMonthlyActivityFallback('2024-01-15', '2026-06-05', 871);
    // 2024: all 12 months
    assert.strictEqual(res['2024'].filter(Boolean).length, 12);
    // 2025: all 12 months
    assert.strictEqual(res['2025'].filter(Boolean).length, 12);
    // 2026: Jan through June (indices 0..5)
    for (let i = 0; i < 6; i++) {
      assert.strictEqual(res['2026'][i], true, `2026 month ${i+1} should be active`);
    }
    for (let i = 6; i < 12; i++) {
      assert.strictEqual(res['2026'][i], false, `2026 month ${i+1} should be inactive`);
    }
  });

  test('Zero and negative durationDays do not throw', () => {
    const resZero = computeMonthlyActivityFallback('2025-01-01', '2025-01-01', 0);
    assert.strictEqual(resZero['2025'].length, 12);
    const resNeg = computeMonthlyActivityFallback('2025-01-01', '2025-01-01', -10);
    assert.strictEqual(resNeg['2025'].length, 12);
  });

  // -------------------------------------------------------------
  // SUITE 2: getTripartiteClassification Heuristics & Rules
  // -------------------------------------------------------------
  console.log('\n--- SUITE 2: getTripartiteClassification Heuristics & Rules ---');

  test('Explicit backend keys override heuristics', () => {
    const c1 = getTripartiteClassification(500, undefined, 'new_test');
    assert.strictEqual(c1.key, 'new_test');
    assert(c1.label.includes('Mới Chạy (New Test)'));

    const c2 = getTripartiteClassification(5, undefined, 'evergreen');
    assert.strictEqual(c2.key, 'evergreen');
    assert(c2.label.includes('Chạy Quanh Năm (Evergreen)'));

    const c3 = getTripartiteClassification(300, undefined, 'seasonal');
    assert.strictEqual(c3.key, 'seasonal');
    assert(c3.label.includes('Chạy Theo Mùa (Seasonal)'));
  });

  test('Vietnamese classification labels correctly mapped', () => {
    const c1 = getTripartiteClassification(100, undefined, undefined, '🌲 Chạy Quanh Năm');
    assert.strictEqual(c1.key, 'evergreen');

    const c2 = getTripartiteClassification(100, undefined, undefined, '🍂 Chạy Theo Mùa');
    assert.strictEqual(c2.key, 'seasonal');

    const c3 = getTripartiteClassification(100, undefined, undefined, '🟡 Mới Chạy Thử Nghiệm');
    assert.strictEqual(c3.key, 'new_test');
  });

  test('Single-day ad (durationDays = 1) without explicit key classifies as new_test', () => {
    const c = getTripartiteClassification(1);
    assert.strictEqual(c.key, 'new_test');
    assert.strictEqual(c.shortLabel, 'Mới Chạy');
    assert.strictEqual(c.icon, '🟡');
  });

  test('durationDays <= 30 classifies as new_test', () => {
    const c = getTripartiteClassification(30);
    assert.strictEqual(c.key, 'new_test');
  });

  test('Multi-year ad (durationDays = 871) classifies as evergreen', () => {
    const c = getTripartiteClassification(871);
    assert.strictEqual(c.key, 'evergreen');
    assert.strictEqual(c.icon, '🌲');
  });

  test('Seasonal ad (<= 4 peak months in one year, duration 60 days) classifies as seasonal', () => {
    const monthly = {
      '2025': [false, false, false, false, false, false, false, false, false, true, true, true] // Q4 only
    };
    const c = getTripartiteClassification(60, monthly);
    assert.strictEqual(c.key, 'seasonal');
    assert.strictEqual(c.icon, '🍂');
  });

  // -------------------------------------------------------------
  // SUITE 3: React Campaign12MonthTimeline Component Rendering
  // -------------------------------------------------------------
  console.log('\n--- SUITE 3: Campaign12MonthTimeline Component Rendering ---');

  test('Single-day ad (durationDays = 1) renders full component without disappearing', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 1,
        firstSeen: '2026-04-10',
        lastShown: '2026-04-10'
      })
    );
    assert(html.length > 500, 'HTML output should not be empty');
    assert(html.includes('1 ngày'), 'Should display "1 ngày"');
    assert(html.includes('🟡'), 'Should display yellow dot icon');
    assert(html.includes('Mới Chạy (New Test)'), 'Should display New Test badge');
    // Check 12 month cells
    for (let m = 1; m <= 12; m++) {
      assert(html.includes(`>T${m}<`), `Should contain label T${m}`);
    }
  });

  test('Single-day ad (durationDays = 1) in compact mode renders properly', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 1,
        firstSeen: '2026-04-10',
        lastShown: '2026-04-10',
        compact: true
      })
    );
    assert(html.length > 200, 'Compact mode should render HTML');
    assert(html.includes('1d'), 'Compact mode should display "1d"');
    assert(html.includes('Mới Chạy'), 'Compact mode should display short badge');
    // Check 12 month cells
    for (let m = 1; m <= 12; m++) {
      assert(html.includes(`>T${m}<`), `Should contain label T${m}`);
    }
  });

  test('Component handles missing monthlyActivity prop gracefully without crash', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 15,
        firstSeen: '2026-01-01',
        lastShown: '2026-01-15'
      })
    );
    assert(html.includes('15 ngày'));
    assert(html.includes('T1'));
    assert(html.includes('T12'));
  });

  test('Component handles null/undefined/empty dates gracefully without crash', () => {
    const html1 = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 45,
        firstSeen: undefined,
        lastShown: undefined
      })
    );
    assert(html1.includes('45 ngày'));

    const html2 = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 45,
        firstSeen: null,
        lastShown: null
      })
    );
    assert(html2.includes('45 ngày'));

    const html3 = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 45,
        firstSeen: '',
        lastShown: ''
      })
    );
    assert(html3.includes('45 ngày'));
  });

  test('Large longevity ad (871 days, 2024 to 2026) renders multi-year UI and evergreen badge', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 871,
        firstSeen: '2024-01-15',
        lastShown: '2026-06-05',
        showMultiYearSelector: true
      })
    );
    assert(html.includes('871 ngày'), 'Should render exact 871 days');
    assert(html.includes('~2.4 năm liên tục'), 'Should render humanized duration');
    assert(html.includes('🌲 Chạy Quanh Năm (Evergreen)'), 'Should classify as Evergreen');
    assert(html.includes('2024'), 'Should include 2024 tab');
    assert(html.includes('2025'), 'Should include 2025 tab');
    assert(html.includes('2026'), 'Should include 2026 tab');
    assert(html.includes('Cả 3 Năm'), 'Should include Cả 3 Năm button');
    assert(html.includes('Phủ sóng'), 'Should render coverage summary');
  });

  test('Component renders active glowing styles and inactive dim styles', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 90,
        firstSeen: '2026-10-01',
        lastShown: '2026-12-31'
      })
    );
    // Q4 active gradient
    assert(html.includes('from-amber-600') || html.includes('to-rose-400'), 'Q4 active months should use amber-rose gradient');
    // Inactive styling
    assert(html.includes('text-slate-400') || html.includes('bg-white/80'), 'Inactive months should use dim text-slate-400');
  });

  test('Extreme longevity (10000 days, durationDays = 0, negative durationDays)', () => {
    const htmlHuge = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, { durationDays: 10000 })
    );
    assert(htmlHuge.includes('10,000 ngày'));
    assert(htmlHuge.includes('🌲 Chạy Quanh Năm (Evergreen)'));

    const htmlZero = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, { durationDays: 0 })
    );
    assert(htmlZero.includes('0 ngày'));

    const htmlNeg = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, { durationDays: -5 })
    );
    assert(htmlNeg.includes('-5 ngày'));
  });

  test('Adversarial inputs: malformed monthlyActivity with irregular types', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Campaign12MonthTimeline, {
        durationDays: 50,
        monthlyActivity: {
          '2024': [true, false, null, undefined, 1, 0, 'yes', false, false, false, false, false],
          '2025': [], // empty array
          'invalidYear': null
        }
      })
    );
    assert(html.includes('50 ngày'));
  });

  // -------------------------------------------------------------
  // SUITE 4: Backward Compatibility & Re-exports
  // -------------------------------------------------------------
  console.log('\n--- SUITE 4: Backward Compatibility & Re-exports ---');

  test('CampaignLongevityTimeline alias points to Campaign12MonthTimeline', () => {
    assert.strictEqual(CampaignLongevityTimeline, Campaign12MonthTimeline);
  });

  test('SeasonalityChart3Year re-exports Campaign12MonthTimeline and CampaignLongevityTimeline', () => {
    assert(seasonalityMod.Campaign12MonthTimeline, 'SeasonalityChart3Year should re-export Campaign12MonthTimeline');
    assert(seasonalityMod.CampaignLongevityTimeline, 'SeasonalityChart3Year should re-export CampaignLongevityTimeline');
    assert.strictEqual(seasonalityMod.Campaign12MonthTimeline, Campaign12MonthTimeline);
  });

  await vite.close();

  console.log('================================================================');
  console.log(`  ALL ${passed}/${total} EMPIRICAL ADVERSARIAL STRESS TESTS PASSED!  `);
  console.log('================================================================');
}

runEmpiricalStressSuite().catch(err => {
  console.error('Stress suite encountered fatal failure:', err);
  process.exit(1);
});
