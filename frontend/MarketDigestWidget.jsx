import { useCallback, useEffect, useRef, useState } from "react";

const API_URL =
  typeof window !== "undefined" && window.MARKET_DIGEST_API_URL
    ? window.MARKET_DIGEST_API_URL.replace(/\/$/, "")
    : "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const sentimentColor = (s) => {
  const map = {
    "Extreme Fear": "#ef4444",
    Fear: "#f97316",
    Neutral: "#a3a3a3",
    Greed: "#22c55e",
    "Extreme Greed": "#16a34a",
  };
  return map[s] ?? "#a3a3a3";
};

const scoreBar = (score) => {
  const pct = Math.max(0, Math.min(100, score));
  const color =
    pct >= 70 ? "#22c55e" : pct >= 45 ? "#eab308" : "#ef4444";
  return (
    <div className="mdi-bar-track">
      <div className="mdi-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
};

const DirectionBadge = ({ direction }) => (
  <span
    className="mdi-badge"
    style={{
      background: direction === "LONG" ? "#16a34a22" : "#ef444422",
      color: direction === "LONG" ? "#16a34a" : "#ef4444",
      border: `1px solid ${direction === "LONG" ? "#16a34a" : "#ef4444"}`,
    }}
  >
    {direction === "LONG" ? "▲ LONG" : "▼ SHORT"}
  </span>
);

const ConfidenceRing = ({ value }) => {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "#22c55e" : pct >= 50 ? "#eab308" : "#ef4444";
  const r = 18;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <svg width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r={r} fill="none" stroke="#27272a" strokeWidth="4" />
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 22 22)"
      />
      <text x="22" y="26" textAnchor="middle" fontSize="11" fill={color} fontWeight="700">
        {pct}%
      </text>
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

const SentimentGauge = ({ score, overall }) => {
  const color = sentimentColor(overall);
  const pct = Math.round(score * 100);
  return (
    <div className="mdi-section mdi-sentiment-gauge">
      <div className="mdi-section-label">Market Sentiment</div>
      <div className="mdi-gauge-row">
        <div className="mdi-gauge-score" style={{ color }}>
          {pct}
        </div>
        <div>
          <div className="mdi-gauge-label" style={{ color }}>
            {overall}
          </div>
          <div className="mdi-gauge-track-wrap">{scoreBar(pct)}</div>
          <div className="mdi-gauge-extremes">
            <span>Fear</span>
            <span>Greed</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const SignalCard = ({ signal }) => (
  <div className="mdi-signal-card">
    <div className="mdi-signal-top">
      <span className="mdi-ticker">{signal.ticker}</span>
      <DirectionBadge direction={signal.direction} />
      <span className="mdi-timeframe">{signal.timeframe}</span>
    </div>
    <div className="mdi-signal-body">
      <ConfidenceRing value={signal.confidence} />
      <p className="mdi-rationale">{signal.rationale}</p>
    </div>
  </div>
);

const HotTicker = ({ t, rank }) => {
  const sentColor =
    t.sentiment === "Bullish"
      ? "#22c55e"
      : t.sentiment === "Bearish"
      ? "#ef4444"
      : "#eab308";
  return (
    <div className="mdi-hot-row">
      <span className="mdi-hot-rank">#{rank}</span>
      <span className="mdi-ticker">{t.ticker}</span>
      <span className="mdi-mentions">{t.mentions?.toLocaleString()} mentions</span>
      <span className="mdi-buzz">
        {scoreBar(t.buzz_score)}
        <span style={{ color: sentColor, marginLeft: 6, fontSize: 11 }}>
          {t.sentiment}
        </span>
      </span>
    </div>
  );
};

const SocialPulse = ({ pulse }) => {
  if (!pulse) return null;
  const sources = [
    { key: "reddit", label: "Reddit" },
    { key: "stocktwits", label: "StockTwits" },
  ];
  return (
    <div className="mdi-section">
      <div className="mdi-section-label">Social Pulse</div>
      {sources.map(({ key, label }) => {
        const data = pulse[key];
        if (!data) return null;
        return (
          <div key={key} className="mdi-pulse-row">
            <span className="mdi-pulse-source">{label}</span>
            <span className="mdi-pulse-mood">{data.mood}</span>
            {scoreBar(data.score)}
          </div>
        );
      })}
    </div>
  );
};

const ChipList = ({ items, variant }) => {
  if (!items?.length) return null;
  const color =
    variant === "risk"
      ? { bg: "#7f1d1d22", border: "#ef4444", text: "#fca5a5" }
      : { bg: "#14532d22", border: "#22c55e", text: "#86efac" };
  return (
    <div className="mdi-chip-list">
      {items.map((item, i) => (
        <span
          key={i}
          className="mdi-chip"
          style={{
            background: color.bg,
            border: `1px solid ${color.border}`,
            color: color.text,
          }}
        >
          {item}
        </span>
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Widget
// ---------------------------------------------------------------------------

export default function MarketDigestWidget() {
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [triggerSession, setTriggerSession] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState(null);
  const pollRef = useRef(null);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/digest/latest`);
      if (!res.ok) {
        if (res.status === 404) {
          setError("No digest available yet. Run a digest first.");
        } else {
          throw new Error(`HTTP ${res.status}`);
        }
      } else {
        setDigest(await res.json());
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatest();
    return () => clearTimeout(pollRef.current);
  }, [fetchLatest]);

  const triggerRun = async () => {
    const session = triggerSession.trim() || "manual";
    setTriggering(true);
    setTriggerMsg(null);
    try {
      const res = await fetch(`${API_URL}/digest/run/${encodeURIComponent(session)}`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setTriggerMsg({ ok: true, text: data.message });
      // Poll for new digest after 30 s
      pollRef.current = setTimeout(fetchLatest, 30_000);
    } catch (e) {
      setTriggerMsg({ ok: false, text: e.message });
    } finally {
      setTriggering(false);
    }
  };

  const createdAt = digest?.created_at
    ? new Date(digest.created_at).toLocaleString("en-US", {
        timeZone: "America/New_York",
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  return (
    <>
      <style>{CSS}</style>
      <div className="mdi-root">
        {/* Header */}
        <div className="mdi-header">
          <div>
            <h2 className="mdi-title">Market Intelligence Digest</h2>
            {createdAt && (
              <span className="mdi-subtitle">
                {digest.session} · {createdAt} ET
              </span>
            )}
          </div>
          <button
            className="mdi-btn mdi-btn-ghost"
            onClick={fetchLatest}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
        </div>

        {/* Error state */}
        {error && <div className="mdi-error">{error}</div>}

        {/* Loading skeleton */}
        {loading && !digest && (
          <div className="mdi-skeleton-grid">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="mdi-skeleton" />
            ))}
          </div>
        )}

        {digest && !loading && (
          <div className="mdi-body">
            {/* Row 1 */}
            <div className="mdi-grid-2">
              <SentimentGauge
                score={digest.sentiment_score ?? 0.5}
                overall={digest.overall_sentiment ?? "Neutral"}
              />
              <SocialPulse pulse={digest.social_pulse} />
            </div>

            {/* Macro snapshot */}
            {digest.macro_snapshot && (
              <div className="mdi-section">
                <div className="mdi-section-label">Macro Snapshot</div>
                <p className="mdi-macro-text">{digest.macro_snapshot}</p>
              </div>
            )}

            {/* Swing trade signals */}
            {digest.swing_trade_signals?.length > 0 && (
              <div className="mdi-section">
                <div className="mdi-section-label">Swing Trade Signals</div>
                <div className="mdi-signals-grid">
                  {digest.swing_trade_signals.map((s, i) => (
                    <SignalCard key={i} signal={s} />
                  ))}
                </div>
              </div>
            )}

            {/* Hot tickers */}
            {digest.hot_tickers?.length > 0 && (
              <div className="mdi-section">
                <div className="mdi-section-label">Hot Tickers</div>
                {digest.hot_tickers.map((t, i) => (
                  <HotTicker key={i} t={t} rank={i + 1} />
                ))}
              </div>
            )}

            {/* Action items + Risk flags */}
            <div className="mdi-grid-2">
              {digest.action_items?.length > 0 && (
                <div className="mdi-section">
                  <div className="mdi-section-label">Action Items</div>
                  <ChipList items={digest.action_items} variant="action" />
                </div>
              )}
              {digest.risk_flags?.length > 0 && (
                <div className="mdi-section">
                  <div className="mdi-section-label">Risk Flags</div>
                  <ChipList items={digest.risk_flags} variant="risk" />
                </div>
              )}
            </div>

            {/* Key themes */}
            {digest.key_themes?.length > 0 && (
              <div className="mdi-section">
                <div className="mdi-section-label">Key Themes</div>
                <div className="mdi-theme-list">
                  {digest.key_themes.map((t, i) => (
                    <span key={i} className="mdi-theme-tag">{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Manual run */}
        <div className="mdi-run-panel">
          <div className="mdi-section-label">Manual Run</div>
          <div className="mdi-run-row">
            <input
              className="mdi-input"
              placeholder="Session label (e.g. morning)"
              value={triggerSession}
              onChange={(e) => setTriggerSession(e.target.value)}
            />
            <button
              className="mdi-btn mdi-btn-primary"
              onClick={triggerRun}
              disabled={triggering}
            >
              {triggering ? "Starting…" : "▶ Run Digest"}
            </button>
          </div>
          {triggerMsg && (
            <div
              className="mdi-trigger-msg"
              style={{ color: triggerMsg.ok ? "#86efac" : "#fca5a5" }}
            >
              {triggerMsg.text}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Scoped CSS (injected via <style> tag so the widget is self-contained)
// ---------------------------------------------------------------------------

const CSS = `
.mdi-root {
  font-family: 'Inter', system-ui, sans-serif;
  background: #18181b;
  color: #e4e4e7;
  border-radius: 12px;
  border: 1px solid #3f3f46;
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}
.mdi-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}
.mdi-title { font-size: 18px; font-weight: 700; margin: 0 0 4px; color: #f4f4f5; }
.mdi-subtitle { font-size: 12px; color: #71717a; text-transform: capitalize; }
.mdi-body { display: flex; flex-direction: column; gap: 16px; }
.mdi-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 600px) { .mdi-grid-2 { grid-template-columns: 1fr; } }
.mdi-section {
  background: #27272a;
  border-radius: 8px;
  padding: 14px 16px;
}
.mdi-section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #71717a;
  margin-bottom: 10px;
}
/* Sentiment gauge */
.mdi-gauge-row { display: flex; align-items: center; gap: 16px; }
.mdi-gauge-score { font-size: 48px; font-weight: 800; line-height: 1; min-width: 64px; }
.mdi-gauge-label { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.mdi-gauge-track-wrap { width: 140px; }
.mdi-gauge-extremes { display: flex; justify-content: space-between; font-size: 10px; color: #52525b; margin-top: 2px; width: 140px; }
/* Score bar */
.mdi-bar-track { background: #3f3f46; border-radius: 4px; height: 6px; width: 100%; overflow: hidden; }
.mdi-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
/* Signals */
.mdi-signals-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.mdi-signal-card { background: #18181b; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px; }
.mdi-signal-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.mdi-signal-body { display: flex; align-items: center; gap: 12px; }
.mdi-ticker { font-size: 15px; font-weight: 700; color: #f4f4f5; }
.mdi-timeframe { font-size: 11px; color: #71717a; margin-left: auto; }
.mdi-badge { font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; }
.mdi-rationale { font-size: 12px; color: #a1a1aa; line-height: 1.5; margin: 0; }
/* Hot tickers */
.mdi-hot-row { display: grid; grid-template-columns: 28px 64px 1fr 1fr; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #3f3f46; }
.mdi-hot-row:last-child { border-bottom: none; }
.mdi-hot-rank { font-size: 11px; color: #52525b; }
.mdi-mentions { font-size: 11px; color: #71717a; }
.mdi-buzz { display: flex; align-items: center; }
/* Social pulse */
.mdi-pulse-row { display: grid; grid-template-columns: 80px 70px 1fr; align-items: center; gap: 8px; margin-bottom: 8px; }
.mdi-pulse-source { font-size: 12px; color: #a1a1aa; }
.mdi-pulse-mood { font-size: 12px; font-weight: 600; color: #e4e4e7; }
/* Chips */
.mdi-chip-list { display: flex; flex-wrap: wrap; gap: 6px; }
.mdi-chip { font-size: 11px; padding: 4px 10px; border-radius: 20px; }
/* Themes */
.mdi-theme-list { display: flex; flex-wrap: wrap; gap: 6px; }
.mdi-theme-tag { background: #3f3f46; color: #a1a1aa; font-size: 11px; padding: 3px 10px; border-radius: 20px; }
/* Macro */
.mdi-macro-text { font-size: 13px; line-height: 1.6; color: #a1a1aa; margin: 0; }
/* Run panel */
.mdi-run-panel { margin-top: 18px; border-top: 1px solid #3f3f46; padding-top: 16px; }
.mdi-run-row { display: flex; gap: 8px; margin-top: 8px; }
.mdi-input {
  flex: 1;
  background: #27272a;
  border: 1px solid #3f3f46;
  color: #e4e4e7;
  border-radius: 6px;
  padding: 7px 12px;
  font-size: 13px;
  outline: none;
}
.mdi-input:focus { border-color: #6366f1; }
.mdi-btn {
  border: none;
  border-radius: 6px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.mdi-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mdi-btn-primary { background: #6366f1; color: #fff; }
.mdi-btn-primary:hover:not(:disabled) { background: #4f46e5; }
.mdi-btn-ghost { background: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; }
.mdi-btn-ghost:hover:not(:disabled) { background: #3f3f46; }
.mdi-trigger-msg { font-size: 12px; margin-top: 8px; }
/* Error */
.mdi-error { background: #7f1d1d22; border: 1px solid #ef4444; color: #fca5a5; border-radius: 8px; padding: 12px; margin-bottom: 12px; font-size: 13px; }
/* Skeleton */
.mdi-skeleton-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.mdi-skeleton { height: 120px; background: linear-gradient(90deg, #27272a 25%, #3f3f46 50%, #27272a 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; border-radius: 8px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
`;
