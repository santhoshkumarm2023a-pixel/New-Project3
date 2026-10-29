import base64
import os

def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

img1_b64 = img_to_base64("screenshots/screenshot1_live_access_feed.png")
img2_b64 = img_to_base64("screenshots/screenshot2_user_card_registry.png")
img3_b64 = img_to_base64("screenshots/screenshot3_access_analytics.png")

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project Report - Santhoshkumar M (23MID0080)</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap');

    :root {{
        --primary: #1e40af;
        --primary-light: #eff6ff;
        --primary-dark: #1e3a8a;
        --secondary: #0d9488;
        --text: #1f2937;
        --text-muted: #4b5563;
        --border: #e5e7eb;
        --card-bg: #f9fafb;
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: var(--text);
        line-height: 1.6;
        background-color: #f3f4f6;
        padding: 30px 15px;
    }}

    .document-container {{
        max-width: 900px;
        margin: 0 auto;
        background: #ffffff;
        padding: 48px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }}

    .header-banner {{
        border-bottom: 2px solid var(--primary);
        padding-bottom: 24px;
        margin-bottom: 28px;
    }}

    .sub-tag {{
        display: inline-block;
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--primary);
        background: var(--primary-light);
        padding: 4px 12px;
        border-radius: 9999px;
        margin-bottom: 12px;
    }}

    h1.doc-title {{
        font-size: 1.75rem;
        font-weight: 700;
        color: #111827;
        line-height: 1.3;
        margin-bottom: 20px;
    }}

    .meta-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px 20px;
    }}

    .meta-item {{
        display: flex;
        font-size: 0.92rem;
    }}

    .meta-label {{
        font-weight: 600;
        color: #374151;
        width: 150px;
        flex-shrink: 0;
    }}

    .meta-value {{
        color: #111827;
        font-weight: 500;
    }}

    .section-title {{
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--primary-dark);
        margin-top: 36px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .quote-box {{
        background: #f8fafc;
        border-left: 4px solid var(--primary);
        padding: 16px 20px;
        border-radius: 0 8px 8px 0;
        margin: 12px 0;
        font-size: 0.98rem;
        color: #334155;
        font-style: italic;
    }}

    .figure-container {{
        margin: 24px 0 28px 0;
        background: #ffffff;
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }}

    .figure-title {{
        background: #f8fafc;
        padding: 10px 16px;
        font-weight: 600;
        font-size: 0.95rem;
        color: #1e293b;
        border-bottom: 1px solid var(--border);
    }}

    .figure-img-wrapper {{
        background: #111827;
        text-align: center;
        padding: 8px;
    }}

    .figure-img-wrapper img {{
        max-width: 100%;
        height: auto;
        border-radius: 6px;
        display: block;
        margin: 0 auto;
    }}

    .figure-caption {{
        padding: 12px 16px;
        font-size: 0.88rem;
        color: var(--text-muted);
        background: #ffffff;
        border-top: 1px solid var(--border);
        line-height: 1.5;
    }}

    .tier-list {{
        list-style: none;
        margin: 14px 0;
    }}

    .tier-item {{
        margin-bottom: 14px;
        padding: 12px 16px;
        border-radius: 8px;
        background: var(--card-bg);
        border: 1px solid var(--border);
    }}

    .tier-item strong {{
        color: var(--primary);
        display: inline-block;
        margin-bottom: 4px;
    }}

    .diagram-container {{
        background: #0f172a;
        color: #e2e8f0;
        font-family: 'Fira Code', monospace;
        font-size: 0.8rem;
        padding: 20px;
        border-radius: 8px;
        overflow-x: auto;
        line-height: 1.45;
        margin: 18px 0;
    }}

    .hosting-box {{
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        border-radius: 8px;
        padding: 18px 20px;
        margin-top: 12px;
    }}

    .hosting-status {{
        font-weight: 700;
        color: #065f46;
        font-size: 1rem;
        margin-bottom: 8px;
    }}

    .hosting-reason {{
        font-size: 0.92rem;
        color: #047857;
        line-height: 1.6;
    }}

    .action-print {{
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: var(--primary);
        color: white;
        padding: 12px 24px;
        border-radius: 50px;
        text-decoration: none;
        font-weight: 600;
        box-shadow: 0 4px 14px rgba(30, 64, 175, 0.4);
        cursor: pointer;
        border: none;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: transform 0.2s, background 0.2s;
    }}

    .action-print:hover {{
        background: var(--primary-dark);
        transform: translateY(-2px);
    }}

    @media print {{
        body {{
            background: #ffffff;
            padding: 0;
        }}
        .document-container {{
            box-shadow: none;
            padding: 0;
            max-width: 100%;
        }}
        .action-print {{
            display: none !important;
        }}
        .figure-container {{
            page-break-inside: avoid;
        }}
        .diagram-container {{
            background: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
        }}
    }}
</style>
</head>
<body>

<div class="document-container">
    <!-- Header -->
    <div class="header-banner">
        <span class="sub-tag">Lab Project Report Submission</span>
        <h1 class="doc-title">IoT-Based Smart RFID Authentication and Access Control Management System</h1>
        
        <div class="meta-grid">
            <div class="meta-item">
                <span class="meta-label">Student Name:</span>
                <span class="meta-value">Santhoshkumar M</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Register Number:</span>
                <span class="meta-value">23MID0080</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Subject Code & Name:</span>
                <span class="meta-value">CSI3007 - Advance Python Programming</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Submission Date:</span>
                <span class="meta-value">8th October 2026</span>
            </div>
        </div>
    </div>

    <!-- 1. Title -->
    <h2 class="section-title">1. Title</h2>
    <p style="font-size: 1.05rem; font-weight: 600; color: #1e3a8a;">
        IoT-Based Smart RFID Authentication and Access Control Management System
    </p>

    <!-- 2. What's your website do? -->
    <h2 class="section-title">2. What's your website do? (in 2 lines)</h2>
    <div class="quote-box">
        A centralized security dashboard that authenticates RFID card scans from an Arduino reader in real time, granting or denying entry based on authorized credentials. It provides live access logs, card registration, and manual security controls for monitoring secure access points.
    </div>

    <!-- 3. Frontend [screenshots] -->
    <h2 class="section-title">3. Frontend (Screenshots)</h2>
    <p style="font-size: 0.95rem; color: var(--text-muted); margin-bottom: 16px;">
        The frontend was engineered in Python using the Streamlit framework, delivering a responsive dark-mode monitoring interface with real-time hardware telemetry and administration forms:
    </p>

    <!-- Figure 1 -->
    <div class="figure-container">
        <div class="figure-title">Figure 1: Main Overview & Live Access Logs Feed</div>
        <div class="figure-img-wrapper">
            <img src="data:image/png;base64,{img1_b64}" alt="Live Access Feed Screenshot">
        </div>
        <div class="figure-caption">
            <strong>Description:</strong> Visualizes key telemetry stat cards (Total Scans Today, Access Granted, Access Denied, Registered Cards), hardware connection indicators in the left sidebar showing active communication with <code>Arduino UNO (COM3)</code> and the <code>RC522 RFID Reader</code>, test swipe simulation triggers, and an automated tabular log feed detailing timestamps, user names, card UIDs, roles, access statuses, and assigned door entrances.
        </div>
    </div>

    <!-- Figure 2 -->
    <div class="figure-container">
        <div class="figure-title">Figure 2: User & Card Registration Registry</div>
        <div class="figure-img-wrapper">
            <img src="data:image/png;base64,{img2_b64}" alt="User and Card Registry Screenshot">
        </div>
        <div class="figure-caption">
            <strong>Description:</strong> The card management registry allows security personnel to register new tags by providing a Full Name, RFID UID (e.g. hexadecimal string), and assigned organizational role (Student, Faculty, Staff). New entries immediately update the Authorized Users Database table on the right.
        </div>
    </div>

    <!-- Figure 3 -->
    <div class="figure-container">
        <div class="figure-title">Figure 3: Access Analytics & Verification Breakdown</div>
        <div class="figure-img-wrapper">
            <img src="data:image/png;base64,{img3_b64}" alt="Access Analytics Screenshot">
        </div>
        <div class="figure-caption">
            <strong>Description:</strong> Real-time analytics view plotting two vital security breakdown bar charts: <em>Access Verification Breakdown</em> (proportion of Granted vs. Denied swipe events) and <em>Registered Users by Role</em> (distribution across Student, Faculty, and Staff demographics) for trend identification and anomaly detection.
        </div>
    </div>

    <!-- 4. Backend architecture -->
    <h2 class="section-title">4. Backend Architecture</h2>
    <p style="font-size: 0.95rem; color: var(--text-muted); margin-bottom: 12px;">
        The system implements a four-tier embedded IoT architecture designed for deterministic low latency, hardware safety, and seamless Python data streaming:
    </p>

    <ul class="tier-list">
        <li class="tier-item">
            <strong>1. Edge Hardware Layer:</strong><br>
            Arduino UNO microcontroller connected to the MFRC522 RFID reader module via the SPI (Serial Peripheral Interface) bus (Pins 9–13) at 13.56 MHz, together with output actuators (Green LED, Red LED, and Active Buzzer).
        </li>
        <li class="tier-item">
            <strong>2. Communication Bridge Layer:</strong><br>
            USB UART Serial communication running at 9600 baud rate bridges the physical tag reading events between the edge microcontroller and the host workstation.
        </li>
        <li class="tier-item">
            <strong>3. Application & Verification Layer:</strong><br>
            Python core application engine processes incoming hexadecimal UID packets, performs query lookups against authorized user dictionaries, validates access rules, and returns acknowledgment control bytes back to the Arduino (<code>'G'</code> for Granted, <code>'D'</code> for Denied).
        </li>
        <li class="tier-item">
            <strong>4. Presentation Layer:</strong><br>
            Python Streamlit web application providing real-time telemetry rendering, manual swipe simulation, credential onboarding forms, and interactive analytics.
        </li>
    </ul>

    <div class="diagram-container"><pre>[RFID Tag / Card (13.56 MHz)]
             │
             ▼
    [RC522 RFID Reader]
             │
             │ (SPI Protocol: MOSI, MISO, SCK, SS)
             ▼
    [Arduino UNO Microcontroller] ──(GPIO)──> [LEDs / Buzzer / Relay]
             │
             │ (USB UART Serial @ 9600 Baud)
             ▼
     [Python Core Backend]
             │
      ┌──────┴────────────────────────────────┐
      ▼                                       ▼
[Local Authorized Database]       [Streamlit Web Frontend]
(Session Credentials & Logs)      (http://localhost:8501)</pre>
    </div>

    <!-- 5. Are you hosting? -->
    <h2 class="section-title">5. Are you hosting? If yes, where are you hosting?</h2>
    <div class="hosting-box">
        <div class="hosting-status">Hosting Status: No, hosted locally on Localhost (http://localhost:8501)</div>
        <div class="hosting-reason">
            <strong>Technical Justification:</strong> The application directly communicates with physical edge hardware (Arduino UNO and RC522 RFID reader) over local hardware USB Serial COM ports (e.g., <code>COM3</code>). Hosting locally ensures ultra-low-latency deterministic response times (&lt;50ms) required for instantaneous door unlocking solenoids and guarantees autonomous offline security functioning without internet or third-party cloud dependence.
        </div>
    </div>
</div>

<button class="action-print" onclick="window.print()">
    🖨️ Print / Save as PDF
</button>

</body>
</html>
"""

with open("Project_Report_23MID0080.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Generated Project_Report_23MID0080.html")
