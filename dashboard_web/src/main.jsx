import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Brain,
  Clock3,
  Database,
  Download,
  FileCheck2,
  GitBranch,
  LayoutDashboard,
  Search,
  ShieldCheck,
  Target,
  UserRound
} from "lucide-react";
import "./styles.css";

const NAV_ITEMS = [
  ["overview", LayoutDashboard, "Overview"],
  ["evidence", FileCheck2, "Evidence"],
  ["openings", GitBranch, "Openings"],
  ["players", UserRound, "Players"],
  ["blunders", Target, "Blunders"],
  ["time", Clock3, "Time Pressure"],
  ["ml", Brain, "ML Lab"],
  ["quality", ShieldCheck, "Quality"]
];

const VALID_TABS = new Set(NAV_ITEMS.map(([id]) => id));

function activeTabFromHash() {
  const tab = window.location.hash.replace("#", "");
  return VALID_TABS.has(tab) ? tab : "overview";
}

const api = async (path) => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
};

const fmt = (value, digits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: digits });
  return value;
};

const fmtCompact = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  if (typeof value !== "number") return value;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 100_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const percent = (value) => (value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`);

function downloadCSV(rows, columns, filename) {
  const header = columns.map((col) => col.label).join(",");
  const body = rows
    .map((row) =>
      columns
        .map((col) => {
          const value = row[col.key];
          if (value === null || value === undefined) return "";
          const str = String(value);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    )
    .join("\n");
  const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function useApi(path, fallback) {
  const [state, setState] = useState({ loading: !!path, data: fallback, error: null });
  useEffect(() => {
    if (!path) {
      setState({ loading: false, data: fallback, error: null });
      return;
    }
    let active = true;
    setState({ loading: true, data: fallback, error: null });
    api(path)
      .then((data) => active && setState({ loading: false, data, error: null }))
      .catch((error) => active && setState({ loading: false, data: fallback, error: error.message }));
    return () => {
      active = false;
    };
  }, [path]);
  return state;
}

const PAGE_COPY = {
  overview: "A quick read of the active warehouse, row counts, Stockfish coverage, and quality state.",
  evidence: "Portfolio proof points across local sample data, real samples, benchmark data, ML artifacts, and quality gates.",
  openings: "Opening performance grouped by ECO, family, time control, year, and Elo bucket.",
  players: "Player monthly profile rows with win-rate, Elo, and opening preference signals.",
  blunders: "Stockfish-evaluated position coverage and 200cp blunder hotspots by board square.",
  time: "Clock bucket and phase analysis for time-pressure behavior.",
  ml: "Saved ML artifacts, model cards, metrics, plots, and clustering profiles.",
  quality: "Parser, Bronze, and Silver quality metrics translated from JSON into reviewable cards."
};

function Shell({ active, setActive, health, source, setSource, year, setYear, years, children }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">♞</div>
          <div>
            <strong>KnightVision</strong>
            <span>Chess analytics</span>
          </div>
        </div>
        <nav>
          {NAV_ITEMS.map(([id, Icon, label]) => (
            <a key={id} className={active === id ? "active" : ""} href={`#${id}`} onClick={() => setActive(id)}>
              <Icon size={18} />
              {label}
            </a>
          ))}
        </nav>
        <div className="source-panel">
          <label htmlFor="warehouse-source">Warehouse</label>
          <select id="warehouse-source" value={source} onChange={(event) => setSource(event.target.value)}>
            {(health?.sources || []).map((item) => (
              <option key={item.key} value={item.key} disabled={!item.exists}>
                {item.label}{item.exists ? ` (${item.size_mb} MB)` : " missing"}
              </option>
            ))}
          </select>
        </div>
        <div className="source-panel">
          <label htmlFor="year-filter">Year</label>
          <select id="year-filter" value={year} onChange={(event) => setYear(event.target.value)}>
            <option value="">All years</option>
            {(years || []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">Local warehouse dashboard</p>
            <h1>{NAV_ITEMS.find(([id]) => id === active)?.[2]}</h1>
            <p className="page-subtitle">{PAGE_COPY[active]}</p>
          </div>
          <div className={`status-pill ${health?.status === "ready" ? "ready" : "warn"}`}>
            <Database size={16} />
            {health?.status === "ready" ? "DuckDB ready" : "Warehouse missing"}
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, hint }) {
  return (
    <section className="metric-card">
      <div className="metric-icon">
        <Icon size={18} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {hint && <small>{hint}</small>}
      </div>
    </section>
  );
}

function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <span className="empty-mark">—</span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

function Badge({ status, label }) {
  const variantMap = { pass: "pass", warn: "warn", fail: "fail", missing: "fail" };
  const variant = variantMap[status] || "info";
  const text = label || (status === "pass" ? "Pass" : status === "fail" ? "Fail" : "Review");
  return <span className={`badge badge--${variant}`}>{text}</span>;
}

function DataTable({ rows, columns, maxRows = 15, downloadName }) {
  if (!rows?.length) return <EmptyState title="No rows available">Run the pipeline or switch to a populated warehouse.</EmptyState>;
  return (
    <div className="table-wrap">
      {downloadName && (
        <div className="export-row">
          <button className="btn--outline" onClick={() => downloadCSV(rows, columns, downloadName)}>
            <Download size={14} />
            Export CSV
          </button>
        </div>
      )}
      <table>
        <thead>
          <tr>{columns.map((col) => <th key={col.key}>{col.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, maxRows).map((row, index) => (
            <tr key={index}>
              {columns.map((col) => (
                <td key={col.key}>{col.render ? col.render(row[col.key], row) : fmt(row[col.key], 2)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoadingOrError({ state }) {
  if (state.loading) return <EmptyState title="Loading data">Reading the active DuckDB warehouse.</EmptyState>;
  if (state.error) return <EmptyState title="Dashboard query failed">{state.error}</EmptyState>;
  return null;
}

function BarChart({ rows, labelKey, valueKey, color = "#c8a24a" }) {
  const visible = rows.filter((row) => row?.[labelKey] !== undefined).slice(0, 12);
  const max = Math.max(...visible.map((row) => Number(row[valueKey]) || 0), 1);
  if (!visible.length) return <EmptyState title="No chart rows">This warehouse does not have enough rows for this chart.</EmptyState>;
  return (
    <div className="bar-chart">
      {visible.map((row) => {
        const value = Number(row[valueKey]) || 0;
        return (
          <div className="bar-row" key={`${row[labelKey]}-${value}`}>
            <span>{row[labelKey]}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${Math.max((value / max) * 100, 2)}%`, background: color }} />
            </div>
            <strong>{fmt(value)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function LineChart({ rows, xKey, yKey }) {
  const points = rows
    .map((row) => ({ x: row[xKey], y: Number(row[yKey]) }))
    .filter((point) => Number.isFinite(point.y));
  if (!points.length) return <EmptyState title="No trend rows">Select a player with monthly profile rows.</EmptyState>;
  const min = Math.min(...points.map((point) => point.y));
  const max = Math.max(...points.map((point) => point.y));
  const range = max - min || 1;
  const width = 640;
  const height = 220;
  const topPad = 14;
  const bottomPad = 14;
  const yPos = (value) => height - ((value - min) / range) * (height - topPad - bottomPad) - bottomPad;
  const xPos = (index) => points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xPos(index).toFixed(1)} ${yPos(point.y).toFixed(1)}`)
    .join(" ");
  const yTicks = [min, min + range * 0.25, min + range * 0.5, min + range * 0.75, max];
  return (
    <div className="line-chart">
      <svg viewBox={`-48 0 ${width + 48} ${height}`} role="img" aria-label="Player Elo trend">
        {yTicks.map((tick) => (
          <text key={tick} x="-6" y={yPos(tick) + 4} fill="#7a8270" fontSize="10" textAnchor="end">
            {Math.round(tick)}
          </text>
        ))}
        <path d={path} />
        {points.map((point, index) => (
          <circle key={`${point.x}-${index}`} cx={xPos(index)} cy={yPos(point.y)} r="5" />
        ))}
      </svg>
      <div className="chart-caption">
        <span>{points[0]?.x}</span>
        <strong>{fmt(min)} – {fmt(max)} Elo</strong>
        <span>{points.at(-1)?.x}</span>
      </div>
    </div>
  );
}

function ResultDistBar({ quality }) {
  const card = (quality || []).find(c => c.kind === "silver" && c.payload?.result_counts?.white_win);
  if (!card) return null;
  const { white_win = 0, draw = 0, black_win = 0 } = card.payload.result_counts;
  const total = white_win + draw + black_win || 1;
  const wPct = (white_win / total * 100).toFixed(1);
  const dPct = (draw / total * 100).toFixed(1);
  const bPct = (black_win / total * 100).toFixed(1);
  return (
    <div className="result-dist">
      <div className="result-dist-bar">
        <div style={{ width: `${wPct}%` }} className="rd-white" />
        <div style={{ width: `${dPct}%` }} className="rd-draw" />
        <div style={{ width: `${bPct}%` }} className="rd-black" />
      </div>
      <div className="result-dist-labels">
        <span>White {wPct}%</span>
        <span>Draw {dPct}%</span>
        <span>Black {bPct}%</span>
      </div>
    </div>
  );
}

function Overview({ health, source }) {
  const { data } = useApi(`/api/overview?source=${source}`, { summary: {}, quality: [] });
  const summary = data.summary || {};
  const silverCard = (data.quality || []).find(c => c.kind === "silver" && c.primary_count > 10);
  const totalGames = silverCard?.primary_count;
  return (
    <div className="page-grid">
      <div className="metrics">
        <MetricCard icon={UserRound} label="Players" value={fmtCompact(summary.player_profile_rows)} />
        <MetricCard icon={GitBranch} label="Openings" value={fmtCompact(summary.opening_rows)} />
        <MetricCard icon={Clock3} label="Time buckets" value={fmtCompact(summary.time_pressure_rows)} />
        <MetricCard icon={Target} label="Positions" value={fmtCompact(summary.evaluated_positions)} hint={`${fmtCompact(summary.blunders)} blunders ≥200cp`} />
      </div>
      <section className="panel hero-panel">
        <p className="eyebrow">Active warehouse</p>
        <h2>{health?.duckdb_path || "—"}</h2>
        {totalGames && (
          <p className="hero-total">{fmtCompact(totalGames)} games processed</p>
        )}
        <ResultDistBar quality={data.quality} />
      </section>
      <section className="panel">
        <h2>Pipeline quality files</h2>
        <DataTable
          rows={data.quality || []}
          columns={[
            { key: "path", label: "File" },
            { key: "status", label: "Status", render: (value) => <Badge status={value} /> },
            { key: "primary_count", label: "Rows", render: (v) => fmtCompact(v) },
            { key: "retention", label: "Retention", render: percent },
            { key: "suspicious_rows", label: "Suspicious" }
          ]}
          maxRows={8}
        />
      </section>
    </div>
  );
}

function Evidence() {
  const state = useApi("/api/evidence", { sources: [], proof_points: [], quality: {}, ml: {} });
  const { data } = state;
  return (
    <div className="page-grid">
      <LoadingOrError state={state} />
      <section className="panel">
        <h2>Production-readiness evidence</h2>
        <div className="proof-grid">
          {(data.proof_points || []).map((point) => (
            <article className={`card card--${point.status}`} key={point.label}>
              <Badge status={point.status} />
              <h3>{point.label}</h3>
              <p>{point.evidence}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Warehouse coverage</h2>
        <DataTable
          rows={data.sources}
          columns={[
            { key: "label", label: "Warehouse" },
            { key: "status", label: "Status", render: (value) => <Badge status={value === "ready" ? "pass" : "warn"} /> },
            { key: "size_mb", label: "Size MB" },
            { key: "opening_rows", label: "Openings" },
            { key: "player_rows", label: "Players" },
            { key: "time_pressure_rows", label: "Time pressure" },
            { key: "blunder_rows", label: "Stockfish rows" }
          ]}
        />
      </section>
      <section className="panel">
        <h2>Quality and ML summary</h2>
        <div className="metrics">
          <MetricCard icon={ShieldCheck} label="Quality pass" value={fmt(data.quality?.pass_count)} />
          <MetricCard icon={Target} label="Quality review" value={fmt(data.quality?.warn_count)} />
          <MetricCard icon={Brain} label="ML artifacts" value={`${fmt(data.ml?.available_count)} / 3`} />
          <MetricCard icon={Database} label="Warehouses" value={fmt(data.sources?.length || 0)} />
        </div>
      </section>
    </div>
  );
}

function OpeningRecommender({ source }) {
  const [elo, setElo] = useState(1500);
  const [timeControl, setTimeControl] = useState("blitz");
  const [goal, setGoal] = useState("win");
  const [submitted, setSubmitted] = useState(false);

  const path = submitted
    ? `/api/recommendations/openings?player_elo=${elo}&time_control=${timeControl}&goal=${goal}&source=${source}&limit=8`
    : null;
  const state = useApi(path, { rows: [], count: 0, elo_bucket: null });
  const { data } = state;

  function handleSubmit(e) {
    e.preventDefault();
    setSubmitted(true);
  }

  return (
    <section className="panel">
      <h2>Opening Recommendations</h2>
      <p className="model-note">Get opening suggestions ranked by {goal === "draw" ? "draw rate" : "win rate"} for your Elo range and time control.</p>
      <form className="predict-form" onSubmit={handleSubmit}>
        <div className="predict-fields">
          <label>
            <small>Your Elo</small>
            <input type="number" min="400" max="3500" value={elo} onChange={(e) => { setElo(Number(e.target.value)); setSubmitted(false); }} />
          </label>
          <label>
            <small>Time control</small>
            <select value={timeControl} onChange={(e) => { setTimeControl(e.target.value); setSubmitted(false); }}>
              <option value="bullet">Bullet</option>
              <option value="blitz">Blitz</option>
              <option value="rapid">Rapid</option>
              <option value="classical">Classical</option>
            </select>
          </label>
          <label>
            <small>Goal</small>
            <select value={goal} onChange={(e) => { setGoal(e.target.value); setSubmitted(false); }}>
              <option value="win">Maximise wins</option>
              <option value="draw">Maximise draws</option>
            </select>
          </label>
        </div>
        <button type="submit" className="btn">Find openings</button>
      </form>
      {submitted && data.elo_bucket && (
        <p className="model-note" style={{ marginTop: 10 }}>
          Elo bucket: <strong>{data.elo_bucket}</strong> — {data.count} opening{data.count !== 1 ? "s" : ""} found
        </p>
      )}
      {submitted && data.rows?.length > 0 && (
        <DataTable
          rows={data.rows}
          columns={[
            { key: "eco_code", label: "ECO" },
            { key: "opening_family", label: "Opening" },
            { key: "games_count", label: "Games", render: (v) => fmtCompact(v) },
            { key: goal === "draw" ? "draw_rate" : "white_win_rate", label: goal === "draw" ? "Draw %" : "Win %", render: percent },
            { key: "most_common_response", label: "Response" },
          ]}
          maxRows={8}
          downloadName="recommendations.csv"
        />
      )}
      {submitted && data.rows?.length === 0 && !state.loading && (
        <p className="model-note" style={{ marginTop: 10 }}>No data for this Elo range and time control in the current warehouse.</p>
      )}
    </section>
  );
}

function Openings({ source, year }) {
  const [term, setTerm] = useState("");
  const yearParam = year ? `&year=${year}` : "";
  const path = `/api/openings?opening=${encodeURIComponent(term)}&limit=80&source=${source}${yearParam}`;
  const state = useApi(path, { rows: [] });
  const { data } = state;
  const chartRows = (data.rows || []).slice(0, 12).reverse();
  return (
    <div className="page-grid">
      <LoadingOrError state={state} />
      <OpeningRecommender source={source} />
      <div className="toolbar">
        <Search size={18} />
        <input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Filter opening family, e.g. Sicilian" />
      </div>
      <section className="panel">
        <h2>Top openings by games</h2>
        <BarChart rows={chartRows} labelKey="opening_family" valueKey="games_count" />
      </section>
      <section className="panel">
        <h2>Opening performance</h2>
        <DataTable
          rows={data.rows}
          columns={[
            { key: "eco_code", label: "ECO" },
            { key: "opening_family", label: "Opening" },
            { key: "games_count", label: "Games", render: (v) => fmtCompact(v) },
            { key: "white_win_rate", label: "White Win", render: percent },
            { key: "black_win_rate", label: "Black Win", render: percent },
            { key: "draw_rate", label: "Draw %", render: percent },
            { key: "most_common_response", label: "Response" }
          ]}
          downloadName="openings.csv"
        />
      </section>
    </div>
  );
}

function Players({ source, year }) {
  const [term, setTerm] = useState("");
  const yearParam = year ? `&year=${year}` : "";
  const state = useApi(`/api/players?limit=80&source=${source}&search=${encodeURIComponent(term)}${yearParam}`, { rows: [] });
  const { data } = state;
  const [selected, setSelected] = useState(null);
  const player = selected || data.rows?.[0]?.player || "";
  const detail = useApi(player ? `/api/players/${encodeURIComponent(player)}?source=${source}` : `/api/players/__none__?source=${source}`, { rows: [] });
  const trendRows = detail.data.rows.map((row) => ({ ...row, period: `${row.year}-${String(row.month).padStart(2, "0")}` }));
  return (
    <div className="page-grid two">
      <LoadingOrError state={state} />
      <section className="panel">
        <div className="toolbar inset">
          <Search size={18} />
          <input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Filter players, e.g. alice" />
        </div>
        <h2>Most active players</h2>
        <DataTable
          rows={data.rows}
          columns={[
            { key: "player", label: "Player", render: (value) => <button className="btn--ghost" onClick={() => setSelected(value)}>{value}</button> },
            { key: "games_played", label: "Games", render: (v) => fmt(v, 0) },
            { key: "avg_win_rate", label: "Win %", render: percent },
            { key: "avg_elo", label: "Avg Elo", render: (v) => fmt(v, 0) }
          ]}
          maxRows={16}
          downloadName="players.csv"
        />
      </section>
      <section className="panel">
        <h2 className="entity-title">{player || "Player profile"}</h2>
        <LoadingOrError state={detail} />
        <LineChart rows={trendRows} xKey="period" yKey="avg_elo" />
        <DataTable rows={detail.data.rows} columns={[
          { key: "year", label: "Year" },
          { key: "month", label: "Month" },
          { key: "games_played", label: "Games" },
          { key: "wins", label: "Wins" },
          { key: "losses", label: "Losses" },
          { key: "draws", label: "Draws" }
        ]} maxRows={8} downloadName={player ? `${player}-profile.csv` : undefined} />
      </section>
    </div>
  );
}

function Blunders({ source, year }) {
  const yearParam = year ? `&year=${year}` : "";
  const state = useApi(`/api/blunders/heatmap?source=${source}${yearParam}`, { rows: [], totals: {} });
  const { data } = state;
  const squares = useMemo(() => {
    const map = new Map((data.rows || []).map((row) => [row.square, row]));
    const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const result = [];
    for (let rank = 8; rank >= 1; rank--) {
      for (const file of files) result.push({ square: `${file}${rank}`, ...(map.get(`${file}${rank}`) || {}) });
    }
    return result;
  }, [data.rows]);
  const max = Math.max(...squares.map((s) => s.blunders || 0), 1);
  return (
    <div className="page-grid two">
      <LoadingOrError state={state} />
      <section className="panel">
        <h2>Blunder map</h2>
        <div className="chessboard">
          {squares.map((s, index) => (
            <div key={s.square} className={(Math.floor(index / 8) + index) % 2 === 0 ? "light" : "dark"} style={{ "--heat": (s.blunders || 0) / max }}>
              <span>{s.square}</span>
              {(s.blunders || 0) > 0 && <strong>{s.blunders}</strong>}
            </div>
          ))}
        </div>
        {!data.totals?.blunders && <EmptyState title="No threshold blunders yet">Stockfish rows may exist, but no move crossed the configured 200cp threshold in this warehouse.</EmptyState>}
      </section>
      <section className="panel">
        <div className="metrics compact">
          <MetricCard icon={Activity} label="Evaluated" value={fmtCompact(data.totals?.evaluated_positions)} />
          <MetricCard icon={Target} label="Blunders" value={fmtCompact(data.totals?.blunders)} />
          <MetricCard icon={BarChart3} label="Max cp loss" value={fmtCompact(data.totals?.max_cp_loss)} />
        </div>
        <DataTable rows={data.rows} columns={[
          { key: "square", label: "Square" },
          { key: "evaluated_positions", label: "Evaluated" },
          { key: "blunders", label: "Blunders" },
          { key: "avg_cp_loss", label: "Avg cp loss" },
          { key: "max_cp_loss", label: "Max cp loss" }
        ]} downloadName="blunders-heatmap.csv" />
      </section>
    </div>
  );
}

function TimePressure({ source, year }) {
  const yearParam = year ? `&year=${year}` : "";
  const state = useApi(`/api/time-pressure?source=${source}${yearParam}`, { rows: [] });
  const { data } = state;
  const rows = data.rows || [];
  return (
    <div className="page-grid">
      <LoadingOrError state={state} />
      <section className="panel">
        <h2>Games by clock bucket</h2>
        <BarChart rows={rows} labelKey="time_remaining_bucket" valueKey="games_count" color="#4e8038" />
      </section>
      <section className="panel">
        <h2>Time-pressure metrics</h2>
        <DataTable rows={rows} columns={[
          { key: "time_remaining_bucket", label: "Clock" },
          { key: "game_phase", label: "Phase" },
          { key: "time_control_type", label: "Control" },
          { key: "games_count", label: "Games" },
          { key: "evaluated_positions", label: "Evaluated" },
          { key: "blunder_rate", label: "Blunder Rate" }
        ]} downloadName="time-pressure.csv" />
      </section>
    </div>
  );
}

function BlunderPredictor() {
  const [form, setForm] = useState({
    game_phase: "middlegame",
    time_control_type: "blitz",
    time_remaining_seconds: 15,
    player_elo: 1500,
    ply_number: 40,
    material_balance: 0,
    is_in_check: false,
    square: "",
    year: 2024,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = {
        ...form,
        time_remaining_seconds: form.time_remaining_seconds !== "" ? Number(form.time_remaining_seconds) : null,
        player_elo: Number(form.player_elo),
        ply_number: Number(form.ply_number),
        material_balance: Number(form.material_balance),
        is_in_check: form.is_in_check ? 1 : 0,
        year: Number(form.year),
        square: form.square || null,
      };
      const resp = await fetch("/api/ml/predict/blunder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Prediction failed");
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const prob = result?.blunder_probability;
  const probClass = prob > 0.5 ? "high" : prob > 0.25 ? "mid" : "low";

  return (
    <section className="panel">
      <h2>Live Blunder Prediction</h2>
      <p className="model-note">Submit a position to get a blunder probability from the trained XGBoost model. Requires <code>make train-blunder-model</code> to have been run.</p>
      <form className="predict-form" onSubmit={handleSubmit}>
        <div className="predict-fields">
          <label>
            <small>Game phase</small>
            <select value={form.game_phase} onChange={(e) => set("game_phase", e.target.value)}>
              <option value="opening">Opening</option>
              <option value="middlegame">Middlegame</option>
              <option value="endgame">Endgame</option>
            </select>
          </label>
          <label>
            <small>Time control</small>
            <select value={form.time_control_type} onChange={(e) => set("time_control_type", e.target.value)}>
              <option value="bullet">Bullet</option>
              <option value="blitz">Blitz</option>
              <option value="rapid">Rapid</option>
              <option value="classical">Classical</option>
            </select>
          </label>
          <label>
            <small>Time remaining (s)</small>
            <input type="number" min="0" max="600" value={form.time_remaining_seconds} onChange={(e) => set("time_remaining_seconds", e.target.value)} />
          </label>
          <label>
            <small>Player Elo</small>
            <input type="number" min="400" max="3500" value={form.player_elo} onChange={(e) => set("player_elo", e.target.value)} />
          </label>
          <label>
            <small>Ply number</small>
            <input type="number" min="1" max="300" value={form.ply_number} onChange={(e) => set("ply_number", e.target.value)} />
          </label>
          <label>
            <small>Material balance (cp)</small>
            <input type="number" min="-2000" max="2000" value={form.material_balance} onChange={(e) => set("material_balance", e.target.value)} />
          </label>
          <label>
            <small>Square (opt.)</small>
            <input type="text" maxLength={2} placeholder="e4" value={form.square} onChange={(e) => set("square", e.target.value)} />
          </label>
          <label className="check-label">
            <input type="checkbox" checked={form.is_in_check} onChange={(e) => set("is_in_check", e.target.checked)} />
            <small>In check</small>
          </label>
        </div>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? "Predicting…" : "Predict blunder probability"}
        </button>
      </form>
      {error && <p className="predict-error">{error}</p>}
      {result?.error && <p className="predict-error">{result.error}</p>}
      {result && !result.error && (
        <div className="predict-result">
          <span className={`predict-prob ${probClass}`}>
            {(prob * 100).toFixed(1)}%
          </span>
          <Badge status={result.is_blunder ? "warn" : "pass"} label={result.is_blunder ? "Likely blunder" : "Likely not a blunder"} />
        </div>
      )}
    </section>
  );
}

/* ---- ML visualisation components ---------------------------------------- */

const ACCENT_COLOR = { gold: "var(--amber)", green: "var(--green)", blue: "var(--info-t)" };

function FeatureImportanceChart({ rows, accent, label = "Feature importance" }) {
  if (!rows?.length) return null;
  const max = Math.max(...rows.map((r) => Number(r.importance) || 0), 1);
  const color = ACCENT_COLOR[accent] || "var(--amber)";
  return (
    <div style={{ marginBottom: "var(--s4)" }}>
      <h2>{label}</h2>
      <div className="feat-chart">
        {rows.slice(0, 10).map((row) => {
          const val = Number(row.importance) || 0;
          return (
            <div className="feat-row" key={row.feature}>
              <span className="feat-label">{String(row.feature).replace(/_/g, " ")}</span>
              <div className="feat-track">
                <div className="feat-fill" style={{ width: `${(val / max) * 100}%`, background: color }} />
              </div>
              <span className="feat-val">{val.toFixed(3)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PerClassF1Chart({ rows, accent }) {
  if (!rows?.length) return null;
  const color = ACCENT_COLOR[accent] || "var(--green)";
  const max = Math.max(...rows.map((r) => Number(r.f1_score ?? r.f1 ?? 0)), 1);
  return (
    <div style={{ marginBottom: "var(--s4)" }}>
      <h2>Per-class F1</h2>
      <div className="f1-chart">
        {rows.map((row) => {
          const label = row.class ?? row.outcome ?? row.label ?? "";
          const val = Number(row.f1_score ?? row.f1 ?? 0);
          const h = Math.max((val / max) * 80, 2);
          return (
            <div className="f1-bar" key={label}>
              <div className="f1-bar-track">
                <div className="f1-bar-fill" style={{ height: `${h}px`, background: color }} />
              </div>
              <span className="f1-bar-val">{val.toFixed(2)}</span>
              <span className="f1-bar-label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ClusterProfiles({ rows }) {
  if (!rows?.length) return null;
  const keys = Object.keys(rows[0]).filter((k) => k !== "cluster" && k !== "cluster_id");
  const CLUSTER_COLORS = ["var(--amber)", "var(--green)", "var(--info-t)", "var(--warn-t)", "var(--pass-t)"];
  return (
    <div style={{ marginBottom: "var(--s4)" }}>
      <h2>Cluster profiles</h2>
      <div className="cluster-grid">
        {rows.map((row, i) => (
          <div className="cluster-row" key={i}>
            <div className="cluster-id" style={{ background: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}>
              {row.cluster ?? row.cluster_id ?? i}
            </div>
            <div className="cluster-stats">
              {keys.slice(0, 6).map((k) => (
                <div className="cluster-stat" key={k}>
                  <small>{k.replace(/_/g, " ")}</small>
                  <strong>{fmt(row[k], 2)}</strong>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MLLab() {
  const blunder = useApi("/api/ml/blunder", {});
  const opening = useApi("/api/ml/opening-outcome", {});
  const style = useApi("/api/ml/player-style", {});
  return (
    <div className="page-grid">
      <BlunderPredictor />
      <ModelPanel data={blunder.data} accent="gold" />
      <ModelPanel data={opening.data} accent="green" />
      <ModelPanel data={style.data} accent="blue" />
    </div>
  );
}

const VERDICT_BADGE = { useful: "pass", diagnostic: "warn", exploratory: "info" };

function ModelPanel({ data, accent }) {
  if (!data?.available) return (
    <div className="panel">
      <EmptyState title={`${data?.title || "Model"} not trained`}>
        Run <code>make train-{accent === "gold" ? "blunder" : accent === "green" ? "opening" : "player-style"}-model</code> to populate this section.
      </EmptyState>
    </div>
  );
  const metrics = modelMetrics(data);
  const verdict = modelVerdict(data);

  /* feature importance: direct field or from pre_game sub-model */
  const featRows = data.feature_importance?.length > 0
    ? data.feature_importance
    : data.models?.pre_game?.feature_importance || [];

  /* per-class F1 for opening outcome */
  const f1Rows = data.models?.pre_game?.per_class_f1 || [];

  return (
    <section className={`panel model ${accent}`}>
      <div className="model-head">
        <h2>{data.title}</h2>
        <span className={`badge badge--${VERDICT_BADGE[verdict.kind] || "info"}`}>{verdict.label}</span>
      </div>
      <p className="model-note">{verdict.note}</p>
      <div className="metric-strip">
        {Object.entries(metrics).slice(0, 5).map(([key, value]) => (
          <span key={key}><small>{key.replaceAll("_", " ")}</small><strong>{fmt(value, 3)}</strong></span>
        ))}
      </div>

      {featRows.length > 0 && <FeatureImportanceChart rows={featRows} accent={accent} />}
      {f1Rows.length > 0 && <PerClassF1Chart rows={f1Rows} accent={accent} />}
      {data.cluster_profiles?.length > 0 && <ClusterProfiles rows={data.cluster_profiles} />}

      {data.comparison?.length > 0 && (
        <>
          <h2>Model comparison</h2>
          <DataTable rows={data.comparison} columns={Object.keys(data.comparison[0]).map((key) => ({ key, label: key.replaceAll("_", " ") }))} maxRows={6} />
        </>
      )}
      {data.threshold_metrics?.length > 0 && (
        <>
          <h2>Threshold sweep</h2>
          <DataTable rows={data.threshold_metrics} columns={Object.keys(data.threshold_metrics[0]).slice(0, 5).map((key) => ({ key, label: key.replaceAll("_", " ") }))} maxRows={8} />
        </>
      )}
    </section>
  );
}

function modelMetrics(data) {
  if (data.title === "Opening Outcome Prediction") {
    const pre = data.metrics?.models?.pre_game?.metrics || {};
    const post = data.metrics?.models?.post_game?.metrics || {};
    return {
      pre_accuracy: pre.accuracy,
      pre_macro_f1: pre.macro_f1,
      post_accuracy: post.accuracy,
      post_macro_f1: post.macro_f1,
      post_log_loss: post.log_loss
    };
  }
  return data.metrics?.metrics || data.metrics || {};
}

function modelVerdict(data) {
  if (data.title === "Blunder Prediction Under Time Pressure") {
    return {
      kind: "useful",
      label: "Useful ranking model",
      note: "Rare-event classifier with better ranking signal than baseline; use for screening and interpretation, not absolute move judgment."
    };
  }
  if (data.title === "Opening Outcome Prediction") {
    return {
      kind: "diagnostic",
      label: "Mixed predictive signal",
      note: "Pre-game model is intentionally weak-signal; post-game model is stronger but diagnostic because it uses after-the-game metadata."
    };
  }
  return {
    kind: "exploratory",
    label: "Exploratory clustering",
    note: "Unsupervised personas summarize behavior patterns; clusters are analytical labels, not ground-truth player identities."
  };
}

function Quality() {
  const state = useApi("/api/data-quality", { cards: [], pass_count: 0, warn_count: 0, anomaly_count: 0 });
  const { data } = state;
  return (
    <div className="page-grid">
      <LoadingOrError state={state} />
      <div className="metrics">
        <MetricCard icon={ShieldCheck} label="Passing files" value={fmt(data.pass_count)} />
        <MetricCard icon={Target} label="Warnings" value={fmt(data.warn_count)} />
        <MetricCard icon={Database} label="Quality files" value={fmt(data.cards?.length || 0)} />
        <MetricCard icon={Activity} label="Anomalies" value={fmt(data.anomaly_count ?? 0)} />
      </div>
      <section className="panel">
        <h2>Quality gates</h2>
        <div className="quality-grid">
          {(data.cards || []).map((card) => (
            <QualityCard key={card.path} card={card} />
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Detailed metrics</h2>
        <DataTable
          rows={data.cards}
          columns={[
            { key: "path", label: "Metric File" },
            { key: "status", label: "Status" },
            { key: "primary_count", label: "Rows" },
            { key: "retention", label: "Retention" },
            { key: "clock_coverage", label: "Clock Coverage" },
            { key: "suspicious_rows", label: "Suspicious" },
            { key: "duplicate_game_ids", label: "Duplicate IDs" },
            { key: "rows_removed", label: "Rows Removed" }
          ]}
          maxRows={20}
          downloadName="quality-metrics.csv"
        />
      </section>
    </div>
  );
}

function QualityCard({ card }) {
  const payload = card.payload || {};
  const important = qualityHighlights(card);
  return (
    <article className={`card card--${card.status}`}>
      <div className="card-head">
        <span className="card-kind">{card.kind}</span>
        <Badge status={card.status} />
      </div>
      <h3>{card.path}</h3>
      <div className="quality-facts">
        {important.map(([label, value]) => (
          <span key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
          </span>
        ))}
      </div>
      {payload.result_counts && (
        <div className="mini-list">
          {Object.entries(payload.result_counts).map(([label, value]) => (
            <span key={label}>{label.replace("_", " ")}: {fmt(value)}</span>
          ))}
        </div>
      )}
      {payload.partitions && (
        <div className="mini-list">
          {payload.partitions.slice(0, 3).map((partition, index) => (
            <span key={index}>{partition.year ? `${partition.year}-${String(partition.month).padStart(2, "0")}` : partition.batch_id}: {fmt(partition.count)}</span>
          ))}
        </div>
      )}
      {payload.anomalies?.length > 0 && (
        <div className="anomaly-list">
          <small className="anomaly-label">Anomalies vs previous month</small>
          {payload.anomalies.map((a, i) => (
            <div key={i} className="anomaly-row">
              <span className="anomaly-check">{a.check.replace(/_/g, " ")}</span>
              <span className="anomaly-msg">{a.message}</span>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function qualityHighlights(card) {
  const payload = card.payload || {};
  if (card.kind === "parser") {
    return [
      ["games seen", fmtCompact(payload.games_seen)],
      ["rows written", fmtCompact(payload.rows_written)],
      ["suspicious", fmt(payload.suspicious_rows)],
      ["parse errors", fmt(payload.parse_errors)]
    ];
  }
  if (card.kind === "bronze") {
    return [
      ["input", fmtCompact(payload.input_count)],
      ["output", fmtCompact(payload.output_count)],
      ["removed", fmt(payload.rows_removed)],
      ["missing id", fmt(payload.missing_game_id)]
    ];
  }
  if (card.kind === "silver") {
    return [
      ["bronze", fmtCompact(payload.bronze_count)],
      ["silver", fmtCompact(payload.silver_count)],
      ["retention", percent(payload.retention)],
      ["clock", percent(payload.clock_coverage)]
    ];
  }
  return [["rows", fmtCompact(card.primary_count)]];
}

function App() {
  const [active, setActive] = useState(activeTabFromHash());
  const [source, setSource] = useState("sample");
  const [year, setYear] = useState("");
  const health = useApi(`/api/health?source=${source}`, { status: "loading", counts: {}, sources: [] });
  const yearsState = useApi(`/api/years?source=${source}`, { years: [] });
  useEffect(() => {
    const handleHashChange = () => setActive(activeTabFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);
  const page = {
    overview: <Overview health={health.data} source={source} />,
    evidence: <Evidence />,
    openings: <Openings source={source} year={year} />,
    players: <Players source={source} year={year} />,
    blunders: <Blunders source={source} year={year} />,
    time: <TimePressure source={source} year={year} />,
    ml: <MLLab />,
    quality: <Quality />
  }[active];
  return (
    <Shell
      active={active}
      setActive={setActive}
      health={health.data}
      source={source}
      setSource={setSource}
      year={year}
      setYear={setYear}
      years={yearsState.data.years}
    >
      {page}
    </Shell>
  );
}

createRoot(document.getElementById("root")).render(<App />);
