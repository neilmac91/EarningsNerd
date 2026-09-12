/* @ds-bundle: {"format":3,"namespace":"EarningsNerdDesignSystem_3681b9","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"StatCard","sourcePath":"components/data/StatCard.jsx"},{"name":"StateCard","sourcePath":"components/data/StateCard.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"d6c1a9f16553","components/core/Button.jsx":"650dc4046815","components/core/Card.jsx":"3f23f48e149f","components/data/StatCard.jsx":"55724b5c5936","components/data/StateCard.jsx":"6fd7e772a80a","components/forms/Input.jsx":"889cdf5510d2","ui_kits/app/AppKit.jsx":"6369333918de","ui_kits/marketing/MarketingApp.jsx":"080b86c8f4fe"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.EarningsNerdDesignSystem_3681b9 = window.EarningsNerdDesignSystem_3681b9 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pill badge. Neutral/brand for labels & Pro; gain/loss/flat for financial
 * direction; filing for monospace filing-type tags (10-K, 10-Q, 8-K).
 */
function Badge({
  variant = 'neutral',
  className = '',
  children,
  ...props
}) {
  const classes = ['en-badge', `en-badge--${variant}`, className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: classes
  }, props), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * EarningsNerd primary button. Three variants, two sizes. Brand is sage (light)
 * / slate (dark); secondary lifts and BRIGHTENS on hover, never darkens.
 */
function Button({
  variant = 'primary',
  size = 'md',
  type = 'button',
  className = '',
  children,
  ...props
}) {
  const classes = ['en-btn', `en-btn--${variant}`, size === 'sm' ? 'en-btn--sm' : size === 'lg' ? 'en-btn--lg' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    className: classes
  }, props), children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Surface card — off-white panel that LIFTS off the cream page with a soft
 * shadow + hairline (in dark, separates via fill + hairline, no shadow).
 */
function Card({
  interactive = false,
  className = '',
  children,
  ...props
}) {
  const classes = ['en-card', interactive ? 'en-card--interactive' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", _extends({
    className: classes
  }, props), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/data/StatCard.jsx
try { (() => {
function fmt(value, unit) {
  if (value == null || !Number.isFinite(value)) return 'N/A';
  if (unit === 'currency') {
    if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    return `$${(value / 1e6).toFixed(2)}M`;
  }
  if (unit === 'percent') return `${value.toFixed(2)}%`;
  return value.toLocaleString();
}
const Arrow = ({
  dir
}) => {
  // Phosphor-style arrow-up-right / arrow-down-right / minus (outline)
  const common = {
    width: 12,
    height: 12,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2.25,
    strokeLinecap: 'round',
    strokeLinejoin: 'round'
  };
  if (dir === 'up') return /*#__PURE__*/React.createElement("svg", common, /*#__PURE__*/React.createElement("path", {
    d: "M7 17 17 7"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M7 7h10v10"
  }));
  if (dir === 'down') return /*#__PURE__*/React.createElement("svg", common, /*#__PURE__*/React.createElement("path", {
    d: "M7 7 17 17"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M17 7v10H7"
  }));
  return /*#__PURE__*/React.createElement("svg", common, /*#__PURE__*/React.createElement("path", {
    d: "M5 12h14"
  }));
};

/**
 * Financial metric tile — monospace tabular value, calm directional chip, and an
 * optional sparkline. Direction tone is gain/loss/flat, never the brand accent.
 */
function StatCard({
  label,
  value,
  unit = 'number',
  change = null,
  trendData = null,
  className = ''
}) {
  const hasValue = value != null && Number.isFinite(value);
  const hasChange = change != null && Number.isFinite(change);
  const dir = hasChange ? change > 0 ? 'up' : change < 0 ? 'down' : 'flat' : 'flat';
  const badge = dir === 'up' ? 'en-badge--gain' : dir === 'down' ? 'en-badge--loss' : 'en-badge--flat';
  let spark = null;
  if (trendData && trendData.length > 1) {
    const w = 96,
      h = 36,
      min = Math.min(...trendData),
      max = Math.max(...trendData);
    const span = max - min || 1;
    const pts = trendData.map((v, i) => `${i / (trendData.length - 1) * w},${h - (v - min) / span * h}`).join(' ');
    const stroke = dir === 'up' ? 'var(--gain)' : dir === 'down' ? 'var(--loss)' : 'var(--flat-light)';
    spark = /*#__PURE__*/React.createElement("svg", {
      width: w,
      height: h,
      style: {
        opacity: 0.6
      },
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("polyline", {
      points: pts,
      fill: "none",
      stroke: stroke,
      strokeWidth: "2",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }));
  }
  return /*#__PURE__*/React.createElement("div", {
    className: ['en-card', className].filter(Boolean).join(' '),
    style: {
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-data-xs)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-wide)',
      color: 'var(--text-tertiary-light)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "tabular",
    style: {
      marginTop: 6,
      fontSize: 'var(--text-2xl)',
      fontWeight: 600,
      letterSpacing: 'var(--tracking-snug)',
      color: 'var(--text-primary-light)'
    }
  }, hasValue ? fmt(value, unit) : 'N/A')), spark), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, hasValue ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: ['en-badge', badge].join(' ')
  }, /*#__PURE__*/React.createElement(Arrow, {
    dir: dir
  }), hasChange ? `${Math.abs(change).toFixed(1)}%` : 'N/A'), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary-light)'
    }
  }, "vs prior period")) : /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-tertiary-light)'
    }
  }, "Data not available")));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/data/StateCard.jsx
try { (() => {
const ICONS = {
  error: /*#__PURE__*/React.createElement("path", {
    d: "M12 8v4M12 16h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
  }),
  info: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M12 16v-4M12 8h.01"
  })),
  success: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M21.801 10A10 10 0 1 1 17 3.335"
  }), /*#__PURE__*/React.createElement("path", {
    d: "m9 11 3 3L22 4"
  }))
};

/**
 * Inline guidance/state container. `info` is brand-tinted (subdued, not loud
 * blue); `success` is green; `error` is red. Reserve loud status colors for
 * genuine state.
 */
function StateCard({
  variant = 'info',
  title,
  message,
  action,
  className = ''
}) {
  const tone = {
    error: {
      bg: 'var(--loss-soft)',
      bd: 'rgba(220,38,38,0.30)',
      fg: 'var(--error-light)'
    },
    info: {
      bg: 'var(--brand-weak)',
      bd: 'rgba(79,122,99,0.30)',
      fg: 'var(--brand-strong)'
    },
    success: {
      bg: 'var(--gain-soft)',
      bd: 'rgba(22,163,74,0.30)',
      fg: 'var(--success-light)'
    }
  }[variant];
  return /*#__PURE__*/React.createElement("div", {
    className: className,
    style: {
      borderRadius: 'var(--radius-2xl)',
      border: `1px solid ${tone.bd}`,
      background: tone.bg,
      color: tone.fg,
      padding: 'var(--space-4-5)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      marginTop: 2,
      flex: 'none'
    }
  }, ICONS[variant]), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 600
    }
  }, title), message && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      lineHeight: 'var(--leading-normal)',
      opacity: 0.85,
      marginTop: 4
    }
  }, message), action && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12
    }
  }, action))));
}
Object.assign(__ds_scope, { StateCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/StateCard.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Text field. Fill is the brightest surface so it reads on the cream page OR an
 * off-white card. Use `as="textarea"` / `as="select"` to reuse the same styling.
 */
function Input({
  as = 'input',
  className = '',
  children,
  ...props
}) {
  const Tag = as;
  return /*#__PURE__*/React.createElement(Tag, _extends({
    className: ['en-input', className].filter(Boolean).join(' ')
  }, props), children);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/AppKit.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const {
  useState,
  useEffect
} = React;
const DS = window.EarningsNerdDesignSystem_3681b9;
const {
  Button,
  Badge,
  Card,
  StatCard,
  StateCard
} = DS;

// ---- phosphor: font-based icons, no JS re-render needed ----
function useIcons() {} // no-op (lucide legacy); Phosphor glyphs render via CSS
const Ic = ({
  name,
  cls = 'ic',
  style = {}
}) => {
  const {
    width,
    height,
    ...rest
  } = style;
  const sz = width != null ? width : height;
  return /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${name} ${cls}`,
    style: {
      ...(sz != null ? {
        fontSize: typeof sz === 'number' ? sz + 'px' : sz
      } : {}),
      lineHeight: 1,
      ...rest
    }
  });
};
const FILING = {
  ticker: 'AAPL',
  name: 'Apple Inc.',
  type: '10-K',
  fy: 'FY2024',
  filed: 'Nov 1, 2024',
  snapshot: 'Apple delivered FY2024 revenue of $391.0B (+2% YoY), led by an all-time Services record of $96.2B (+13%). Product revenue was roughly flat as iPhone held steady and Mac/iPad recovered from prior-year declines. Operating margin expanded ~120bps to 31.5% on Services mix; the company returned over $110B to shareholders.',
  stats: [{
    label: 'Revenue',
    value: 391035000000,
    unit: 'currency',
    change: 2.0,
    trendData: [365, 366, 383, 394, 391]
  }, {
    label: 'Net income',
    value: 93736000000,
    unit: 'currency',
    change: -3.4,
    trendData: [99.8, 94.7, 97, 99.8, 93.7]
  }, {
    label: 'Gross margin',
    value: 46.2,
    unit: 'percent',
    change: 1.9
  }, {
    label: 'Operating margin',
    value: 31.5,
    unit: 'percent',
    change: 1.2
  }],
  sections: [{
    icon: 'trend-up',
    t: 'Financial performance',
    pts: ['Services revenue reached a record $96.2B, up 13% YoY and now 25% of total revenue.', 'iPhone revenue of $201.2B was roughly flat; Greater China declined 8%.', 'Diluted EPS of $6.08 vs $6.13 prior year, weighed by a one-time EU tax charge.']
  }, {
    icon: 'shield-warning',
    t: 'Key risks',
    pts: ['Concentration in iPhone (≈51% of revenue) leaves results sensitive to a single product cycle.', 'Ongoing regulatory pressure in the EU (DMA) and pending antitrust matters in the US.', 'Supply-chain exposure to Greater China for both manufacturing and demand.']
  }, {
    icon: 'compass',
    t: 'Management discussion',
    pts: ['Management highlighted Apple Intelligence as a multi-year platform driver.', 'Capital return program expanded with a new $110B buyback authorization.', 'No formal guidance issued; commentary points to continued Services momentum.']
  }]
};
const SAVED = [{
  name: 'Apple Inc.',
  type: '10-K',
  when: 'Nov 1, 2024'
}, {
  name: 'Microsoft Corporation',
  type: '10-Q',
  when: 'Oct 24, 2024'
}];
const WATCH = [{
  name: 'NVIDIA Corporation',
  ticker: 'NVDA'
}, {
  name: 'Tesla, Inc.',
  ticker: 'TSLA'
}, {
  name: 'Amazon.com, Inc.',
  ticker: 'AMZN'
}];
const FEED = [{
  ticker: 'NVDA',
  name: 'NVIDIA',
  text: 'New 10-Q filed — data-center revenue +94% YoY.',
  when: '2h',
  dir: 'gain'
}, {
  ticker: 'TSLA',
  name: 'Tesla',
  text: 'New 10-Q filed — automotive margin compressed.',
  when: '5h',
  dir: 'loss'
}];

// ════════════════════ App header ════════════════════
function AppHeader({
  dark,
  onToggle,
  onHome
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 40,
      background: 'var(--surface-page)',
      borderBottom: '1px solid var(--hairline)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1180,
      margin: '0 auto',
      padding: '10px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("a", {
    onClick: onHome,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: `../../assets/earningsnerd-icon-${dark ? 'dark' : 'light'}.svg`,
    width: "30",
    height: "30",
    alt: ""
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 700,
      color: 'var(--text-body)'
    }
  }, "EarningsNerd")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      maxWidth: 380,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      background: 'var(--surface-field)',
      border: '1px solid var(--hairline)',
      borderRadius: 'var(--radius-lg)',
      padding: '7px 12px'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "magnifying-glass",
    style: {
      width: 16,
      height: 16,
      color: 'var(--text-subtle)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    placeholder: "Jump to any company\u2026",
    style: {
      flex: 1,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-body)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onToggle,
    "aria-label": "Toggle theme",
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 34,
      height: 34,
      borderRadius: 'var(--radius-full)',
      border: '1px solid var(--hairline)',
      background: 'transparent',
      color: 'var(--text-muted)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: dark ? 'sun' : 'moon',
    style: {
      width: 16,
      height: 16
    }
  })), /*#__PURE__*/React.createElement("button", {
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 34,
      height: 34,
      borderRadius: 'var(--radius-full)',
      border: '1px solid var(--hairline)',
      background: 'transparent',
      color: 'var(--text-muted)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "bell",
    style: {
      width: 16,
      height: 16
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 34,
      height: 34,
      borderRadius: 'var(--radius-full)',
      background: 'var(--brand-strong)',
      color: '#fff',
      fontWeight: 700,
      fontSize: 'var(--text-sm)'
    }
  }, "N")));
}
function SectionTitle({
  children,
  action
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      margin: '0 0 16px'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontSize: 'var(--text-2xl)',
      margin: 0,
      color: 'var(--text-title)'
    }
  }, children), action);
}

// ════════════════════ Dashboard ════════════════════
function Dashboard({
  onOpenFiling
}) {
  const used = 3,
    limit = 5,
    pct = used / limit * 100;
  return /*#__PURE__*/React.createElement("main", {
    style: {
      maxWidth: 1180,
      margin: '0 auto',
      padding: '32px 24px 80px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-3xl)',
      margin: 0,
      color: 'var(--text-title)'
    }
  }, "Dashboard"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '6px 0 0',
      color: 'var(--text-muted)'
    }
  }, "Welcome back, Neil \u2014 here's what changed across your companies.")), /*#__PURE__*/React.createElement("div", {
    style: {
      margin: '28px 0'
    }
  }, /*#__PURE__*/React.createElement(SectionTitle, null, "What changed"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 12
    }
  }, FEED.map(f => /*#__PURE__*/React.createElement(Card, {
    key: f.ticker,
    interactive: true,
    onClick: onOpenFiling,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      cursor: 'pointer',
      padding: 'var(--space-4) var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 40,
      height: 40,
      borderRadius: 'var(--radius-lg)',
      background: 'var(--surface-tint)',
      color: 'var(--accent-strong)'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "file-text"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-body)',
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "tabular",
    style: {
      color: 'var(--accent-strong)'
    }
  }, f.ticker), " \xB7 ", f.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, f.text)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)'
    }
  }, f.when), /*#__PURE__*/React.createElement(Ic, {
    name: "caret-right",
    style: {
      width: 18,
      height: 18,
      color: 'var(--text-subtle)'
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 24,
      marginBottom: 28
    }
  }, /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontSize: 'var(--text-lg)',
      color: 'var(--text-title)'
    }
  }, "Subscription"), /*#__PURE__*/React.createElement(Badge, {
    variant: "neutral"
  }, "Free")), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '0 0 16px',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, "Upgrade to Pro for unlimited summaries, comparison, and Ask-this-Filing."), /*#__PURE__*/React.createElement(Button, null, "Upgrade to Pro")), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: '0 0 14px',
      fontSize: 'var(--text-lg)',
      color: 'var(--text-title)'
    }
  }, "Usage this month"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "tabular"
  }, used, " / ", limit, " summaries"), /*#__PURE__*/React.createElement("span", {
    className: "tabular"
  }, limit - used, " remaining")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 12,
      borderRadius: 'var(--radius-full)',
      background: 'var(--surface-tint)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: pct + '%',
      height: '100%',
      borderRadius: 'var(--radius-full)',
      background: 'var(--brand-strong)'
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.3fr 1fr',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(SectionTitle, null, "Saved summaries"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 12
    }
  }, SAVED.map((s, i) => /*#__PURE__*/React.createElement(Card, {
    key: i,
    interactive: true,
    onClick: onOpenFiling,
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      cursor: 'pointer',
      padding: 'var(--space-4) var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-body)',
      fontSize: 'var(--text-sm)'
    }
  }, s.name, " ", /*#__PURE__*/React.createElement(Badge, {
    variant: "filing"
  }, s.type)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)',
      marginTop: 4
    }
  }, "Filed ", s.when)), /*#__PURE__*/React.createElement("button", {
    style: {
      border: 'none',
      background: 'transparent',
      color: 'var(--loss)',
      cursor: 'pointer',
      padding: 6
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "trash",
    style: {
      width: 16,
      height: 16
    }
  })))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(SectionTitle, null, "Watchlist"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 12
    }
  }, WATCH.map((w, i) => /*#__PURE__*/React.createElement(Card, {
    key: i,
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: 'var(--space-4) var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-body)',
      fontSize: 'var(--text-sm)'
    }
  }, w.name), /*#__PURE__*/React.createElement("div", {
    className: "tabular",
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)'
    }
  }, w.ticker)), /*#__PURE__*/React.createElement(Badge, {
    variant: "brand"
  }, "Watching")))))));
}

// ════════════════════ Filing summary ════════════════════
function Filing({
  onBack
}) {
  const [streaming, setStreaming] = useState(false);
  return /*#__PURE__*/React.createElement("main", {
    style: {
      maxWidth: 900,
      margin: '0 auto',
      padding: '24px 24px 80px'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onBack,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      border: 'none',
      background: 'transparent',
      color: 'var(--text-muted)',
      cursor: 'pointer',
      fontSize: 'var(--text-sm)',
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "arrow-left",
    style: {
      width: 16,
      height: 16
    }
  }), " Back to dashboard"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 20,
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "tabular",
    style: {
      fontSize: 'var(--text-xl)',
      fontWeight: 700,
      color: 'var(--accent-strong)'
    }
  }, FILING.ticker), /*#__PURE__*/React.createElement(Badge, {
    variant: "filing"
  }, FILING.type), /*#__PURE__*/React.createElement(Badge, {
    variant: "neutral"
  }, FILING.fy)), /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      fontSize: 'var(--text-3xl)',
      color: 'var(--text-title)'
    }
  }, FILING.name), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '6px 0 0',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-subtle)'
    }
  }, "Annual report \xB7 filed ", FILING.filed, " \xB7 sourced from SEC EDGAR")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary"
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "bookmark-simple",
    style: {
      width: 16,
      height: 16
    }
  }), " Save"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary"
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "git-diff",
    style: {
      width: 16,
      height: 16
    }
  }), " Compare"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4,1fr)',
      gap: 14,
      marginBottom: 24
    }
  }, FILING.stats.map((s, i) => /*#__PURE__*/React.createElement(StatCard, _extends({
    key: i
  }, s)))), /*#__PURE__*/React.createElement(Card, {
    style: {
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-data-xs)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-wide)',
      color: 'var(--text-subtle)'
    }
  }, "Executive snapshot"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontSize: 'var(--text-xs)',
      color: 'var(--gain)'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "check-circle",
    style: {
      width: 14,
      height: 14
    }
  }), " Evidence-backed")), /*#__PURE__*/React.createElement("p", {
    className: "filing-summary",
    style: {
      margin: 0,
      fontFamily: 'var(--font-data)',
      fontSize: 'var(--text-sm)',
      lineHeight: 1.75,
      color: 'var(--text-body)'
    }
  }, FILING.snapshot)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 16
    }
  }, FILING.sections.map((sec, i) => /*#__PURE__*/React.createElement(Card, {
    key: i
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      margin: '0 0 14px',
      fontSize: 'var(--text-lg)',
      color: 'var(--text-title)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 32,
      height: 32,
      borderRadius: 'var(--radius)',
      background: 'var(--surface-tint)',
      color: 'var(--accent-strong)'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: sec.icon,
    style: {
      width: 17,
      height: 17
    }
  })), sec.t), /*#__PURE__*/React.createElement("ul", {
    style: {
      margin: 0,
      paddingLeft: 0,
      listStyle: 'none',
      display: 'grid',
      gap: 10
    }
  }, sec.pts.map((p, j) => /*#__PURE__*/React.createElement("li", {
    key: j,
    style: {
      display: 'flex',
      gap: 10,
      fontSize: 'var(--text-sm)',
      lineHeight: 1.6,
      color: 'var(--text-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent-strong)',
      flex: 'none',
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "quotes",
    style: {
      width: 14,
      height: 14
    }
  })), /*#__PURE__*/React.createElement("span", null, p))))))), /*#__PURE__*/React.createElement(Card, {
    style: {
      marginTop: 20,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 16,
      background: 'var(--surface-tint)',
      border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "sparkle",
    style: {
      width: 20,
      height: 20,
      color: 'var(--accent-strong)'
    }
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-body)',
      fontSize: 'var(--text-sm)'
    }
  }, "Ask this filing ", /*#__PURE__*/React.createElement(Badge, {
    variant: "pro"
  }, "Pro")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-muted)',
      marginTop: 2
    }
  }, "Natural-language Q&A grounded in this 10-K, with deep-linked citations."))), /*#__PURE__*/React.createElement(Button, null, "Upgrade")));
}

// ════════════════════ App ════════════════════
function AppKit() {
  const [dark, setDark] = useState(false);
  const [view, setView] = useState('dashboard');
  useIcons([dark, view]);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      background: 'var(--surface-page)'
    }
  }, /*#__PURE__*/React.createElement(AppHeader, {
    dark: dark,
    onToggle: () => setDark(d => !d),
    onHome: () => setView('dashboard')
  }), view === 'dashboard' ? /*#__PURE__*/React.createElement(Dashboard, {
    onOpenFiling: () => setView('filing')
  }) : /*#__PURE__*/React.createElement(Filing, {
    onBack: () => setView('dashboard')
  }));
}
window.AppKit = AppKit;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/AppKit.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/MarketingApp.jsx
try { (() => {
const {
  useState,
  useEffect,
  useRef
} = React;
const DS = window.EarningsNerdDesignSystem_3681b9;
const {
  Button,
  Badge,
  Card
} = DS;

// ---- phosphor: font-based icons, render via CSS (no JS re-render) ----
function useIcons() {} // no-op (lucide legacy)
const Ic = ({
  name,
  cls = 'ic',
  style = {}
}) => {
  const {
    width,
    height,
    ...rest
  } = style;
  const sz = width != null ? width : height;
  return /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${name} ${cls}`,
    style: {
      ...(sz != null ? {
        fontSize: typeof sz === 'number' ? sz + 'px' : sz
      } : {}),
      lineHeight: 1,
      ...rest
    }
  });
};
const COMPANIES = [{
  ticker: 'AAPL',
  name: 'Apple Inc.',
  sector: 'Technology'
}, {
  ticker: 'MSFT',
  name: 'Microsoft Corporation',
  sector: 'Technology'
}, {
  ticker: 'NVDA',
  name: 'NVIDIA Corporation',
  sector: 'Semiconductors'
}, {
  ticker: 'AMZN',
  name: 'Amazon.com, Inc.',
  sector: 'Consumer'
}, {
  ticker: 'TSLA',
  name: 'Tesla, Inc.',
  sector: 'Automotive'
}, {
  ticker: 'NKE',
  name: 'NIKE, Inc.',
  sector: 'Consumer'
}, {
  ticker: 'JPM',
  name: 'JPMorgan Chase & Co.',
  sector: 'Financials'
}];
const HOT = [{
  ticker: 'NVDA',
  name: 'NVIDIA Corporation',
  type: '10-Q',
  when: '2h ago',
  note: 'Data-center revenue up 94% YoY; guidance raised.',
  dir: 'gain',
  pct: '+94%'
}, {
  ticker: 'TSLA',
  name: 'Tesla, Inc.',
  type: '10-Q',
  when: '5h ago',
  note: 'Automotive margin compresses on price cuts.',
  dir: 'loss',
  pct: '−4.6%'
}, {
  ticker: 'AAPL',
  name: 'Apple Inc.',
  type: '10-K',
  when: '1d ago',
  note: 'Services hits record; iPhone roughly flat.',
  dir: 'gain',
  pct: '+2.0%'
}, {
  ticker: 'NKE',
  name: 'NIKE, Inc.',
  type: '10-K',
  when: '2d ago',
  note: 'Revenue down on soft wholesale demand.',
  dir: 'loss',
  pct: '−11.5%'
}];

// ════════════════════════════ Header ════════════════════════════
function Header({
  dark,
  onToggle
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 50,
      borderBottom: '1px solid var(--hairline)',
      background: 'color-mix(in srgb, var(--surface-page) 82%, transparent)',
      backdropFilter: 'blur(16px)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 1,
      background: 'linear-gradient(90deg, transparent, color-mix(in srgb, var(--accent-strong) 40%, transparent), transparent)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '12px 24px'
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      textDecoration: 'none'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: `../../assets/earningsnerd-icon-${dark ? 'dark' : 'light'}.svg`,
    width: "32",
    height: "32",
    alt: ""
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-lg)',
      fontWeight: 700,
      color: 'var(--text-body)'
    }
  }, "EarningsNerd")), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      gap: 32
    }
  }, ['Search', 'Compare', 'Pricing', 'Contact'].map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 500,
      color: 'var(--text-muted)',
      textDecoration: 'none'
    }
  }, l))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onToggle,
    "aria-label": "Toggle theme",
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 36,
      height: 36,
      borderRadius: 'var(--radius-full)',
      border: '1px solid var(--hairline)',
      background: 'transparent',
      color: 'var(--text-muted)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: dark ? 'sun' : 'moon'
  })), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 500,
      color: 'var(--text-muted)',
      textDecoration: 'none'
    }
  }, "Log In"), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      borderRadius: 'var(--radius-full)',
      background: 'var(--brand-strong)',
      color: '#fff',
      padding: '8px 18px',
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      textDecoration: 'none',
      boxShadow: 'var(--shadow-e2)'
    }
  }, "Get Started ", /*#__PURE__*/React.createElement(Ic, {
    name: "arrow-right",
    style: {
      width: 15,
      height: 15
    }
  })))));
}

// ════════════════════════════ Search ════════════════════════════
function Search({
  onPick,
  autoFocus
}) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const results = q ? COMPANIES.filter(c => (c.ticker + c.name).toLowerCase().includes(q.toLowerCase())) : [];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      maxWidth: 520
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "hero-search-glow",
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: 'var(--surface-field)',
      border: '1px solid var(--hairline)',
      borderRadius: 'var(--radius-xl)',
      padding: '4px 4px 4px 16px'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "magnifying-glass",
    style: {
      width: 20,
      height: 20,
      color: 'var(--text-subtle)'
    }
  }), /*#__PURE__*/React.createElement("input", {
    autoFocus: autoFocus,
    value: q,
    onChange: e => {
      setQ(e.target.value);
      setOpen(true);
    },
    onFocus: () => setOpen(true),
    placeholder: "Search by company name or ticker\u2026",
    style: {
      flex: 1,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      padding: '12px 0',
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--text-base)',
      color: 'var(--text-body)'
    }
  }), /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    onClick: () => results[0] && onPick(results[0])
  }, "Analyze")), open && results.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 'calc(100% + 8px)',
      left: 0,
      right: 0,
      background: 'var(--surface-card)',
      border: '1px solid var(--hairline)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-e4)',
      overflow: 'hidden',
      zIndex: 20
    }
  }, results.map(c => /*#__PURE__*/React.createElement("button", {
    key: c.ticker,
    onClick: () => {
      onPick(c);
      setOpen(false);
      setQ('');
    },
    style: {
      display: 'flex',
      width: '100%',
      alignItems: 'center',
      gap: 12,
      padding: '11px 16px',
      border: 'none',
      background: 'transparent',
      cursor: 'pointer',
      textAlign: 'left'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'var(--surface-tint)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement("span", {
    className: "tabular",
    style: {
      fontWeight: 700,
      fontSize: 'var(--text-sm)',
      color: 'var(--accent-strong)',
      width: 52
    }
  }, c.ticker), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-body)',
      flex: 1
    }
  }, c.name), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)'
    }
  }, c.sector)))));
}

// ════════════════════════════ Hero example card ════════════════════════════
function ExampleCard() {
  return /*#__PURE__*/React.createElement(Card, {
    className: "animate-float",
    style: {
      padding: 0,
      overflow: 'hidden',
      maxWidth: 420
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 20px',
      borderBottom: '1px solid var(--hairline)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "tabular",
    style: {
      fontWeight: 700,
      color: 'var(--accent-strong)'
    }
  }, "AAPL"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, "Apple Inc.")), /*#__PURE__*/React.createElement(Badge, {
    variant: "filing"
  }, "10-K")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-data-xs)',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-wide)',
      color: 'var(--text-subtle)',
      marginBottom: 8
    }
  }, "Executive snapshot"), /*#__PURE__*/React.createElement("p", {
    className: "filing-summary",
    style: {
      margin: 0,
      fontFamily: 'var(--font-data)',
      fontSize: 'var(--text-sm)',
      lineHeight: 1.7,
      color: 'var(--text-body)'
    }
  }, "FY2024 revenue of ", /*#__PURE__*/React.createElement("b", null, "$391.0B"), " (+2% YoY) with Services at a record ", /*#__PURE__*/React.createElement("b", null, "$96.2B"), ". iPhone roughly flat; Mac and iPad recovered. Operating margin expanded to ", /*#__PURE__*/React.createElement("b", null, "31.5%"), "."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 10,
      marginTop: 16
    }
  }, /*#__PURE__*/React.createElement(Mini, {
    label: "Revenue",
    val: "$391.0B",
    pct: "+2.0%",
    dir: "gain"
  }), /*#__PURE__*/React.createElement(Mini, {
    label: "Net income",
    val: "$93.7B",
    pct: "\u22123.4%",
    dir: "loss"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      marginTop: 16,
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "link",
    style: {
      width: 14,
      height: 14
    }
  }), " Every figure deep-links to its SEC EDGAR source.")));
}
function Mini({
  label,
  val,
  pct,
  dir
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      border: '1px solid var(--hairline)',
      borderRadius: 'var(--radius-md)',
      padding: '10px 12px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-data-xs)',
      color: 'var(--text-subtle)',
      textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-wide)',
      fontWeight: 700
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "tabular",
    style: {
      fontSize: 'var(--text-lg)',
      fontWeight: 600,
      color: 'var(--text-body)'
    }
  }, val), /*#__PURE__*/React.createElement(Badge, {
    variant: dir,
    style: {
      marginTop: 4
    }
  }, dir === 'gain' ? '▲' : '▼', " ", pct));
}

// ════════════════════════════ Sections ════════════════════════════
function HowItWorks() {
  const steps = [{
    icon: 'magnifying-glass',
    t: 'Search any company',
    d: 'Find any public company by name or ticker, straight from SEC EDGAR.'
  }, {
    icon: 'sparkle',
    t: 'Generate a summary',
    d: 'AI turns the 10-K or 10-Q into a structured, evidence-backed brief — streamed live.'
  }, {
    icon: 'chart-line',
    t: 'Decide with confidence',
    d: 'Financials, risks, and trends in minutes. Every claim cites the filing.'
  }];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      padding: '80px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontSize: 'var(--text-4xl)',
      margin: 0,
      color: 'var(--text-title)'
    }
  }, "From filing to insight in three steps"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-lg)',
      color: 'var(--text-muted)',
      maxWidth: 560,
      margin: '14px auto 48px'
    }
  }, "No spreadsheets, no 100-page PDFs. Just the signal."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 24
    }
  }, steps.map((s, i) => /*#__PURE__*/React.createElement(Card, {
    key: i,
    style: {
      textAlign: 'left'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      placeItems: 'center',
      width: 44,
      height: 44,
      borderRadius: 'var(--radius-lg)',
      background: 'var(--surface-tint)',
      color: 'var(--accent-strong)',
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: s.icon,
    style: {
      width: 22,
      height: 22
    }
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: '0 0 8px',
      fontSize: 'var(--text-xl)',
      color: 'var(--text-title)'
    }
  }, s.t), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 'var(--text-sm)',
      lineHeight: 1.6,
      color: 'var(--text-muted)'
    }
  }, s.d))))));
}
function Trending({
  onPick
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      padding: '40px 0 80px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      maxWidth: 880
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      fontSize: 'var(--text-2xl)',
      color: 'var(--text-title)',
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "flame",
    style: {
      width: 22,
      height: 22,
      color: 'var(--chart-4, #CF7159)'
    }
  }), " Trending Filings"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 14
    }
  }, HOT.map(f => /*#__PURE__*/React.createElement(Card, {
    key: f.ticker,
    interactive: true,
    onClick: () => onPick(f),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 18,
      cursor: 'pointer',
      padding: 'var(--space-4-5) var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 64
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "tabular",
    style: {
      fontWeight: 700,
      color: 'var(--accent-strong)'
    }
  }, f.ticker), /*#__PURE__*/React.createElement(Badge, {
    variant: "filing",
    style: {
      marginTop: 4
    }
  }, f.type)), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-body)',
      fontSize: 'var(--text-sm)'
    }
  }, f.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      marginTop: 2
    }
  }, f.note)), /*#__PURE__*/React.createElement(Badge, {
    variant: f.dir
  }, f.dir === 'gain' ? '▲' : '▼', " ", f.pct), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)',
      width: 56,
      textAlign: 'right'
    }
  }, f.when))))));
}
function CTA() {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      padding: '0 0 90px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--background-dark)',
      borderRadius: 'var(--radius-2xl)',
      padding: '56px 48px',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontSize: 'var(--text-4xl)',
      color: '#fff',
      margin: 0
    }
  }, "Stop skimming. Start ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--brand-strong-dark)'
    }
  }, "understanding"), "."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-lg)',
      color: 'var(--text-secondary-dark)',
      maxWidth: 520,
      margin: '16px auto 32px'
    }
  }, "Your first summary is free \u2014 no signup needed. Join the waitlist for Pro."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      borderRadius: 'var(--radius-full)',
      background: 'var(--brand-dark)',
      color: 'var(--background-dark)',
      padding: '12px 26px',
      fontSize: 'var(--text-base)',
      fontWeight: 600,
      textDecoration: 'none'
    }
  }, "Get started free ", /*#__PURE__*/React.createElement(Ic, {
    name: "arrow-right"
  })), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      borderRadius: 'var(--radius-full)',
      border: '1px solid rgba(255,255,255,0.18)',
      color: '#fff',
      padding: '12px 26px',
      fontSize: 'var(--text-base)',
      fontWeight: 600,
      textDecoration: 'none'
    }
  }, "See a live example")))));
}
function Footer() {
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      borderTop: '1px solid var(--hairline)',
      padding: '48px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/earningsnerd-icon-light.svg",
    width: "28",
    height: "28",
    alt: "",
    className: "dark-hide"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, "\xA9 2026 EarningsNerd. Data from SEC EDGAR. Not investment advice.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 24,
      fontSize: 'var(--text-sm)'
    }
  }, ['Privacy', 'Terms', 'Security'].map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    style: {
      color: 'var(--text-muted)',
      textDecoration: 'none'
    }
  }, l)))));
}

// ════════════════════════════ Toast ════════════════════════════
function Toast({
  msg
}) {
  if (!msg) return null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 24,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 100,
      background: 'var(--background-dark)',
      color: '#fff',
      padding: '12px 20px',
      borderRadius: 'var(--radius-full)',
      boxShadow: 'var(--shadow-e5)',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "sparkle",
    style: {
      width: 16,
      height: 16,
      color: 'var(--brand-strong-dark)'
    }
  }), " ", msg);
}

// ════════════════════════════ App ════════════════════════════
function MarketingApp() {
  const [dark, setDark] = useState(false);
  const [toast, setToast] = useState('');
  useIcons([dark, toast]);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);
  const pick = c => {
    setToast(`Generating summary for ${c.ticker}…`);
    setTimeout(() => setToast(''), 2600);
  };
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Header, {
    dark: dark,
    onToggle: () => setDark(d => !d)
  }), /*#__PURE__*/React.createElement("section", {
    style: {
      padding: '72px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      display: 'grid',
      gridTemplateColumns: '1.1fr 0.9fr',
      gap: 56,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-6xl)',
      lineHeight: 1.05,
      letterSpacing: 'var(--tracking-tight)',
      margin: 0,
      color: 'var(--text-body)'
    }
  }, "Understand any ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent-strong)'
    }
  }, "SEC filing"), " in minutes"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-lg)',
      lineHeight: 1.6,
      color: 'var(--text-muted)',
      maxWidth: 460,
      margin: '24px 0 32px'
    }
  }, "AI-powered summaries that turn 100-page 10-Ks and 10-Qs into clear, decision-ready insights. Financials, risks, and trends \u2014 all in one place."), /*#__PURE__*/React.createElement(Search, {
    autoFocus: true,
    onPick: pick
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      marginTop: 16,
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      color: 'var(--accent-strong)',
      fontWeight: 500,
      textDecoration: 'underline',
      textUnderlineOffset: 4
    }
  }, "See a live example \u2192"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-subtle)'
    }
  }, "Your first summary is free \u2014 no signup needed.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginTop: 24,
      flexWrap: 'wrap'
    }
  }, COMPANIES.slice(0, 6).map(c => /*#__PURE__*/React.createElement("button", {
    key: c.ticker,
    onClick: () => pick(c),
    className: "tabular",
    style: {
      border: '1px solid var(--hairline)',
      background: 'var(--surface-card)',
      borderRadius: 'var(--radius-full)',
      padding: '6px 14px',
      fontSize: 'var(--text-xs)',
      fontWeight: 600,
      color: 'var(--text-muted)',
      cursor: 'pointer'
    }
  }, c.ticker)))), /*#__PURE__*/React.createElement(ExampleCard, null))), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--hairline)',
      borderBottom: '1px solid var(--hairline)',
      padding: '20px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wrap",
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 40,
      color: 'var(--text-subtle)',
      fontSize: 'var(--text-sm)',
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      gap: 8,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "shield-check",
    style: {
      width: 16,
      height: 16
    }
  }), " Sourced from SEC EDGAR"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      gap: 8,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "quotes",
    style: {
      width: 16,
      height: 16
    }
  }), " Evidence-backed citations"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      gap: 8,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Ic, {
    name: "lightning",
    style: {
      width: 16,
      height: 16
    }
  }), " Summaries in under a minute"))), /*#__PURE__*/React.createElement(Trending, {
    onPick: pick
  }), /*#__PURE__*/React.createElement(HowItWorks, null), /*#__PURE__*/React.createElement(CTA, null), /*#__PURE__*/React.createElement(Footer, null), /*#__PURE__*/React.createElement(Toast, {
    msg: toast
  }));
}
window.MarketingApp = MarketingApp;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/MarketingApp.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.StateCard = __ds_scope.StateCard;

__ds_ns.Input = __ds_scope.Input;

})();
