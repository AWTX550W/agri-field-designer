# -*- coding: utf-8 -*-
"""
Harvest Robot Path Visualization
Reads test_viz_output.json, generates matplotlib chart:
- Fruit positions scatter (color = maturity)
- Robot movement trajectory with arrows
- Pick order annotations
"""
import json
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib", "-q"])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize


SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / "test_viz_output.json"
OUT_PATH = SCRIPT_DIR / "harvest_visualization.png"


def load_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def plot_viz(data):
    targets = data["targets"]
    path = data["robot_path"]
    stats = data["stats"]

    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor("#f9f9f9")
    ax.set_facecolor("#f0f4f0")

    # ---- 1. Fruit scatter: color = maturity ----
    maturities = [t["maturity"] for t in targets]
    norm = Normalize(vmin=0.5, vmax=1.0)
    cmap = plt.cm.RdYlGn  # Red (low) -> Green (high)
    colors = [cmap(norm(m)) for m in maturities]

    tx = [t["x"] for t in targets]
    ty = [t["y"] for t in targets]

    ax.scatter(tx, ty, s=260, c=colors, edgecolors="black",
               linewidths=1.8, zorder=5)

    # Fruit index labels
    for i, t in enumerate(targets, 1):
        ax.annotate(f"#{i}", (t["x"], t["y"]),
                    xytext=(0, -20),
                    textcoords="offset points",
                    ha="center", fontsize=10, fontweight="bold",
                    color="#222")

    # Colorbar for maturity
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.82, pad=0.1)
    cbar.set_label("Maturity", fontsize=11, labelpad=10)
    cbar.ax.tick_params(labelsize=9)

    # ---- 2. Robot movement trajectory ----
    move_pts = [p for p in path if p["action"] == "move"]
    pick_pts = [p for p in path if p["action"] == "pick"]

    if move_pts:
        mx = [p["x"] for p in move_pts]
        my = [p["y"] for p in move_pts]
        ax.plot(mx, my, "o-", color="#4A90D9", linewidth=2.5,
                markersize=7, zorder=3, label="Movement Path")
        # Direction arrows
        for i in range(len(mx) - 1):
            dx = mx[i+1] - mx[i]
            dy = my[i+1] - my[i]
            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                ax.annotate("", xy=(mx[i+1], my[i+1]),
                            xytext=(mx[i], my[i]),
                            arrowprops=dict(arrowstyle="->", color="#4A90D9",
                                            lw=1.8, mutation_scale=16),
                            zorder=4)

    # Pick positions with diamond markers
    if pick_pts:
        px = [p["x"] for p in pick_pts]
        py = [p["y"] for p in pick_pts]
        ax.scatter(px, py, s=100, marker="D", color="#FF6600",
                   edgecolors="black", linewidths=1.2, zorder=6, label="Pick Position")

    # Start point
    ax.scatter([0], [0], s=140, c="red", marker="s",
               edgecolors="black", linewidths=1.8, zorder=6, label="Start (0,0)")

    # ---- 3. Pick order numbers on pick positions ----
    priority_colors = {1: "#2E7D32", 2: "#F57F17", 3: "#C62828"}
    priority_labels = {1: "P1", 2: "P2", 3: "P3"}
    for i, t in enumerate(targets, 1):
        pri = t["priority"]
        fc = priority_colors.get(pri, "#333")
        label = priority_labels.get(pri, "")
        ax.annotate(f"M:{t['maturity']:.0%}\n{label}",
                    (t["x"], t["y"]),
                    xytext=(16, 8),
                    textcoords="offset points",
                    fontsize=8.5, color=fc, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.35", fc="white",
                              ec=fc, alpha=0.9))

    # ---- 4. Stats panel ----
    stats_text = (
        f"Fruits: {stats['picking_count']}    "
        f"Total: {stats['total_time(s)']}s    "
        f"Move: {stats['move_time(s)']}s | Pick: {stats['pick_time(s)']}s    "
        f"Avg/fruit: {stats['avg_per_fruit(s)']}s"
    )
    ax.text(0.5, -0.10, stats_text,
            transform=ax.transAxes,
            ha="center", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#e8f4e8", edgecolor="#4A90D9"))

    # ---- Format ----
    ax.set_xlabel("X (m)", fontsize=12)
    ax.set_ylabel("Y (m)", fontsize=12)
    ax.set_title("Agricultural Harvest Robot - Path Planning Visualization",
                fontsize=15, fontweight="bold", pad=14)
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_aspect("equal", adjustable="box")

    # Margins
    all_x = tx + [p["x"] for p in path] + [0]
    all_y = ty + [p["y"] for p in path] + [0]
    margin = 0.8
    ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
    ax.set_ylim(min(all_y) - margin, max(all_y) + margin)

    plt.tight_layout()
    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Done: {OUT_PATH.name}")
    return str(OUT_PATH)


if __name__ == "__main__":
    print("Generating harvest robot visualization...")
    data = load_data()
    # Check stats keys (may be Chinese or English)
    stats = data["stats"]
    # Normalize keys if they are in Chinese
    key_map = {
        "采摘数量": "picking_count",
        "总时间(s)": "total_time(s)",
        "移动时间(s)": "move_time(s)",
        "采摘时间(s)": "pick_time(s)",
        "平均单果时间(s)": "avg_per_fruit(s)",
    }
    normalized = {}
    for k, v in stats.items():
        new_key = key_map.get(k, k)
        normalized[new_key] = v
    data["stats"] = normalized

    out = plot_viz(data)
    print(f"Saved to: {out}")
