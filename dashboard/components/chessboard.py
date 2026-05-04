# Simple chessboard renderer for square-level heatmaps

from __future__ import annotations

import pandas as pd
import streamlit.components.v1 as components

FILES = "abcdefgh"
RANKS = "87654321"

def render_square_heatmap(df: pd.DataFrame, value_col: str = "blunders", value_label: str = "value") -> None:
    values = {row["square"]: row[value_col] for _, row in df.iterrows()} if not df.empty else {}
    max_value = max(values.values(), default=0) or 1

    rows: list[str] = []
    for rank_index, rank in enumerate(RANKS):
        cells: list[str] = []
        for file_index, file_name in enumerate(FILES):
            square = f"{file_name}{rank}"
            value = values.get(square, 0)
            display_value = f"{value:.1f}" if isinstance(value, float) and not value.is_integer() else f"{int(value)}"
            intensity = value / max_value
            base = "#f0d9b5" if (rank_index + file_index) % 2 == 0 else "#769656"
            overlay = f"rgba(191, 90, 69, {0.14 + intensity * 0.66:.2f})" if value else "transparent"
            cells.append(
                f"""
                <div class="kv-square" title="{square}: {value_label} {value}" style="background: linear-gradient({overlay}, {overlay}), {base};">
                    <span>{square}</span><strong>{display_value if value else ''}</strong>
                </div>
                """
            )
        rows.append("".join(cells))

    html = f"""
    <html>
    <head>
      <style>
        html, body {{
          margin: 0;
          padding: 0;
          background: transparent;
          font-family: sans-serif;
        }}
        .kv-board {{
          display: grid;
          grid-template-columns: repeat(8, minmax(34px, 1fr));
          width: 100%;
          max-width: 560px;
          aspect-ratio: 1;
          border: 8px solid #2b2114;
          border-radius: 8px;
          box-shadow: 0 18px 40px rgba(0, 0, 0, 0.32);
          overflow: hidden;
        }}
        .kv-square {{
          position: relative;
          aspect-ratio: 1;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-sizing: border-box;
        }}
        .kv-square span {{
          position: absolute;
          left: 4px;
          top: 2px;
          font-size: 0.7rem;
          color: rgba(43, 33, 20, 0.74);
          line-height: 1;
        }}
        .kv-square strong {{
          font-size: 1.05rem;
          color: #2b2114;
          text-shadow: 0 1px 0 rgba(240, 217, 181, 0.28);
          line-height: 1;
        }}
      </style>
    </head>
    <body>
      <div class="kv-board">{''.join(rows)}</div>
    </body>
    </html>
    """
    components.html(html, height=580, scrolling=False)