import streamlit as st
import pandas as pd
import json
import os
import shutil
import base64
import serial.tools.list_ports
import html
import time
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2
import importlib
import db_manager
try:
    importlib.reload(db_manager)
except Exception:
    pass

_IMAGE_CACHE = {}

def get_image_data_uri(path, max_dim=220):
    """Converts a local image file to a lightweight cached base64 data URI for instant dashboard rendering."""
    if not path or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        cache_key = (path, mtime, max_dim)
        if cache_key in _IMAGE_CACHE:
            return _IMAGE_CACHE[cache_key]

        img = cv2.imread(path)
        if img is None:
            return None
        h, w = img.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        _, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        b64 = base64.b64encode(buf).decode('utf-8')
        uri = f"data:image/jpeg;base64,{b64}"
        _IMAGE_CACHE[cache_key] = uri
        return uri
    except Exception:
        return None

def load_cctv_frame_bytes():
    """Reads cctv_live.jpg safely with retry logic and full JPEG validation to prevent Windows file-lock race errors."""
    if not os.path.exists("cctv_live.jpg"):
        return None
    for _ in range(4):
        try:
            with open("cctv_live.jpg", "rb") as f:
                data = f.read()
            # Ensure complete JPEG image by verifying Start-of-Image and End-of-Image markers
            if len(data) > 2048 and data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
                return data
        except (PermissionError, OSError, FileNotFoundError):
            time.sleep(0.015)
        except Exception:
            pass
    return None

st.set_page_config(
    page_title="VIT Campus RFID Access & Security Control",
    page_icon="🏢",
    layout="wide"
)

# Launch Telegram Mobile Guard Daemon seamlessly in background (Single Instance)
@st.cache_resource
def init_telegram_service():
    try:
        import telegram_guard
        return telegram_guard.start_background_daemon()
    except Exception:
        return None

try:
    init_telegram_service()
except Exception:
    pass

# Custom CSS for modern enterprise dashboard styling, perfect alignment & zero flickering
st.markdown("""
<style>
/* Modern typography and container spacing */
.stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
    max-width: 100% !important;
}

/* ELIMINATE ALL STREAMLIT FADE / BLINK / STALE ANIMATIONS GLOBALLY */
[data-st-stale="true"],
[data-st-stale="true"] *,
div[data-testid="stFragment"],
div[data-testid="stFragment"] *,
div[data-testid="stVerticalBlock"],
div[data-testid="stVerticalBlock"] *,
div[data-testid="stHorizontalBlock"],
div[data-testid="stHorizontalBlock"] *,
div[data-testid="stAppViewBlockContainer"],
div[data-testid="stAppViewBlockContainer"] *,
.element-container {
    transition: none !important;
    animation: none !important;
    opacity: 1 !important;
    filter: none !important;
}

/* Modern Enterprise Table Styling */
.modern-table-card {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45);
    overflow: hidden;
    margin-top: 12px;
    margin-bottom: 24px;
}

.modern-table-wrapper {
    max-height: 580px;
    overflow-y: auto;
    overflow-x: auto;
    scrollbar-width: thin;
    scrollbar-color: #30363d #0d1117;
}

.modern-table-wrapper::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
.modern-table-wrapper::-webkit-scrollbar-track {
    background: #0d1117;
}
.modern-table-wrapper::-webkit-scrollbar-thumb {
    background: #30363d;
    border-radius: 4px;
}
.modern-table-wrapper::-webkit-scrollbar-thumb:hover {
    background: #58a6ff;
}

.modern-table {
    width: 100%;
    min-width: 980px;
    border-collapse: collapse;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13.5px;
    color: #c9d1d9;
    text-align: left;
}

.modern-table thead th {
    position: sticky;
    top: 0;
    background: #161b22;
    color: #8b949e;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 12px 14px;
    border-bottom: 2px solid #30363d;
    z-index: 10;
    white-space: nowrap;
}

.modern-table tbody tr {
    border-bottom: 1px solid #21262d;
    transition: background 0.15s ease;
}
.modern-table tbody tr:nth-child(even) {
    background: #0d1117;
}
.modern-table tbody tr:nth-child(odd) {
    background: #11161d;
}
.modern-table tbody tr:hover {
    background: #19212c !important;
}

.modern-table tbody td {
    padding: 10px 14px;
    vertical-align: middle;
}

/* Badges & Text Formatting */
.sno-badge {
    color: #8b949e;
    font-weight: 700;
    font-size: 12.5px;
}

.time-badge {
    font-family: 'SF Mono', Consolas, Monaco, monospace;
    font-size: 12.5px;
    color: #e6edf3;
    font-weight: 500;
    white-space: nowrap;
}

.user-name-text {
    font-weight: 600;
    color: #f0f6fc;
    font-size: 13.5px;
    white-space: nowrap;
}

.reg-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-family: 'SF Mono', Consolas, Monaco, monospace;
    font-size: 11.5px;
    font-weight: 600;
    white-space: nowrap;
}

.place-text {
    color: #8b949e;
    font-size: 13px;
    white-space: nowrap;
}

.violation-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #ff7b72;
    background: rgba(248,81,73,0.12);
    border: 1px solid rgba(248,81,73,0.3);
    white-space: nowrap;
}

.details-text {
    color: #c9d1d9;
    font-size: 12.5px;
    line-height: 1.4;
}

.sev-badge {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    white-space: nowrap;
}

/* Status Pills */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.35;
    white-space: normal;
    word-break: break-word;
}
.status-icon {
    font-size: 13px;
    font-weight: 800;
    flex-shrink: 0;
}
.status-pill-granted {
    background: rgba(35, 134, 54, 0.18);
    border: 1px solid #2ea043;
    color: #3fb950;
}
.status-pill-denied {
    background: rgba(218, 54, 51, 0.18);
    border: 1px solid #f85149;
    color: #ff7b72;
}
.status-pill-warning {
    background: rgba(210, 153, 34, 0.18);
    border: 1px solid #d29922;
    color: #e3b341;
}

/* Moment Image Box with Interactive Floating Popover */
.moment-box {
    position: relative;
    display: inline-block;
}
.moment-thumb {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    object-fit: cover;
    border: 2px solid #30363d;
    cursor: zoom-in;
    transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), border-color 0.25s ease, box-shadow 0.25s ease;
    display: block;
}
.moment-box:hover .moment-thumb,
.moment-box:active .moment-thumb {
    border-color: #58a6ff;
    transform: scale(1.12);
    box-shadow: 0 0 10px rgba(88, 166, 255, 0.6);
}

.moment-popover {
    position: absolute;
    right: 56px;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
    z-index: 999999;
    background: #161b22;
    border: 2px solid #58a6ff;
    box-shadow: 0 18px 45px rgba(0, 0, 0, 0.95), 0 0 24px rgba(88, 166, 255, 0.45);
    border-radius: 12px;
    padding: 8px;
    width: 215px;
    text-align: left;
}

.popover-align-top {
    top: -6px;
    transform: scale(0.85);
    transform-origin: top right;
}
.moment-box:hover .popover-align-top,
.moment-box:active .popover-align-top {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: scale(1);
}

.popover-align-bottom {
    bottom: -6px;
    top: auto;
    transform: scale(0.85);
    transform-origin: bottom right;
}
.moment-box:hover .popover-align-bottom,
.moment-box:active .popover-align-bottom {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: scale(1);
}

.popover-align-center {
    top: 50%;
    transform: translateY(-50%) scale(0.85);
    transform-origin: center right;
}
.moment-box:hover .popover-align-center,
.moment-box:active .popover-align-center {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transform: translateY(-50%) scale(1);
}

.popover-img {
    width: 100%;
    height: 165px;
    object-fit: cover;
    border-radius: 8px;
    display: block;
}
.popover-desc {
    padding: 7px 4px 2px 4px;
}
.popover-title {
    font-weight: 700;
    font-size: 13px;
    color: #f0f6fc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.popover-sub {
    font-size: 11px;
    color: #8b949e;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Full-width single-row segmented control tab bar styling (zero wrapping) */
div[data-testid="stSegmentedControl"] {
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    gap: 8px !important;
    margin-bottom: 22px !important;
    width: 100% !important;
}
div[data-testid="stSegmentedControl"] > div {
    display: flex !important;
    flex-wrap: nowrap !important;
    width: 100% !important;
    gap: 8px !important;
}
div[data-testid="stSegmentedControl"] button {
    flex: 1 1 0px !important;
    min-width: 0 !important;
    white-space: nowrap !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    text-align: center !important;
    border: 1px solid #30363d !important;
}

/* Refined Metric Card Styling */
div[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}
div[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: #8b949e !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="stMetricValue"] {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    color: #f0f6fc !important;
}
</style>
""", unsafe_allow_html=True)

DATA_FILE = "access_data.json"
EVIDENCE_DIR = "evidence_snaps"
REGISTERED_FACES_DIR = "registered_faces"
os.makedirs(EVIDENCE_DIR, exist_ok=True)
os.makedirs(REGISTERED_FACES_DIR, exist_ok=True)

# =============================================================================
# VIT Campus Geographic Layout & Pathway Coordinates
# =============================================================================
CAMPUS_LOCATIONS = {
    "Campus Main Gate": {
        "x": 140, "y": 120,
        "type": "GATE",
        "name": "Campus Main Gate",
        "desc": "Main Campus Perimeter Gate (Dual Entry & Exit Turnstiles)"
    },
    "MGR Block": {
        "x": 250, "y": 400,
        "type": "ACADEMIC",
        "name": "Dr. MGR Block",
        "desc": "Central Administration, Classrooms & Auditoriums"
    },
    "TT - Technology Tower": {
        "x": 540, "y": 220,
        "type": "ACADEMIC",
        "name": "Technology Tower (TT)",
        "desc": "Computing Centers, IT Departments & Engineering Labs"
    },
    "SJT - Silver Jubilee Tower": {
        "x": 450, "y": 580,
        "type": "ACADEMIC",
        "name": "Silver Jubilee Tower (SJT)",
        "desc": "School of Computer Science & Software Engineering"
    },
    "PRP Block": {
        "x": 800, "y": 490,
        "type": "ACADEMIC",
        "name": "Periyar Block (PRP)",
        "desc": "Advanced Research Labs & Seminar Complexes (Final Terminal Station)"
    }
}

def get_distance_between(loc1, loc2):
    """Calculates 2D Euclidean distance in meters between any two campus locations."""
    if not loc1 or not loc2 or loc1 == "None" or loc2 == "None" or loc1 == loc2:
        return 0
    p1 = CAMPUS_LOCATIONS.get(loc1)
    p2 = CAMPUS_LOCATIONS.get(loc2)
    if not p1 or not p2:
        return 300
    dx = p1["x"] - p2["x"]
    dy = p1["y"] - p2["y"]
    return int(round((dx**2 + dy**2) ** 0.5))

def plot_campus_map(active_door, users, phone_mode="CO_LOCATED", geo_guard_on=True, geo_dist=0.0, is_within_geofence=True):
    """Draws a high-tech schematic 2D layout map of the VIT Campus with glowing pathways, active reader beacon, and 200m geofence."""
    import matplotlib.patches as patches
    fig, ax = plt.subplots(figsize=(10.5, 6.4), dpi=140, facecolor="#090d16")
    ax.set_facecolor("#0d111a")

    coords = {k: (v["x"], v["y"]) for k, v in CAMPUS_LOCATIONS.items()}

    # 1. Subtle campus architectural perimeter
    perimeter = patches.Polygon(
        [(60, 50), (100, 520), (420, 665), (890, 580), (880, 140), (450, 45)],
        closed=True, facecolor='#0f1624', edgecolor='#1e293b', linewidth=1.2, linestyle=':', alpha=0.6, zorder=0
    )
    ax.add_patch(perimeter)

    # 2. Subtle concentric radar range rings from central quad
    for r in [180, 380, 600]:
        circle = plt.Circle((470, 350), r, color='#172133', fill=False, linestyle=':', linewidth=0.7, alpha=0.45, zorder=0)
        ax.add_patch(circle)

    # 3. Central Academic Quad Area
    quad = patches.Polygon(
        [(230, 380), (440, 555), (520, 235)],
        closed=True, facecolor='#16253b', edgecolor='#1f3352', linewidth=1.0, linestyle=':', alpha=0.32, zorder=0
    )
    ax.add_patch(quad)
    ax.text(380, 370, 'Academic Quad & Central Green', color='#388bfd', fontsize=7.8, style='italic', alpha=0.45, ha='center', va='center', zorder=1)

    # 4. Clean North compass badge (top right)
    ax.text(860, 630, '▲\nN', color='#8b949e', fontsize=8.5, fontweight='bold', ha='center', va='center',
            bbox=dict(boxstyle='circle,pad=0.25', facecolor='#161b22', edgecolor='#30363d', linewidth=1.0), zorder=5)

    # 5. Connected campus avenues & pathways (Planar 2-quad loop without cross-overlapping)
    pathways = [
        ("Campus Main Gate", "MGR Block"),
        ("Campus Main Gate", "TT - Technology Tower"),
        ("MGR Block", "TT - Technology Tower"),
        ("MGR Block", "SJT - Silver Jubilee Tower"),
        ("TT - Technology Tower", "PRP Block"),
        ("SJT - Silver Jubilee Tower", "PRP Block")
    ]

    for start, end in pathways:
        p1 = coords[start]
        p2 = coords[end]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = int(round((dx**2 + dy**2)**0.5))

        # Road underlay (wide dark avenue)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#141c2b', linewidth=8.0, alpha=0.85, zorder=1)
        # Outer pathway blue glow
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#1f6feb', alpha=0.38, linewidth=3.2, zorder=2)
        # Inner crisp dashed line
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#58a6ff', linestyle='--', linewidth=1.3, alpha=0.9, zorder=3)

        # Milestone distance pill offset perpendicularly from center line to prevent overlap
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        L = max(1e-3, (dx**2 + dy**2)**0.5)
        nx, ny = -dy / L * 13, dx / L * 13

        ax.text(
            mx + nx, my + ny, f"{dist}m",
            color="#c9d1d9", fontsize=7.8, fontweight="bold", fontfamily="sans-serif",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#161b22", edgecolor="#30363d", linewidth=1.1, alpha=0.95),
            zorder=4
        )

    colors = {
        "Campus Main Gate": "#2ea043",           # Emerald Green
        "MGR Block": "#d29922",                  # Amber Gold
        "TT - Technology Tower": "#58a6ff",      # Cyan Blue
        "SJT - Silver Jubilee Tower": "#f85149", # Crimson Red
        "PRP Block": "#bc8cff"                   # Violet Purple (Last Station!)
    }

    # 6. Draw station nodes with distinct colors and high-tech glow
    for name, (x, y) in coords.items():
        is_active = (name == active_door)
        marker_color = colors.get(name, "#58a6ff")

        if is_active:
            # Active reader: high-intensity pulsing rings
            ax.scatter(x, y, s=1100, color="#ffffff", alpha=0.08, zorder=5)
            ax.scatter(x, y, s=750, color=marker_color, alpha=0.25, zorder=6)
            ax.scatter(x, y, s=420, color=marker_color, edgecolors="#ffffff", linewidths=2.5, zorder=7)
            ax.scatter(x, y, s=120, color="#ffffff", zorder=8)

            # Active beacon label
            ax.text(
                x, y + 42, f"● {name} [ACTIVE READER]",
                color="#58a6ff", fontsize=8.8, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.32", facecolor="#0d1117", edgecolor="#58a6ff", linewidth=1.4, alpha=0.95),
                zorder=9
            )
        else:
            # Standard node
            ax.scatter(x, y, s=480, color=marker_color, alpha=0.18, zorder=5)
            ax.scatter(x, y, s=260, color=marker_color, edgecolors="#30363d", linewidths=1.8, zorder=6)
            ax.scatter(x, y, s=70, color="#ffffff", alpha=0.9, zorder=7)

            ax.text(
                x, y + 36, f"{name}",
                color="#f0f6fc", fontsize=8.5, fontweight="600", ha="center",
                bbox=dict(boxstyle="round,pad=0.22", facecolor="#161b22", edgecolor="#30363d", linewidth=0.8, alpha=0.9),
                zorder=8
            )

    # 7. Dual-Factor Geofence & Stolen Card Visualizer (Novelty 1)
    if geo_guard_on and active_door in coords:
        ax_pos, ay_pos = coords[active_door]
        geo_col = "#2ea043" if is_within_geofence else "#f85149"

        # 200m Geofence zone radius circle
        geofence_circ = plt.Circle(
            (ax_pos, ay_pos), 105, color=geo_col,
            fill=True, alpha=0.08, linestyle="--", linewidth=1.5, zorder=3
        )
        ax.add_patch(geofence_circ)

        ax.text(
            ax_pos, ay_pos - 120, "200m Geofence Zone",
            color=geo_col, fontsize=7.5, fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#0d1117", edgecolor=geo_col, linewidth=0.8, alpha=0.9),
            zorder=4
        )

        if is_within_geofence:
            px, py = ax_pos + 28, ay_pos - 28
            phone_lbl = f"📱 Phone Co-Located ({geo_dist:.0f}m)"
            ax.scatter(px, py, s=190, color="#2ea043", edgecolors="#ffffff", linewidths=1.6, zorder=10)
            ax.text(
                px, py - 20, phone_lbl,
                color="#39d353", fontsize=7.8, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#04260f", edgecolor="#238636", linewidth=0.8, alpha=0.95),
                zorder=11
            )
        else:
            # Place breach indicator in a dedicated uncluttered region
            px, py = 100, 610
            ax.scatter(px, py, s=260, color="#f85149", edgecolors="#ffffff", linewidths=1.8, zorder=10)
            mode_desc = f"{phone_mode.replace('_', ' ')}: {geo_dist:.0f}m away"
            ax.annotate(
                f"🚨 Phone Breach\n[{mode_desc}]",
                xy=(ax_pos, ay_pos), xytext=(px + 35, py - 10),
                color="#ff7b72", fontsize=7.8, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#290707", edgecolor="#f85149", linewidth=1.0, alpha=0.95),
                arrowprops=dict(arrowstyle="->", color="#f85149", linestyle=":", linewidth=1.4),
                zorder=11
            )

    # 8. Annotate live users inside campus buildings
    for u in users:
        loc = u.get("CurrentBuilding")
        if loc in coords and u.get("Occupancy") == "INSIDE_BUILDING":
            ux, uy = coords[loc]
            first_name = u["Name"].split()[0]
            ax.text(
                ux, uy - 40, f"🟢 {first_name} (Inside)",
                color="#39d353", fontsize=8.2, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#04260f", edgecolor="#238636", linewidth=1.2, alpha=0.95),
                zorder=9
            )
        elif u.get("Occupancy") == "CAMPUS_TRANSIT":
            first_name = u["Name"].split()[0]
            ax.text(
                380, 290, f"🚶 {first_name} (In Transit)",
                color="#58a6ff", fontsize=8.2, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#0c2d6b", edgecolor="#1f6feb", linewidth=1.2, alpha=0.95),
                zorder=9
            )

    ax.set_title("VIT Campus Spatial Topology & Pathway Transit Network", color="#f0f6fc", fontsize=11.5, fontweight="bold", pad=12)
    ax.set_xlim(30, 910)
    ax.set_ylim(20, 680)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
        spine.set_linewidth(1.0)

    plt.tight_layout()
    return fig

def load_data():
    return db_manager.load_data()

def save_data(data):
    db_manager.save_data(data)

current_data = load_data()

# ---------------------------------------------------------
# Sidebar: System Administration & Physical Reader Control
# ---------------------------------------------------------
st.sidebar.markdown("### System Administration")

def get_physical_usb_ports():
    try:
        ports = serial.tools.list_ports.comports()
        usb_ports = []
        for p in ports:
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            # Exclude virtual Bluetooth serial links (e.g., COM3, COM4)
            if "bthenum" in hwid or "bluetooth" in desc:
                continue
            if any(sig in desc or sig in hwid for sig in ["usb", "cp210", "ch340", "arduino", "ftdi", "vid:"]):
                usb_ports.append(p.device)
            elif p.device == "COM5":
                usb_ports.append(p.device)
        return usb_ports
    except Exception:
        return []

usb_ports = get_physical_usb_ports()
hw_status = db_manager.get_hardware_status()

# Dynamically set badge status based on physical USB hardware and serial bridge heartbeat
if hw_status.get("connected") and (time.time() - float(hw_status.get("last_heartbeat", 0)) < 6.0):
    bridge_port = hw_status.get("port", "COM5")
    bridge_badge_text = f"{bridge_port} ONLINE"
    bridge_badge_style = "background:rgba(46,160,67,0.18); color:#3fb950; border:1px solid rgba(46,160,67,0.4);"
    reader_badge_text = "RC522 ACTIVE"
    reader_badge_style = "background:rgba(56,139,253,0.18); color:#58a6ff; border:1px solid rgba(56,139,253,0.4);"
elif usb_ports:
    # Physical USB microcontroller is plugged in, but serial_bridge.py script isn't running yet
    bridge_badge_text = f"{usb_ports[0]} STANDBY"
    bridge_badge_style = "background:rgba(210,153,34,0.18); color:#d29922; border:1px solid rgba(210,153,34,0.4);"
    reader_badge_text = "BRIDGE OFFLINE"
    reader_badge_style = "background:rgba(139,148,158,0.18); color:#8b949e; border:1px solid rgba(139,148,158,0.4);"
else:
    # No physical USB hardware connected
    bridge_badge_text = "DISCONNECTED"
    bridge_badge_style = "background:rgba(248,81,73,0.18); color:#f85149; border:1px solid rgba(248,81,73,0.4);"
    reader_badge_text = "NO HARDWARE"
    reader_badge_style = "background:rgba(139,148,158,0.18); color:#8b949e; border:1px solid rgba(139,148,158,0.4);"

st.sidebar.markdown(f"""
<div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:12px; margin-bottom:14px;">
    <div style="font-size:11px; color:#8b949e; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px; font-weight:600;">Hardware Interface</div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-size:13px; color:#c9d1d9;">Serial Bridge</span>
        <span style="{bridge_badge_style} padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600;">{bridge_badge_text}</span>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-size:13px; color:#c9d1d9;">Reader Node</span>
        <span style="{reader_badge_style} padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600;">{reader_badge_text}</span>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:13px; color:#c9d1d9;">Telegram Guard</span>
        <a href="https://t.me/vit_security_007_bot" target="_blank" style="text-decoration:none;">
            <span style="background:rgba(56,139,253,0.18); color:#58a6ff; border:1px solid rgba(56,139,253,0.4); padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600;">@vit_security_007_bot 🔗</span>
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("#### Hardware Reader Location")
st.sidebar.caption("Assigned location for incoming RFID physical scans:")

door_options = list(CAMPUS_LOCATIONS.keys())

if "sel_active_door" not in st.session_state:
    st.session_state["sel_active_door"] = current_data.get("active_door", "Campus Main Gate")

def on_door_change():
    new_door = st.session_state.get("sel_active_door")
    if new_door:
        db = load_data()
        db["active_door"] = new_door
        save_data(db)

st.sidebar.selectbox(
    "Active Terminal Station",
    door_options,
    key="sel_active_door",
    on_change=on_door_change,
    label_visibility="collapsed"
)

# Security engine policies remain active in backend configuration (hidden from sidebar)
sec_cfg = current_data.get("security_config", {})
is_geo_on = sec_cfg.get("geolocation_guard_enabled", True)
curr_radius = float(sec_cfg.get("geofence_radius_meters", 200.0))

st.sidebar.markdown("---")
st.sidebar.markdown("#### 📱 Cardholder Phone GPS Location")
st.sidebar.caption("Simulate or live-stream the registered student's mobile GPS:")

local_presets = getattr(db_manager, "MOBILE_GPS_PRESETS", {
    "CO_LOCATED": {
        "label": "📱 Co-Located with Student (Standing at Active Reader < 25m)",
        "desc": "Normal legitimate access: phone and RFID card are together"
    },
    "TELEGRAM_LIVE": {
        "label": "📲 Live Telegram Phone GPS (Real 4G/5G Satellite Pin)",
        "desc": "Real live GPS coordinates streamed from smartphone via @vit_security_007_bot"
    },
    "HOSTEL_MH": {
        "label": "🏨 In Hostel (Men's Hostel Block J — 1,480m) [Stolen Card Simulation]",
        "lat": 12.96250,
        "lon": 79.15800,
        "desc": "Card dropped or stolen while student's phone is in hostel room"
    },
    "GAZEBO_FOODYS": {
        "label": "☕ At Gazebo / Foodys Cafeteria (750m) [Geofence Breach]",
        "lat": 12.97020,
        "lon": 79.16250,
        "desc": "Phone left at cafeteria table while card swiped elsewhere"
    },
    "OUTSIDE_CAMPUS": {
        "label": "🚗 Off-Campus Katpadi Junction (3.2 km) [Critical Stolen Card]",
        "lat": 12.97950,
        "lon": 79.13520,
        "desc": "Card stolen by outsider or dropped outside campus perimeter"
    }
})

phone_mode_keys = list(local_presets.keys())
phone_mode_labels = [local_presets[k]["label"] for k in phone_mode_keys]
curr_mode = sec_cfg.get("phone_gps_mode", "CO_LOCATED")
if curr_mode not in phone_mode_keys:
    curr_mode = "CO_LOCATED"
curr_idx = phone_mode_keys.index(curr_mode)

def on_phone_mode_change():
    selected_label = st.session_state.get("sel_phone_mode")
    for k, v in local_presets.items():
        if v["label"] == selected_label:
            db = load_data()
            db["security_config"]["phone_gps_mode"] = k
            save_data(db)
            break

st.sidebar.selectbox(
    "Student Phone GPS Scenario",
    phone_mode_labels,
    index=curr_idx,
    key="sel_phone_mode",
    on_change=on_phone_mode_change,
    label_visibility="collapsed"
)

def reset_occupancy_callback():
    db_manager.reset_all_occupancy()
    st.session_state["sel_active_door"] = "Campus Main Gate"
    st.session_state["occupancy_reset_notice"] = True

st.sidebar.markdown("---")
st.sidebar.markdown("#### Database Maintenance")

st.sidebar.button(
    "🔄 Reset Campus Occupancy",
    width="stretch",
    on_click=reset_occupancy_callback,
    help="Resets all cardholders to 'OUTSIDE' campus without deleting enrolled photos or cards. Perfect for testing campus entry and zone containment."
)

if st.session_state.pop("occupancy_reset_notice", False):
    st.sidebar.success("Occupancy reset! All students set to OUTSIDE campus. Active door set to Main Gate.")

# ---------------------------------------------------------
# Header & KPI Metrics (Clean & Static - Zero Global Flickering)
# ---------------------------------------------------------
st.title("Campus Access & Perimeter Security System")
st.caption("Centralized hardware access management • Zone containment • 1-to-1 SFace Neural Match Guard • Live CCTV Surveillance")

# 5 Clean Metric Cards
total_scans = len(current_data.get("logs", []))
granted_scans = sum(1 for log in current_data.get("logs", []) if "GRANTED" in log.get("Status", ""))
denied_scans = total_scans - granted_scans
total_violations = len(current_data.get("violations", []))
currently_inside = sum(1 for u in current_data.get("users", []) if u.get("Occupancy") in ["INSIDE_BUILDING", "CAMPUS_TRANSIT"])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Events", total_scans)
col2.metric("Access Granted", granted_scans, delta=f"{int(granted_scans/total_scans*100 if total_scans else 0)}% Rate")
col3.metric("Access Denied", denied_scans, delta=f"{denied_scans} Rejected" if denied_scans else "0", delta_color="inverse")
col4.metric("Security Alerts", total_violations, delta=f"{total_violations} Anomalies" if total_violations else "Clear", delta_color="inverse" if total_violations else "normal")
col5.metric("On Campus", currently_inside, delta=f"{currently_inside}/{len(current_data.get('users', []))} Registered")

st.markdown("---")

# ---------------------------------------------------------
# Isolated Top Navigation (Compact Labels - Zero Wrapping - Single Row)
# ---------------------------------------------------------
NAV_OPTIONS = [
    "📋 Live Access", 
    "🚨 Security Audit", 
    "📹 CCTV Monitor",
    "🗺️ Campus Map", 
    "👤 Registry"
]

if "main_nav_tab" not in st.session_state:
    st.session_state["main_nav_tab"] = "📋 Live Access"

selected_tab = st.segmented_control(
    "Navigation Tabs",
    options=NAV_OPTIONS,
    default="📋 Live Access",
    key="main_nav_tab",
    label_visibility="collapsed"
)
if not selected_tab:
    selected_tab = "📋 Live Access"

# Automatically activate RFID enrollment scanner mode whenever admin opens the Registry tab
is_reg_tab = (selected_tab == "👤 Registry")
if db_manager.get_config_val("registration_mode", False) != is_reg_tab:
    db_manager.set_config_val("registration_mode", is_reg_tab)
    current_data["registration_mode"] = is_reg_tab

# Helper Functions: Modern Enterprise HTML Tables with Zero-Truncation & Hover Zoom
def build_live_feed_html(logs, users):
    if not logs:
        return (
            '<div class="modern-table-card" style="padding: 36px 20px; text-align: center; color: #8b949e;">'
            '<div style="font-size: 32px; margin-bottom: 10px;">💳</div>'
            '<div style="font-size: 16px; font-weight: 600; color: #f0f6fc;">Ready for RFID Card Swipes</div>'
            '<div style="font-size: 13px; color: #8b949e; margin-top: 6px;">Present an RFID card at the reader terminal to log biometric identity access events.</div>'
            '</div>'
        )

    # Strict newest-first sorting guarantee: most recent swipe always appears as S.No 1 at the top
    logs_sorted = sorted(
        logs,
        key=lambda x: x.get("id", 0),
        reverse=True
    )

    user_lookup = {}
    for u in users:
        clean_uid = u.get("UID", "").replace(" ", "").upper()
        user_lookup[clean_uid] = u.get("RegNo", "N/A")

    rows_html = []
    num_logs = len(logs_sorted)
    for idx, log in enumerate(logs_sorted):
        s_no = idx + 1
        time_str = html.escape(str(log.get("Time", "--:--:--")))
        user_str = html.escape(str(log.get("User", "Unknown")))

        reg_no = log.get("RegNo")
        if not reg_no or reg_no == "N/A":
            clean_uid = log.get("Card UID", "").replace(" ", "").upper()
            reg_no = user_lookup.get(clean_uid)
            if not reg_no:
                role = log.get("Role", "")
                if "(" in role and ")" in role:
                    reg_no = role.split("(")[-1].split(")")[0]
                elif "Unregistered" in log.get("User", ""):
                    reg_no = "Unregistered"
                else:
                    reg_no = "N/A"
        reg_no_escaped = html.escape(str(reg_no))

        place = html.escape(str(log.get("Place", log.get("Door", "Campus Main Gate"))))
        status = log.get("Status", "Unknown")
        status_escaped = html.escape(str(status))

        snap_path = log.get("Snapshot")
        img_uri = get_image_data_uri(snap_path)

        status_upper = status.upper()
        if "GRANTED" in status_upper:
            status_class = "status-pill-granted"
            status_icon = "✓"
        elif "UNREGISTERED" in status_upper:
            status_class = "status-pill-warning"
            status_icon = "⚠"
        else:
            status_class = "status-pill-denied"
            status_icon = "✕"

        # Popover alignment depending on row position to prevent container clipping
        if idx < 2:
            pop_align = "popover-align-top"
        elif idx >= num_logs - 2:
            pop_align = "popover-align-bottom"
        else:
            pop_align = "popover-align-center"

        if img_uri:
            img_html = (
                f'<div class="moment-box">'
                f'<img src="{img_uri}" class="moment-thumb" alt="Moment Photo" />'
                f'<div class="moment-popover {pop_align}">'
                f'<img src="{img_uri}" class="popover-img" alt="Enlarged Evidence" />'
                f'<div class="popover-desc">'
                f'<div class="popover-title">{user_str}</div>'
                f'<div class="popover-sub">{time_str} • {place}</div>'
                f'</div></div></div>'
            )
        else:
            img_html = '<span style="color:#484f58; font-size:11px; font-weight:500;">No Image</span>'

        if reg_no == "Unregistered":
            reg_style = "color:#e3b341; background:rgba(210,153,34,0.14); border:1px solid rgba(210,153,34,0.35);"
        else:
            reg_style = "color:#58a6ff; background:rgba(56,139,253,0.12); border:1px solid rgba(56,139,253,0.3);"

        row_html = (
            f'<tr>'
            f'<td style="text-align: center;"><span class="sno-badge">{s_no}</span></td>'
            f'<td><span class="time-badge">{time_str}</span></td>'
            f'<td><span class="user-name-text">{user_str}</span></td>'
            f'<td><span class="reg-badge" style="{reg_style}">{reg_no_escaped}</span></td>'
            f'<td><span class="place-text">📍 {place}</span></td>'
            f'<td><span class="status-pill {status_class}"><span class="status-icon">{status_icon}</span><span>{status_escaped}</span></span></td>'
            f'<td style="text-align: center;">{img_html}</td>'
            f'</tr>'
        )
        rows_html.append(row_html)

    tbody_content = "".join(rows_html)

    return (
        f'<div class="modern-table-card">'
        f'<div class="modern-table-wrapper">'
        f'<table class="modern-table">'
        f'<thead><tr>'
        f'<th style="width: 50px; text-align: center;">S.No</th>'
        f'<th style="width: 95px;">Time</th>'
        f'<th style="width: 170px;">Cardholder Name</th>'
        f'<th style="width: 125px;">Reg. No</th>'
        f'<th style="width: 165px;">Terminal Station</th>'
        f'<th>Access Result / Verification</th>'
        f'<th style="width: 95px; text-align: center;">Moment Image</th>'
        f'</tr></thead>'
        f'<tbody>{tbody_content}</tbody>'
        f'</table></div></div>'
    )

def build_audit_table_html(violations, users):
    if not violations:
        return (
            '<div class="modern-table-card" style="padding: 36px 20px; text-align: center; color: #3fb950;">'
            '<div style="font-size: 32px; margin-bottom: 10px;">🛡️</div>'
            '<div style="font-size: 16px; font-weight: 600;">Perimeter Secure</div>'
            '<div style="font-size: 13px; color: #8b949e; margin-top: 6px;">No security anomalies, policy breaches, or facial mismatches detected.</div>'
            '</div>'
        )

    # Strict newest-first sorting guarantee: most recent security anomaly always appears as S.No 1 at the top
    violations_sorted = sorted(
        violations,
        key=lambda x: x.get("id", 0),
        reverse=True
    )

    user_lookup = {}
    for u in users:
        clean_uid = u.get("UID", "").replace(" ", "").upper()
        user_lookup[clean_uid] = u.get("RegNo", "N/A")

    rows_html = []
    num_v = len(violations_sorted)
    for idx, v in enumerate(violations_sorted):
        s_no = idx + 1
        time_str = html.escape(str(v.get("Time", "--:--:--")))
        user_str = html.escape(str(v.get("User", "Unknown")))

        reg_no = v.get("RegNo")
        if not reg_no or reg_no == "N/A":
            clean_uid = v.get("Card UID", "").replace(" ", "").upper()
            reg_no = user_lookup.get(clean_uid)
            if not reg_no:
                reg_no = "Unregistered" if "Unregistered" in v.get("User", "") else "N/A"
        reg_no_escaped = html.escape(str(reg_no))

        v_type = html.escape(str(v.get("ViolationType", "Security Alert")))
        details = html.escape(str(v.get("Details", "Anomaly detected")))
        severity = html.escape(str(v.get("Severity", "HIGH")))
        place = html.escape(str(v.get("Place", v.get("Door", "Campus Main Gate"))))

        snap_path = v.get("Snapshot")
        img_uri = get_image_data_uri(snap_path)

        if severity == "CRITICAL":
            sev_style = "color:#ff7b72; background:rgba(248,81,73,0.18); border:1px solid rgba(248,81,73,0.4);"
        elif severity == "HIGH":
            sev_style = "color:#ffa657; background:rgba(210,153,34,0.18); border:1px solid rgba(210,153,34,0.4);"
        else:
            sev_style = "color:#79c0ff; background:rgba(56,139,253,0.18); border:1px solid rgba(56,139,253,0.4);"

        if reg_no == "Unregistered":
            reg_style = "color:#e3b341; background:rgba(210,153,34,0.14); border:1px solid rgba(210,153,34,0.35);"
        else:
            reg_style = "color:#58a6ff; background:rgba(56,139,253,0.12); border:1px solid rgba(56,139,253,0.3);"

        if idx < 2:
            pop_align = "popover-align-top"
        elif idx >= num_v - 2:
            pop_align = "popover-align-bottom"
        else:
            pop_align = "popover-align-center"

        if img_uri:
            img_html = (
                f'<div class="moment-box">'
                f'<img src="{img_uri}" class="moment-thumb" alt="Forensic Snapshot" />'
                f'<div class="moment-popover {pop_align}">'
                f'<img src="{img_uri}" class="popover-img" alt="Forensic Zoom" />'
                f'<div class="popover-desc">'
                f'<div class="popover-title" style="color:#ff7b72;">⚠️ {v_type}</div>'
                f'<div class="popover-sub">{user_str} • {time_str}</div>'
                f'</div></div></div>'
            )
        else:
            img_html = '<span style="color:#484f58; font-size:11px; font-weight:500;">No Image</span>'

        row_html = (
            f'<tr>'
            f'<td style="text-align: center;"><span class="sno-badge">{s_no}</span></td>'
            f'<td><span class="time-badge">{time_str}</span></td>'
            f'<td><span class="user-name-text">{user_str}</span></td>'
            f'<td><span class="reg-badge" style="{reg_style}">{reg_no_escaped}</span></td>'
            f'<td><span class="violation-badge">{v_type}</span></td>'
            f'<td><span class="details-text">{details}</span></td>'
            f'<td><span class="sev-badge" style="{sev_style}">{severity}</span></td>'
            f'<td><span class="place-text">📍 {place}</span></td>'
            f'<td style="text-align: center;">{img_html}</td>'
            f'</tr>'
        )
        rows_html.append(row_html)

    tbody_content = "".join(rows_html)

    return (
        f'<div class="modern-table-card">'
        f'<div class="modern-table-wrapper">'
        f'<table class="modern-table">'
        f'<thead><tr>'
        f'<th style="width: 50px; text-align: center;">S.No</th>'
        f'<th style="width: 90px;">Time</th>'
        f'<th style="width: 150px;">Cardholder Name</th>'
        f'<th style="width: 115px;">Reg. No</th>'
        f'<th style="width: 175px;">Security Violation</th>'
        f'<th>Forensic Incident Details</th>'
        f'<th style="width: 80px;">Severity</th>'
        f'<th style="width: 145px;">Terminal Station</th>'
        f'<th style="width: 85px; text-align: center;">Evidence Image</th>'
        f'</tr></thead>'
        f'<tbody>{tbody_content}</tbody>'
        f'</table></div></div>'
    )

# =========================================================
# View 1: Live Access Feed (Modern Responsive Table Layout)
# =========================================================
if selected_tab == "📋 Live Access":
    @st.fragment(run_every="1s")
    def render_tab1_feed():
        data = load_data()
        logs = data.get("logs", [])
        users = data.get("users", [])
        st.subheader("Real-Time Access Feed")
        st.caption("Live streaming RFID terminal logs with 1-to-1 biometric facial identity verification")
        if hasattr(st, "html"):
            st.html(build_live_feed_html(logs, users))
        else:
            st.markdown(build_live_feed_html(logs, users), unsafe_allow_html=True)

    render_tab1_feed()

# =========================================================
# View 2: Security Violations & Audit (Full Width)
# =========================================================
elif selected_tab == "🚨 Security Audit":
    st.subheader("Security Violations & Anomaly Audit")
    st.caption("Incidents automatically flagged by Zone Containment, 1-to-1 Facial Identity Verification & Perimeter Gate Policies")

    # Audit & Registry Maintenance Controls
    col_del1, col_del2, col_space = st.columns([1.6, 1.9, 2.5], gap="small")

    with col_del1:
        if st.button("🗑️ Clear Logs & Violations", width="stretch", help="Deletes all event logs, violation incident records, and CCTV snapshots from SQLite database. Enrolled cardholders and photos remain untouched."):
            db_manager.clear_logs_and_violations()
            if os.path.exists(EVIDENCE_DIR):
                for f in os.listdir(EVIDENCE_DIR):
                    try:
                        os.remove(os.path.join(EVIDENCE_DIR, f))
                    except Exception:
                        pass
            st.session_state["audit_msg"] = ("success", "All access logs and security violation records cleared from SQLite database! Enrolled cardholders remain preserved.")
            st.rerun()

    with col_del2:
        if st.button("🗑️ Delete Registered Cardholders Info", width="stretch", help="Deletes all registered student/cardholder profiles and biometric photos from SQLite database. Audit logs and security history are preserved."):
            db_manager.delete_all_users()
            if os.path.exists(REGISTERED_FACES_DIR):
                for f in os.listdir(REGISTERED_FACES_DIR):
                    try:
                        os.remove(os.path.join(REGISTERED_FACES_DIR, f))
                    except Exception:
                        pass
            if os.path.exists("temp_reg_photo.jpg"):
                try:
                    os.remove("temp_reg_photo.jpg")
                except Exception:
                    pass
            st.session_state["audit_msg"] = ("warning", "All registered cardholders, biometrics, and photos have been removed from SQLite database.")
            st.rerun()

    if "audit_msg" in st.session_state:
        m_type, m_text = st.session_state.pop("audit_msg")
        if m_type == "success":
            st.success(m_text)
        else:
            st.warning(m_text)

    st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)

    @st.fragment(run_every="1s")
    def render_tab2_audit():
        data = load_data()
        violations = data.get("violations", [])
        users = data.get("users", [])
        if hasattr(st, "html"):
            st.html(build_audit_table_html(violations, users))
        else:
            st.markdown(build_audit_table_html(violations, users), unsafe_allow_html=True)

    render_tab2_audit()

# =========================================================
# View 3: Terminal CCTV Monitor
# =========================================================
elif selected_tab == "📹 CCTV Monitor":
    active_door_curr = st.session_state.get("sel_active_door", "Campus Main Gate")
    st.subheader("Terminal CCTV Surveillance & Biometric Facial Guard")
    st.caption(f"Active Reader Station: **{active_door_curr}** | Neural Detection: **OpenCV YuNet Deep Learning CNN & SFace**")

    c_cctv, c_diag = st.columns([3, 1.8], gap="medium")

    with c_cctv:
        @st.fragment(run_every="1s")
        def render_cctv_frame():
            active_d = st.session_state.get("sel_active_door", "Campus Main Gate")
            try:
                frame_data = load_cctv_frame_bytes()
                if frame_data is not None:
                    st.session_state["cached_cctv_frame"] = frame_data
                    st.image(frame_data, caption=f"Live CCTV Stream • Stationed at {active_d}", use_container_width=True)
                elif "cached_cctv_frame" in st.session_state and st.session_state["cached_cctv_frame"] is not None:
                    # Seamless fallback to previous clean frame during file I/O contention
                    st.image(st.session_state["cached_cctv_frame"], caption=f"Live CCTV Stream • Stationed at {active_d}", use_container_width=True)
                elif os.path.exists("cctv_live.jpg"):
                    pass
                else:
                    st.info("Terminal CCTV is in Standby mode. Run 'python serial_bridge.py' in the terminal to activate the live video stream.")
            except Exception:
                if "cached_cctv_frame" in st.session_state and st.session_state["cached_cctv_frame"] is not None:
                    try:
                        st.image(st.session_state["cached_cctv_frame"], caption=f"Live CCTV Stream • Stationed at {active_d}", use_container_width=True)
                    except Exception:
                        pass

        render_cctv_frame()

    with c_diag:
        st.markdown(f"""
        <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:14px; font-size:13px; line-height:1.8;">
            <div style="font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:0.5px; font-weight:600; margin-bottom:8px;">Surveillance Node Status</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#8b949e;">Active Station:</span>
                <span style="color:#f0f6fc; font-weight:600;">{active_door_curr}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#8b949e;">Neural AI Model:</span>
                <span style="color:#58a6ff; font-weight:600;">YuNet + SFace CNN</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#8b949e;">Match Threshold:</span>
                <span style="color:#3fb950; font-weight:600;">>= 0.44 Cosine</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#8b949e;">Anti-Theft Lockout:</span>
                <span style="color:#3fb950; font-weight:600;">Active</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:14px; font-size:12.5px; line-height:1.6; color:#c9d1d9;">
            <b style="color:#f0f6fc;">1-to-1 Biometric Anti-Theft Guard:</b><br>
            • <b>Cardholder Identity:</b> Compares live camera face against enrolled reference photo.<br>
            • <b>Cosine Threshold (0.44):</b> True cardholders score ~0.65; friends or impostors score ~0.20-0.37.<br>
            • <i>If an unregistered friend or unauthorized person swipes your card, access is immediately blocked and a security breach is logged!</i>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Recent CCTV Forensic Snapshots")

    snap_files = []
    if os.path.exists(EVIDENCE_DIR):
        try:
            files = [os.path.join(EVIDENCE_DIR, f) for f in os.listdir(EVIDENCE_DIR) if f.endswith(".jpg")]
            files.sort(key=os.path.getmtime, reverse=True)
            snap_files = files[:4]
        except Exception:
            snap_files = []

    if snap_files:
        cols = st.columns(len(snap_files))
        for idx, snap_path in enumerate(snap_files):
            with cols[idx]:
                try:
                    fname = os.path.basename(snap_path)
                    is_viol = "VIOLATION" in fname
                    badge = "VIOLATION" if is_viol else "AUTHORIZED"
                    st.image(snap_path, caption=f"[{badge}] {fname[5:20]}...", use_container_width=True)
                except Exception:
                    pass
    else:
        st.info("No CCTV snapshots recorded yet. Present RFID cards to capture forensic evidence.")

# =========================================================
# View 4: Campus Map & Pathways
# =========================================================
elif selected_tab == "🗺️ Campus Map":
    map_db = load_data()
    active_door_curr = st.session_state.get("sel_active_door", map_db.get("active_door", "Campus Main Gate"))
    users_current = map_db.get("users", [])
    is_geo_on = map_db.get("security_config", {}).get("geolocation_guard_enabled", True)
    geofence_r = float(map_db.get("security_config", {}).get("geofence_radius_meters", 200.0))
    phone_mode = map_db.get("security_config", {}).get("phone_gps_mode", "CO_LOCATED")
    c_lat = float(map_db.get("security_config", {}).get("custom_phone_lat", 12.96918))
    c_lon = float(map_db.get("security_config", {}).get("custom_phone_lon", 79.15593))

    tg_u_lat, tg_u_lon = None, None
    if users_current:
        tg_u_lat = users_current[0].get("PhoneLat")
        tg_u_lon = users_current[0].get("PhoneLon")

    door_gps = db_manager.CAMPUS_GPS.get(active_door_curr, db_manager.CAMPUS_GPS["Campus Main Gate"])
    phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode(
        phone_mode, active_door_curr, custom_lat=c_lat, custom_lon=c_lon, tg_lat=tg_u_lat, tg_lon=tg_u_lon
    )
    geo_dist = db_manager.calculate_geodesic_distance(door_gps["lat"], door_gps["lon"], phone_lat, phone_lon)
    is_within_geofence = (geo_dist <= geofence_r)

    st.subheader("Campus Topology & Dual-Factor Security Engine")
    st.caption(f"Active Reader Station: **{active_door_curr}** `({door_gps['lat']:.5f}°, {door_gps['lon']:.5f}°)` | Geofence Radius: **{geofence_r:.0f}m**")

    # Status Banners for Evaluators
    if is_geo_on:
        if is_within_geofence:
            st.success(f"📍 **Stolen Card Geofence Guard is ACTIVE** &mdash; Cardholder smartphone is co-located at **{active_door_curr}** (Distance: **{geo_dist:.0f}m** &le; {geofence_r:.0f}m). Physical card swipes are authorized.")
        else:
            st.error(f"🚨 **STOLEN CARD GEOFENCE BREACH DETECTED** &mdash; Cardholder smartphone is **{geo_dist:.0f}m away** at **[{phone_label}]** (Allowed Geofence: {geofence_r:.0f}m). Any swipe at `{active_door_curr}` will be immediately **DENIED as a Stolen Card** with forensic camera capture and buzzer alarm!")
    else:
        st.info("ℹ️ **Geolocation Guard is OFF** &mdash; Stolen card co-location checks bypassed. Enable via sidebar.")

    col_map, col_matrix = st.columns([3.2, 1.8], gap="medium")

    with col_map:
        fig = plot_campus_map(
            active_door_curr, users_current, phone_mode=phone_mode, 
            geo_guard_on=is_geo_on, geo_dist=geo_dist, is_within_geofence=is_within_geofence
        )
        st.pyplot(fig)

    with col_matrix:
        st.markdown(f"#### Campus Pathway Matrix from `{active_door_curr}`")
        matrix_data = []
        for bldg, meta in CAMPUS_LOCATIONS.items():
            if bldg == active_door_curr:
                matrix_data.append({
                    "Destination Station": bldg,
                    "Pathway Distance": "0 m",
                    "Station Type": meta.get("type", "ACADEMIC"),
                    "Zone Status": "Current Active Reader"
                })
            else:
                dist = get_distance_between(active_door_curr, bldg)
                matrix_data.append({
                    "Destination Station": bldg,
                    "Pathway Distance": f"{dist} m",
                    "Station Type": meta.get("type", "ACADEMIC"),
                    "Zone Status": "Connected Campus Zone"
                })

        df_matrix = pd.DataFrame(matrix_data)
        st.dataframe(df_matrix, width="stretch", hide_index=True)

        # Geofence & Stolen Card Dispatch Card
        if not is_within_geofence and is_geo_on:
            dispatch_html = f"""
            <div style="background:#290707; border:1px solid #f85149; border-radius:8px; padding:12px; margin-top:14px; font-size:12.5px; line-height:1.6;">
                <div style="font-weight:700; color:#ff7b72; margin-bottom:4px;">📲 PUSH ALERT DISPATCHED TO STUDENT:</div>
                <div style="color:#f0f6fc;"><b>"⚠️ Urgent Security Warning:</b> Someone tried to use your RFID card at <b>{active_door_curr}</b> while your phone was detected at <b>{phone_label}</b> ({geo_dist:.0f}m away). Access blocked & CCTV photo archived!"</div>
            </div>
            """
        else:
            dispatch_html = f"""
            <div style="background:#04260f; border:1px solid #238636; border-radius:8px; padding:12px; margin-top:14px; font-size:12.5px; line-height:1.6;">
                <div style="font-weight:700; color:#39d353; margin-bottom:4px;">📱 MOBILE CO-LOCATION STATUS:</div>
                <div style="color:#f0f6fc;">Dual-Factor Match: Student phone is confirmed at <b>{active_door_curr}</b> ({geo_dist:.0f}m). Ready for authorized cardholder entry.</div>
            </div>
            """
        st.markdown(dispatch_html, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:14px; margin-top:14px; font-size:13px; line-height:1.6;">
            <div style="font-weight:600; color:#f0f6fc; margin-bottom:6px;">Security Rules & Novelty Guard:</div>
            <div style="color:#c9d1d9; margin-bottom:4px;">• <b>Novelty 1 (Stolen Card Geofence):</b> Real-time GPS verification confirms cardholder smartphone is physically at reader location.</div>
            <div style="color:#c9d1d9; margin-bottom:4px;">• <b>Novelty 2 (Spatial Zone Containment):</b> Simultaneous presence across multiple campus buildings is flagged and locked out.</div>
            <div style="color:#c9d1d9;">• <b>Novelty 3 (Biometric Identity Matching):</b> 1-to-1 SFace neural network verifies physical cardholder face against enrolled card.</div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# View 5: Personnel & Registry (100% PURE STATIC - ZERO FLICKERING - SILENT ENROLLMENT)
# =========================================================
elif selected_tab == "👤 Registry":
    st.subheader("Cardholder Registration & Biometric Enrollment")
    st.caption("Swipe your card on the Freeduino reader to automatically fill the UID, then enter your Name, Reg No, and photo:")

    data_tab5 = load_data()
    pending_uid = data_tab5.get("pending_registration_uid") or ""

    # Status Banner & Card Detection:
    if pending_uid:
        # Card already detected: 100% STATIC, NO TIMERS RUNNING!
        st.markdown(f"""
        <div style="background:rgba(46, 160, 67, 0.2); border:1px solid #2ea043; border-radius:8px; padding:12px 18px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-size:11px; color:#3fb950; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">● HARDWARE RFID CARD DETECTED</span>
                <div style="font-size:20px; font-weight:700; color:#f0f6fc; margin-top:2px;">UID: {pending_uid}</div>
            </div>
            <span style="background:#238636; color:#ffffff; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">UID LOCKED IN FORM</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Awaiting swipe: only a small scoped listener runs until the card is swiped
        @st.fragment(run_every="1s")
        def swipe_detector():
            db = load_data()
            scanned = db.get("pending_registration_uid")
            if scanned:
                st.rerun()
            else:
                hw_banner_port = bridge_badge_text if "ONLINE" in bridge_badge_text else "Hardware Reader"
                st.markdown(f"""
                <div style="background:#161b22; border:1px dashed #30363d; border-radius:8px; padding:12px 18px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:11px; color:#58a6ff; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">📡 Scanner Ready</span>
                        <div style="font-size:13px; color:#c9d1d9; margin-top:2px;">Present your RFID card to the Freeduino scanner ({hw_banner_port})...</div>
                    </div>
                    <span style="background:rgba(56, 139, 253, 0.15); color:#58a6ff; border:1px solid rgba(56, 139, 253, 0.4); padding:3px 10px; border-radius:12px; font-size:11px; font-weight:600;">AWAITING SWIPE</span>
                </div>
                """, unsafe_allow_html=True)
        swipe_detector()

    # Form Fields: completely static and immune to DOM re-renders
    col_details, col_photo = st.columns([1.2, 0.8], gap="large")

    with col_details:
        st.markdown("#### Step 1: Cardholder Identity")
        
        # Auto-filled locked UID
        if pending_uid:
            c_uid_show, c_uid_btn = st.columns([2.5, 1.2])
            with c_uid_show:
                st.text_input("RFID Card UID (Auto-Filled from Hardware)", value=pending_uid, disabled=True, key="field_uid_locked")
            with c_uid_btn:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("✖ Scan Another", key="btn_clear_scanned_card", width="stretch"):
                    data_tab5["pending_registration_uid"] = None
                    save_data(data_tab5)
                    st.rerun()
            active_reg_uid = pending_uid
        else:
            manual_input = st.text_input("RFID Card UID", placeholder="Swipe your card on reader, or enter UID here", key="field_uid_manual")
            active_reg_uid = manual_input

        user_fullname = st.text_input("Full Name", placeholder="e.g. Santhoshkumar M", key="field_fullname")
        user_regno = st.text_input("Registration / Roll Number", placeholder="e.g. 23MID0080", key="field_regno")
        user_role = st.selectbox("Role", ["Student", "Faculty", "Security / Staff", "Guest"], key="field_role")
        user_phone = st.text_input("Mobile Phone Number", placeholder="e.g. +91 98765 43210", key="field_phoneno")

        # Telegram Mobile Pairing (Optional during enrollment)
        rec_tg_form = db_manager.get_recent_telegram_users()
        tg_form_opts = ["None / Link Later"]
        tg_form_map = {}
        for tu in rec_tg_form:
            lbl = f"📱 {tu['first_name']} (@{tu['username']} | ID: {tu['chat_id']})"
            tg_form_opts.append(lbl)
            tg_form_map[lbl] = tu['chat_id']
        tg_form_opts.append("✍️ Enter Custom Chat ID")
        sel_reg_tg = st.selectbox("Telegram Mobile Device (Optional)", tg_form_opts, key="field_reg_tg_user")
        manual_reg_tg = ""
        if sel_reg_tg == "✍️ Enter Custom Chat ID":
            manual_reg_tg = st.text_input("Enter Telegram Chat ID", placeholder="e.g. 582910482", key="field_manual_reg_tg")

    with col_photo:
        st.markdown("#### Step 2: Biometric Photo Enrollment")
        st.caption("Provide reference photo for 1-to-1 SFace neural verification:")

        c_snap_btn, c_up_btn = st.columns([1, 1])
        with c_snap_btn:
            if st.button("📸 Capture from Live CCTV", width="stretch"):
                if os.path.exists("cctv_live.jpg"):
                    shutil.copy("cctv_live.jpg", "temp_reg_photo.jpg")
                    st.toast("Captured live CCTV photo!", icon="📸")
                else:
                    st.error("CCTV feed not available. Make sure serial_bridge.py is running.")
        with c_up_btn:
            uploaded_file = st.file_uploader("Upload ID Photo", type=["jpg", "jpeg", "png"], key="field_upload_photo", label_visibility="collapsed")
            if uploaded_file is not None:
                with open("temp_reg_photo.jpg", "wb") as f_out:
                    f_out.write(uploaded_file.getbuffer())
                st.toast("Uploaded photo file!", icon="📁")

        if os.path.exists("temp_reg_photo.jpg"):
            st.image("temp_reg_photo.jpg", caption="Staged Biometric Photo", width=180)
            st.caption("✅ Photo staged and ready to enroll")
        else:
            st.info("No biometric photo staged yet. Click 'Capture from Live CCTV' or upload an ID photo.")

    st.markdown("---")

    # Step 3: Registration Submission (ALL DETAILS MANDATORY)
    if st.button("Complete Cardholder Registration", type="primary", width="stretch"):
        if not active_reg_uid or len(active_reg_uid.strip().replace(" ", "")) < 6:
            st.error("⚠️ RFID Card UID is mandatory! Please swipe your RFID card on the Freeduino reader first.")
        elif not user_fullname or not user_fullname.strip():
            st.error("⚠️ Full Name is mandatory! Please enter the cardholder's Full Name.")
        elif not user_regno or not user_regno.strip():
            st.error("⚠️ Registration / Roll Number is mandatory! Please enter the Registration Number (e.g. 23MID0080).")
        elif not os.path.exists("temp_reg_photo.jpg"):
            st.error("⚠️ Biometric Reference Photo is mandatory! Please click '📸 Capture from Live CCTV' or upload an ID photo before submitting.")
        else:
            formatted_uid = active_reg_uid.strip().upper()
            uid_compact = formatted_uid.replace(" ", "")

            # Check duplicate
            existing_uids = [u["UID"].replace(" ", "").upper() for u in data_tab5.get("users", [])]
            if uid_compact in existing_uids:
                st.error(f"Card UID [{formatted_uid}] is already registered to an existing user!")
            else:
                # Move staged photo to registered_faces (mandatory)
                dest_photo = os.path.join(REGISTERED_FACES_DIR, f"{uid_compact}.jpg")
                shutil.move("temp_reg_photo.jpg", dest_photo)

                chosen_chat_id = "None"
                if sel_reg_tg in tg_form_map:
                    chosen_chat_id = tg_form_map[sel_reg_tg]
                elif manual_reg_tg.strip():
                    chosen_chat_id = manual_reg_tg.strip()

                role_label = f"{user_role} ({user_regno.strip()})"
                new_user = {
                    "Name": user_fullname.strip(),
                    "RegNo": user_regno.strip(),
                    "UID": formatted_uid,
                    "Role": role_label,
                    "Status": "Active",
                    "Occupancy": "OUTSIDE",
                    "CurrentBuilding": "None",
                    "LastLocation": "None",
                    "LastSwipeTime": None,
                    "Photo": f"registered_faces/{uid_compact}.jpg",
                    "PhoneNumber": user_phone.strip() if user_phone else "N/A",
                    "TelegramChatId": chosen_chat_id,
                    "PhoneDeviceName": f"Telegram ({user_fullname.strip()})" if chosen_chat_id != "None" else "Mobile Device",
                    "PhoneGpsMode": "TELEGRAM_LIVE" if chosen_chat_id != "None" else "CO_LOCATED",
                    "PhoneLat": 12.96918,
                    "PhoneLon": 79.15593,
                    "PhoneLastPing": "Never"
                }
                data_tab5["users"].append(new_user)
                data_tab5["pending_registration_uid"] = None
                save_data(data_tab5)

                if chosen_chat_id != "None":
                    try:
                        import telegram_guard
                        telegram_guard.send_registration_confirmation(chosen_chat_id, user_fullname.strip(), user_regno.strip(), formatted_uid)
                    except Exception:
                        pass

                st.success(f"Registered {user_fullname.strip()} ({role_label}) successfully with 1-to-1 Biometric Profile!")
                st.rerun()

    st.markdown("---")
    st.subheader("Authorized Personnel Directory & Live Occupancy")
    
    current_registered = data_tab5.get("users", [])
    if current_registered:
        display_users = []
        for idx, u in enumerate(current_registered):
            u_clean = u["UID"].replace(" ", "").upper()
            has_p = os.path.exists(os.path.join(REGISTERED_FACES_DIR, f"{u_clean}.jpg"))
            tg_id = str(u.get("TelegramChatId", "None"))
            is_tg = (tg_id not in ["None", "", "0"])
            p_lat = float(u.get("PhoneLat", 12.96918))
            p_lon = float(u.get("PhoneLon", 79.15593))
            p_ping = str(u.get("PhoneLastPing", "Never"))
            ping_short = p_ping.split("T")[1][:8] if "T" in p_ping else p_ping

            row = {
                "S.No": idx + 1,
                "Name": u["Name"],
                "Reg.No": u.get("RegNo", "N/A"),
                "Mobile Phone": u.get("PhoneNumber", "N/A"),
                "UID": u["UID"],
                "Role": u["Role"],
                "Occupancy": u.get("Occupancy", "OUTSIDE"),
                "Current Location": u.get("CurrentBuilding", "None"),
                "Biometric ID": "✅ 1-to-1 Enrolled" if has_p else "⚠️ Presence Only",
                "Mobile Phone Guard": "🟢 4G/5G Linked" if is_tg else "⚪ Unlinked",
                "Phone GPS Lat/Lon": f"{p_lat:.4f}°, {p_lon:.4f}°" if is_tg else "Station Default",
                "Last Phone Ping": ping_short if is_tg else "Never"
            }
            display_users.append(row)
        st.dataframe(pd.DataFrame(display_users), width="stretch", hide_index=True)

        st.markdown("""
        <div style="background:#0c1f36; border:1px solid #1f6feb; border-radius:8px; padding:12px 16px; margin-top:14px; margin-bottom:14px; font-size:13px; line-height:1.6;">
            <div style="font-weight:700; color:#58a6ff; margin-bottom:4px;">📱 Telegram Mobile Companion Linking (@vit_security_007_bot):</div>
            <div style="color:#f0f6fc;">Connect a student's smartphone directly from the dashboard or via mobile:</div>
            <div style="color:#c9d1d9; margin-top:4px;">
                • <b>Option A (From Dashboard):</b> Select the student below and choose their detected Telegram account to link instantly!<br>
                • <b>Option B (1-Tap from Phone):</b> Open <a href="https://t.me/vit_security_007_bot" target="_blank" style="color:#58a6ff; font-weight:700;">@vit_security_007_bot</a> on Telegram and tap <b>Start</b>.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🔗 Pair Cardholder to Telegram Mobile & Dispatch Confirmation")
        st.caption("Select any registered cardholder below and connect their Telegram account. The system will automatically dispatch an official registration confirmation directly to their phone!")

        # Build clean mapping from cardholder label to user object
        user_map = {}
        for u in current_registered:
            lbl = f"{u['Name']} ({u.get('RegNo', 'N/A')} • {u.get('PhoneNumber', 'No Phone')} - {u['UID']})"
            user_map[lbl] = u
        user_options = list(user_map.keys())

        # Attempt quick update sync with Telegram bot server
        try:
            import telegram_guard
            telegram_guard.sync_telegram_updates()
        except Exception:
            pass

        rec_tg_users = db_manager.get_recent_telegram_users()
        tg_options = ["🔍 Auto-Detect (Latest Telegram User)"]
        tg_map = {}
        for tu in rec_tg_users:
            label = f"📱 {tu['first_name']} (@{tu['username']} | ID: {tu['chat_id']})"
            tg_options.append(label)
            tg_map[label] = tu['chat_id']
        tg_options.append("✍️ Enter Custom Chat ID")

        c_pair1, c_pair2, c_pair3 = st.columns([2.2, 2.2, 1.8], gap="small")
        sel_user_str = c_pair1.selectbox("Cardholder", user_options, key="sel_tg_cardholder")
        sel_tg_str = c_pair2.selectbox("Detected Telegram Account", tg_options, key="sel_tg_device")

        custom_chat_id = ""
        if sel_tg_str == "✍️ Enter Custom Chat ID":
            custom_chat_id = c_pair2.text_input("Enter Telegram Chat ID", placeholder="e.g. 582910482", key="field_custom_chat_id")

        with c_pair3:
            st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if st.button("📲 Link & Send Message", width="stretch", type="primary", key="btn_link_tg"):
                # Fetch target user from clean map
                target_user = user_map.get(sel_user_str)

                # Fresh update sync
                try:
                    import telegram_guard
                    telegram_guard.sync_telegram_updates()
                    rec_tg_users = db_manager.get_recent_telegram_users()
                except Exception:
                    pass

                target_chat_id = None
                if sel_tg_str in tg_map:
                    target_chat_id = tg_map[sel_tg_str]
                elif sel_tg_str == "🔍 Auto-Detect (Latest Telegram User)":
                    if rec_tg_users:
                        target_chat_id = rec_tg_users[0]['chat_id']
                    else:
                        st.error("No Telegram users detected yet! Please open @vit_security_007_bot on your phone and tap 'Start' first.")
                elif custom_chat_id.strip():
                    target_chat_id = custom_chat_id.strip()

                if target_user and target_chat_id:
                    db_manager.bind_telegram_chat_to_user(target_chat_id, target_user["RegNo"], f"Telegram ({target_user['Name']})")
                    import telegram_guard
                    telegram_guard.send_registration_confirmation(
                        target_chat_id, target_user["Name"], target_user.get("RegNo", "N/A"), target_user["UID"]
                    )
                    st.toast(f"✅ Linked {target_user['Name']} to Telegram!", icon="📲")
                    st.success(f"🎉 Successfully paired **{target_user['Name']}**! Confirmation message sent to Telegram phone (Chat ID: `{target_chat_id}`).")
                    time.sleep(1.2)
                    st.rerun()
                elif not target_user:
                    st.error("Could not resolve cardholder profile. Please re-select from dropdown.")
                elif not target_chat_id and sel_tg_str != "🔍 Auto-Detect (Latest Telegram User)":
                    st.warning("Please enter a valid Telegram Chat ID, or tap Start on @vit_security_007_bot.")
    else:
        st.info("No personnel currently registered in the database. Swipe your RFID card above to enroll!")

