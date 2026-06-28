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
  Sparkles,
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
  const [state, setState] = useState({ loading: true, data: fallback, error: null });
  useEffect(() => {
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
      <Sparkles size={20} />
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}

function DataTable({ rows, columns, maxRows = 15, downloadName }) {
  if (!rows?.length) return <EmptyState title="No rows available">Run the pipeline or switch to a populated warehouse.</EmptyState>;
  return (
    <div className="table-wrap">
      {downloadName && (
        <div className="export-row">
          <button className="btn-export" onClick={() => downloadCSV(rows, columns, downloadName)}>
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

function BarChart({ rows, labelKey, valueKey, color = "#d6a94f" }) {
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
          <text key={tick} x="-6" y={yPos(tick) + 4} fill="#9aa58f" fontSize="11" textAnchor="end">
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

function Overview({ health, source }) {
  const { data } = useApi(`/api/overview?source=${source}`, { summary: {}, quality: [] });
  const summary = data.summary || {};
  return (
    <div className="page-grid">
      <div className="metrics">
        <MetricCard icon={UserRound} label="Player profile rows" value={fmt(summary.player_profile_rows)} />
        <MetricCard icon={GitBranch} label="Opening rows" value={fmt(summary.opening_rows)} />
        <MetricCard icon={Clock3} label="Time buckets" value={fmt(summary.time_pressure_rows)} />
        <MetricCard icon={Target} label="Evaluated positions" value={fmt(summary.evaluated_positions)} hint={`${fmt(summary.blunders)} 200cp blunders`} />
      </div>
      <section className="panel hero-panel">
        <div>
          <p className="eyebrow">Active warehouse</p>
          <h2>{health?.duckdb_path || "warehouse not configured"}</h2>
          <p>Use this page to check whether the analytics warehouse, Stockfish rows, quality metrics, and ML artifacts are available before opening deeper tabs.</p>
        </div>
        <div className="board-orbit" aria-hidden="true">
          {Array.from({ length: 16 }).map((_, i) => <span key={i} />)}
        </div>
      </section>
      <section className="panel">
        <h2>Pipeline quality files</h2>
        <DataTable
          rows={data.quality || []}
          columns={[
            { key: "path", label: "File" },
            { key: "status", label: "Status", render: (value) => <StatusBadge status={value} /> },
            { key: "primary_count", label: "Rows" },
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
            <article className={`proof-card ${point.status}`} key={point.label}>
              <StatusBadge status={point.status} />
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
            { key: "status", label: "Status", render: (value) => <StatusBadge status={value === "ready" ? "pass" : "warn"} /> },
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
            { key: "games_count", label: "Games" },
            { key: "white_win_rate", label: "White Win Rate" },
            { key: "black_win_rate", label: "Black Win Rate" },
            { key: "draw_rate", label: "Draw Rate" },
            { key: "most_common_response", label: "Common Response" }
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
            { key: "player", label: "Player", render: (value) => <button className="link-button" onClick={() => setSelected(value)}>{value}</button> },
            { key: "games_played", label: "Games" },
            { key: "avg_win_rate", label: "Win Rate" },
            { key: "avg_elo", label: "Avg Elo" }
          ]}
          maxRows={16}
          downloadName="players.csv"
        />
      </section>
      <section className="panel">
        <h2>{player || "Player profile"}</h2>
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
          <MetricCard icon={Activity} label="Evaluated" value={fmt(data.totals?.evaluated_positions)} />
          <MetricCard icon={Target} label="Blunders" value={fmt(data.totals?.blunders)} />
          <MetricCard icon={BarChart3} label="Max cp loss" value={fmt(data.totals?.max_cp_loss)} />
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
        <BarChart rows={rows} labelKey="time_remaining_bucket" valueKey="games_count" color="#8dbf67" />
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
  return (
    <section className="panel predictor">
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
        <button type="submit" className="btn-predict" disabled={loading}>
          {loading ? "Predicting…" : "Predict blunder probability"}
        </button>
      </form>
      {error && <p className="predict-error">{error}</p>}
      {result?.error && <p className="predict-error">{result.error}</p>}
      {result && !result.error && (
        <div className="predict-result">
          <span className="predict-prob" style={{ color: prob > 0.5 ? "#e07070" : prob > 0.25 ? "#e0b870" : "#7ec87e" }}>
            {(prob * 100).toFixed(1)}%
          </span>
          <span className={`model-verdict ${result.is_blunder ? "diagnostic" : "useful"}`}>
            {result.is_blunder ? "Likely blunder" : "Likely not a blunder"}
          </span>
        </div>
      )}
    </section>
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

function ModelPanel({ data, accent }) {
  if (!data?.available) return <EmptyState title={`${data?.title || "Model"} unavailable`}>Train the matching ML pipeline to populate this section.</EmptyState>;
  const metrics = modelMetrics(data);
  const assets = data.assets || data.models?.pre_game?.assets || {};
  const verdict = modelVerdict(data);
  return (
    <section className={`panel model ${accent}`}>
      <div className="model-head">
        <h2>{data.title}</h2>
        <span className={`model-verdict ${verdict.kind}`}>{verdict.label}</span>
      </div>
      <p className="model-note">{verdict.note}</p>
      <div className="metric-strip">
        {Object.entries(metrics).slice(0, 5).map(([key, value]) => (
          <span key={key}><small>{key.replaceAll("_", " ")}</small><strong>{fmt(value, 3)}</strong></span>
        ))}
      </div>
      <div className="asset-grid">
        {Object.entries(assets).filter(([, src]) => src).slice(0, 3).map(([key, src]) => (
          <figure key={key}>
            <img src={src} alt={key} />
            <figcaption>{key.replaceAll("_", " ")}</figcaption>
          </figure>
        ))}
      </div>
      {data.comparison?.length > 0 && <DataTable rows={data.comparison} columns={Object.keys(data.comparison[0]).map((key) => ({ key, label: key.replaceAll("_", " ") }))} maxRows={6} />}
      {data.cluster_profiles?.length > 0 && <DataTable rows={data.cluster_profiles} columns={Object.keys(data.cluster_profiles[0]).slice(0, 7).map((key) => ({ key, label: key.replaceAll("_", " ") }))} maxRows={8} />}
      {data.feature_importance?.length > 0 && <DataTable rows={data.feature_importance} columns={Object.keys(data.feature_importance[0]).slice(0, 3).map((key) => ({ key, label: key.replaceAll("_", " ") }))} maxRows={8} />}
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
  const state = useApi("/api/data-quality", { cards: [], pass_count: 0, warn_count: 0 });
  const { data } = state;
  return (
    <div className="page-grid">
      <LoadingOrError state={state} />
      <div className="metrics">
        <MetricCard icon={ShieldCheck} label="Passing files" value={fmt(data.pass_count)} />
        <MetricCard icon={Target} label="Warnings" value={fmt(data.warn_count)} />
        <MetricCard icon={Database} label="Quality files" value={fmt(data.cards?.length || 0)} />
        <MetricCard icon={Clock3} label="Latest status" value={data.warn_count ? "Review" : "Clean"} />
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
    <article className={`quality-card ${card.status}`}>
      <div className="quality-card-head">
        <span>{card.kind}</span>
        <StatusBadge status={card.status} />
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
    </article>
  );
}

function StatusBadge({ status }) {
  const label = status === "pass" ? "Pass" : "Review";
  return <strong className={`status-badge ${status}`}>{label}</strong>;
}

function qualityHighlights(card) {
  const payload = card.payload || {};
  if (card.kind === "parser") {
    return [
      ["games seen", fmt(payload.games_seen)],
      ["rows written", fmt(payload.rows_written)],
      ["suspicious", fmt(payload.suspicious_rows)],
      ["parse errors", fmt(payload.parse_errors)]
    ];
  }
  if (card.kind === "bronze") {
    return [
      ["input", fmt(payload.input_count)],
      ["output", fmt(payload.output_count)],
      ["removed", fmt(payload.rows_removed)],
      ["missing id", fmt(payload.missing_game_id)]
    ];
  }
  if (card.kind === "silver") {
    return [
      ["bronze", fmt(payload.bronze_count)],
      ["silver", fmt(payload.silver_count)],
      ["retention", percent(payload.retention)],
      ["clock", percent(payload.clock_coverage)]
    ];
  }
  return [["rows", fmt(card.primary_count)]];
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
