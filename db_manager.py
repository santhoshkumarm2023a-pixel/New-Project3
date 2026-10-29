"""
db_manager.py - SQLite Database Management Layer for Campus Security System
Uses Python's built-in sqlite3 module with WAL (Write-Ahead Logging) mode
for concurrent multi-process access between Streamlit and Serial Bridge.
"""

import sqlite3
import os
import json
import time
from datetime import datetime

DB_FILE = "campus_security.db"
JSON_BACKUP = "access_data.json"

DEFAULT_CONFIG = {
    "active_door": "Campus Main Gate",
    "pending_registration_uid": None,
    "registration_mode": False,
    "zone_containment_enabled": True,
    "enforce_perimeter_gate": True,
    "face_verification_enabled": True,
    "geolocation_guard_enabled": True,
    "geofence_radius_meters": 200.0,
    "phone_gps_mode": "CO_LOCATED",
    "custom_phone_lat": 12.96918,
    "custom_phone_lon": 79.15593
}

# =============================================================================
# VIT Campus Geographic GPS Coordinates (WGS84 Real-World Google Maps)
# =============================================================================
CAMPUS_GPS = {
    "Campus Main Gate": {"lat": 12.96918, "lon": 79.15593, "name": "Campus Main Gate"},
    "MGR Block": {"lat": 12.97105, "lon": 79.15880, "name": "Dr. MGR Block"},
    "TT - Technology Tower": {"lat": 12.97185, "lon": 79.16010, "name": "Technology Tower (TT)"},
    "SJT - Silver Jubilee Tower": {"lat": 12.97340, "lon": 79.16380, "name": "Silver Jubilee Tower (SJT)"},
    "PRP Block": {"lat": 12.97520, "lon": 79.16620, "name": "Periyar Block (PRP)"}
}

# Smartphone Location Scenarios for Viva & Classroom Demonstrations
MOBILE_GPS_PRESETS = {
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
}

def calculate_geodesic_distance(lat1, lon1, lat2, lon2):
    """Calculates geodesic surface distance in meters using geopy with Haversine fallback."""
    try:
        from geopy.distance import geodesic
        return float(geodesic((lat1, lon1), (lat2, lon2)).meters)
    except Exception:
        import math
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return float(R * c)

def get_phone_gps_for_mode(mode, active_door="Campus Main Gate", custom_lat=None, custom_lon=None, tg_lat=None, tg_lon=None):
    """Returns (lat, lon, label) for a given student phone GPS mode."""
    door_gps = CAMPUS_GPS.get(active_door, CAMPUS_GPS["Campus Main Gate"])
    if mode == "CO_LOCATED":
        # Slight jitter (~15m) to simulate realistic smartphone GPS accuracy
        return (door_gps["lat"] + 0.00010, door_gps["lon"] + 0.00008, "Co-Located at Reader (< 20m)")
    elif mode == "TELEGRAM_LIVE":
        if tg_lat is not None and tg_lon is not None and float(tg_lat) != 0.0:
            return (float(tg_lat), float(tg_lon), f"Telegram Live Sensor ({float(tg_lat):.4f}°, {float(tg_lon):.4f}°)")
        return (door_gps["lat"] + 0.00010, door_gps["lon"] + 0.00008, "Co-Located (Telegram Active)")
    elif mode == "HOSTEL_MH":
        preset = MOBILE_GPS_PRESETS["HOSTEL_MH"]
        return (preset["lat"], preset["lon"], "Men's Hostel Block J (1,480m)")
    elif mode == "GAZEBO_FOODYS":
        preset = MOBILE_GPS_PRESETS["GAZEBO_FOODYS"]
        return (preset["lat"], preset["lon"], "Gazebo / Foodys Cafeteria (750m)")
    elif mode == "OUTSIDE_CAMPUS":
        preset = MOBILE_GPS_PRESETS["OUTSIDE_CAMPUS"]
        return (preset["lat"], preset["lon"], "Katpadi Junction Off-Campus (3.2 km)")
    return (door_gps["lat"] + 0.00010, door_gps["lon"] + 0.00008, "Co-Located")

def get_connection(db_path=DB_FILE):
    """Establishes a connection to the SQLite database with WAL mode and timeout."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_database(db_path=DB_FILE):
    """Initializes SQLite tables if they do not already exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Users Table (Enrolled Cardholders & Biometric Profiles)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                reg_no TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT DEFAULT 'Active',
                occupancy TEXT DEFAULT 'OUTSIDE',
                current_building TEXT DEFAULT 'None',
                last_location TEXT DEFAULT 'None',
                last_swipe_time TEXT,
                photo TEXT,
                phone_number TEXT DEFAULT 'N/A',
                telegram_chat_id TEXT DEFAULT 'None',
                phone_device_name TEXT DEFAULT 'Mobile Device',
                phone_gps_mode TEXT DEFAULT 'CO_LOCATED',
                phone_lat REAL DEFAULT 12.96918,
                phone_lon REAL DEFAULT 79.15593,
                phone_last_ping TEXT DEFAULT 'Never'
            );
        """)

        # Dynamically ensure newly added columns exist in older SQLite databases
        try:
            user_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users)").fetchall()]
            for c_name, c_type in [
                ("phone_number", "TEXT DEFAULT 'N/A'"),
                ("telegram_chat_id", "TEXT DEFAULT 'None'"),
                ("phone_device_name", "TEXT DEFAULT 'Mobile Device'"),
                ("phone_gps_mode", "TEXT DEFAULT 'CO_LOCATED'"),
                ("phone_lat", "REAL DEFAULT 12.96918"),
                ("phone_lon", "REAL DEFAULT 79.15593"),
                ("phone_last_ping", "TEXT DEFAULT 'Never'")
            ]:
                if c_name not in user_cols:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {c_name} {c_type};")
        except Exception:
            pass

        # 2. Access Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                timestamp TEXT,
                user_name TEXT NOT NULL,
                card_uid TEXT NOT NULL,
                reg_no TEXT,
                role TEXT,
                status TEXT NOT NULL,
                door TEXT NOT NULL,
                place TEXT NOT NULL,
                snapshot TEXT
            );
        """)
        try:
            cursor.execute("SELECT timestamp FROM access_logs LIMIT 1")
        except Exception:
            try:
                cursor.execute("ALTER TABLE access_logs ADD COLUMN timestamp TEXT;")
            except Exception:
                pass

        # 3. Security Violations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                timestamp TEXT,
                user_name TEXT NOT NULL,
                card_uid TEXT NOT NULL,
                reg_no TEXT,
                violation_type TEXT NOT NULL,
                details TEXT,
                severity TEXT DEFAULT 'HIGH',
                door TEXT NOT NULL,
                place TEXT NOT NULL,
                snapshot TEXT
            );
        """)
        try:
            cursor.execute("SELECT timestamp FROM security_violations LIMIT 1")
        except Exception:
            try:
                cursor.execute("ALTER TABLE security_violations ADD COLUMN timestamp TEXT;")
            except Exception:
                pass

        # 4. System Configuration & State
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        # 5. Telegram Detected Users & Inbound Chat Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (
                chat_id TEXT PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                last_seen TEXT
            );
        """)

        # Set default configurations if missing
        for k, v in DEFAULT_CONFIG.items():
            cursor.execute("SELECT key FROM system_config WHERE key = ?", (k,))
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO system_config (key, value) VALUES (?, ?)", (k, json.dumps(v)))

        conn.commit()

    # Migrate from access_data.json if database is newly initialized and JSON exists
    migrate_from_json_if_needed(db_path)

def migrate_from_json_if_needed(db_path=DB_FILE, json_path=JSON_BACKUP):
    """Migrates existing records from access_data.json into SQLite if database is empty, only once."""
    if not os.path.exists(json_path):
        return

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_config WHERE key = 'json_migration_completed'")
            flag_row = cursor.fetchone()
            if flag_row:
                try:
                    if json.loads(flag_row[0]) is True:
                        return
                except Exception:
                    pass

            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM access_logs")
            log_count = cursor.fetchone()[0]

            if user_count == 0 and log_count == 0:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Migrate Users
                for u in data.get("users", []):
                    cursor.execute("""
                        INSERT OR REPLACE INTO users 
                        (uid, name, reg_no, role, status, occupancy, current_building, last_location, last_swipe_time, photo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        u.get("UID", "").strip().upper(),
                        u.get("Name", "Unknown"),
                        u.get("RegNo", "N/A"),
                        u.get("Role", "Student"),
                        u.get("Status", "Active"),
                        u.get("Occupancy", "OUTSIDE"),
                        u.get("CurrentBuilding", "None"),
                        u.get("LastLocation", "None"),
                        u.get("LastSwipeTime"),
                        u.get("Photo")
                    ))

                # Migrate Logs
                for l in data.get("logs", []):
                    cursor.execute("""
                        INSERT INTO access_logs 
                        (time, user_name, card_uid, reg_no, role, status, door, place, snapshot)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        l.get("Time", ""),
                        l.get("User", ""),
                        l.get("Card UID", ""),
                        l.get("RegNo", ""),
                        l.get("Role", ""),
                        l.get("Status", ""),
                        l.get("Door", ""),
                        l.get("Place", ""),
                        l.get("Snapshot", "")
                    ))

                # Migrate Violations
                for v in data.get("violations", []):
                    cursor.execute("""
                        INSERT INTO security_violations 
                        (time, user_name, card_uid, reg_no, violation_type, details, severity, door, place, snapshot)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        v.get("Time", ""),
                        v.get("User", ""),
                        v.get("Card UID", ""),
                        v.get("RegNo", ""),
                        v.get("ViolationType", ""),
                        v.get("Details", ""),
                        v.get("Severity", "HIGH"),
                        v.get("Door", ""),
                        v.get("Place", ""),
                        v.get("Snapshot", "")
                    ))

                # Migrate Config
                sec_cfg = data.get("security_config", {})
                for k, v in sec_cfg.items():
                    cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (k, json.dumps(v)))

                if "active_door" in data:
                    cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("active_door", json.dumps(data["active_door"])))
                if "pending_registration_uid" in data:
                    cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("pending_registration_uid", json.dumps(data["pending_registration_uid"])))
                if "registration_mode" in data:
                    cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("registration_mode", json.dumps(data["registration_mode"])))

            # Mark migration permanently completed
            cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('json_migration_completed', ?)", (json.dumps(True),))
            conn.commit()
    except Exception as e:
        print(f"[DB MIGRATION WARN] Could not migrate from JSON: {e}")

# =============================================================================
# High-Level Query & Mutation APIs
# =============================================================================

def get_all_users(db_path=DB_FILE):
    """Returns a list of all enrolled users as dictionaries."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY name ASC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            keys = r.keys()
            result.append({
                "Name": r["name"],
                "RegNo": r["reg_no"],
                "UID": r["uid"],
                "Role": r["role"],
                "Status": r["status"],
                "Occupancy": r["occupancy"],
                "CurrentBuilding": r["current_building"],
                "LastLocation": r["last_location"],
                "LastSwipeTime": r["last_swipe_time"],
                "Photo": r["photo"],
                "PhoneNumber": r["phone_number"] if "phone_number" in keys else "N/A",
                "TelegramChatId": r["telegram_chat_id"] if "telegram_chat_id" in keys else "None",
                "PhoneDeviceName": r["phone_device_name"] if "phone_device_name" in keys else "Mobile Device",
                "PhoneGpsMode": r["phone_gps_mode"] if "phone_gps_mode" in keys else "CO_LOCATED",
                "PhoneLat": float(r["phone_lat"]) if ("phone_lat" in keys and r["phone_lat"] is not None) else 12.96918,
                "PhoneLon": float(r["phone_lon"]) if ("phone_lon" in keys and r["phone_lon"] is not None) else 79.15593,
                "PhoneLastPing": r["phone_last_ping"] if "phone_last_ping" in keys else "Never"
            })
        return result

def get_user_by_uid(uid_clean, db_path=DB_FILE):
    """Finds a user by clean or compacted UID."""
    compact_target = uid_clean.replace(" ", "").upper()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        for r in cursor.fetchall():
            if r["uid"].replace(" ", "").upper() == compact_target:
                keys = r.keys()
                return {
                    "Name": r["name"],
                    "RegNo": r["reg_no"],
                    "UID": r["uid"],
                    "Role": r["role"],
                    "Status": r["status"],
                    "Occupancy": r["occupancy"],
                    "CurrentBuilding": r["current_building"],
                    "LastLocation": r["last_location"],
                    "LastSwipeTime": r["last_swipe_time"],
                    "Photo": r["photo"],
                    "PhoneNumber": r["phone_number"] if "phone_number" in keys else "N/A",
                    "TelegramChatId": r["telegram_chat_id"] if "telegram_chat_id" in keys else "None",
                    "PhoneDeviceName": r["phone_device_name"] if "phone_device_name" in keys else "Mobile Device",
                    "PhoneGpsMode": r["phone_gps_mode"] if "phone_gps_mode" in keys else "CO_LOCATED",
                    "PhoneLat": float(r["phone_lat"]) if ("phone_lat" in keys and r["phone_lat"] is not None) else 12.96918,
                    "PhoneLon": float(r["phone_lon"]) if ("phone_lon" in keys and r["phone_lon"] is not None) else 79.15593,
                    "PhoneLastPing": r["phone_last_ping"] if "phone_last_ping" in keys else "Never"
                }
        return None

def upsert_user(user_dict, db_path=DB_FILE):
    """Inserts or updates a user record."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users 
            (uid, name, reg_no, role, status, occupancy, current_building, last_location, last_swipe_time, photo,
             phone_number, telegram_chat_id, phone_device_name, phone_gps_mode, phone_lat, phone_lon, phone_last_ping)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_dict["UID"].strip().upper(),
            user_dict.get("Name", "Unknown"),
            user_dict.get("RegNo", "N/A"),
            user_dict.get("Role", "Student"),
            user_dict.get("Status", "Active"),
            user_dict.get("Occupancy", "OUTSIDE"),
            user_dict.get("CurrentBuilding", "None"),
            user_dict.get("LastLocation", "None"),
            user_dict.get("LastSwipeTime"),
            user_dict.get("Photo"),
            user_dict.get("PhoneNumber", "N/A"),
            user_dict.get("TelegramChatId", "None"),
            user_dict.get("PhoneDeviceName", "Mobile Device"),
            user_dict.get("PhoneGpsMode", "CO_LOCATED"),
            float(user_dict.get("PhoneLat", 12.96918)),
            float(user_dict.get("PhoneLon", 79.15593)),
            user_dict.get("PhoneLastPing", "Never")
        ))
        conn.commit()

def bind_telegram_chat_to_user(chat_id, query_str, device_name="Telegram Mobile", db_path=DB_FILE):
    """Binds a telegram chat_id to a user matching phone_number, reg_no, name, or uid."""
    q_str = str(query_str or "").strip()
    q_clean = q_str.upper()
    q_digits = "".join(filter(str.isdigit, q_str))

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        for r in cursor.fetchall():
            keys = r.keys()
            u_phone = str(r["phone_number"] or "").strip() if "phone_number" in keys else ""
            u_phone_digits = "".join(filter(str.isdigit, u_phone))
            u_reg = (r["reg_no"] or "").strip().upper()
            u_name = (r["name"] or "").strip().upper()
            u_uid = (r["uid"] or "").replace(" ", "").upper()

            # Match phone number (e.g. last 10 digits match)
            phone_matched = False
            if len(q_digits) >= 10 and len(u_phone_digits) >= 10:
                if q_digits[-10:] == u_phone_digits[-10:]:
                    phone_matched = True
            elif q_digits and q_digits == u_phone_digits:
                phone_matched = True

            if phone_matched or q_clean == u_reg or q_clean in u_name or q_clean == u_uid:
                cursor.execute("""
                    UPDATE users 
                    SET telegram_chat_id = ?, phone_device_name = ?, phone_gps_mode = 'TELEGRAM_LIVE'
                    WHERE uid = ?
                """, (str(chat_id), device_name, r["uid"]))
                conn.commit()
                return dict(r)
    return None

def update_user_gps_from_telegram(chat_id, lat, lon, db_path=DB_FILE):
    """Updates GPS coordinates for user associated with telegram chat_id."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),))
        row = cursor.fetchone()
        if row:
            now_iso = datetime.now().isoformat()
            cursor.execute("""
                UPDATE users
                SET phone_lat = ?, phone_lon = ?, phone_last_ping = ?, phone_gps_mode = 'TELEGRAM_LIVE'
                WHERE uid = ?
            """, (float(lat), float(lon), now_iso, row["uid"]))
            conn.commit()
            return dict(row)
    return None

def get_user_by_chat_id(chat_id, db_path=DB_FILE):
    """Finds user by telegram chat_id."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),))
        row = cursor.fetchone()
        return dict(row) if row else None

def record_telegram_user(chat_id, first_name, username, db_path=DB_FILE):
    """Records any incoming telegram user who opens or messages the bot."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        now_iso = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO telegram_users (chat_id, first_name, username, last_seen)
            VALUES (?, ?, ?, ?)
        """, (str(chat_id), first_name or "Unknown", username or "None", now_iso))
        conn.commit()

def get_recent_telegram_users(db_path=DB_FILE):
    """Returns list of recent Telegram users who interacted with the bot."""
    init_database(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telegram_users ORDER BY last_seen DESC LIMIT 20")
        return [dict(r) for r in cursor.fetchall()]

def get_phone_gps_for_user(user_dict, active_door="Campus Main Gate"):
    """
    Returns (lat, lon, label, mode) for a specific user cardholder.
    Prioritizes the student's personal Telegram / live GPS coordinates if available.
    """
    door_gps = CAMPUS_GPS.get(active_door, CAMPUS_GPS["Campus Main Gate"])
    mode = user_dict.get("PhoneGpsMode", "CO_LOCATED")
    tg_id = user_dict.get("TelegramChatId", "None")
    dev_name = user_dict.get("PhoneDeviceName", "Mobile Device")
    p_lat = user_dict.get("PhoneLat")
    p_lon = user_dict.get("PhoneLon")
    p_ping = user_dict.get("PhoneLastPing", "Never")

    if tg_id != "None" and p_lat is not None and p_lon is not None and float(p_lat) != 0.0:
        return (float(p_lat), float(p_lon), f"{dev_name} (Telegram 4G/5G Live)", "TELEGRAM_LIVE")

    if mode in MOBILE_GPS_PRESETS:
        p_info = MOBILE_GPS_PRESETS[mode]
        if mode == "CO_LOCATED":
            return (door_gps["lat"] + 0.00010, door_gps["lon"] + 0.00008, f"{dev_name} (Co-Located < 20m)", mode)
        return (p_info["lat"], p_info["lon"], f"{dev_name} ({p_info['label']})", mode)

    return (door_gps["lat"], door_gps["lon"], f"{dev_name} (Co-Located)", "CO_LOCATED")

def update_user_occupancy(uid, occupancy, building, location, swipe_time, db_path=DB_FILE):
    """Updates user occupancy location and timestamp."""
    compact_target = uid.replace(" ", "").upper()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Find exact UID representation in db
        cursor.execute("SELECT uid FROM users")
        exact_uid = None
        for r in cursor.fetchall():
            if r["uid"].replace(" ", "").upper() == compact_target:
                exact_uid = r["uid"]
                break
        if exact_uid:
            cursor.execute("""
                UPDATE users 
                SET occupancy = ?, current_building = ?, last_location = ?, last_swipe_time = ?
                WHERE uid = ?
            """, (occupancy, building, location, swipe_time, exact_uid))
            conn.commit()

def add_access_log(log_dict, db_path=DB_FILE):
    """Inserts a new event into access_logs."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        now_ts = log_dict.get("Timestamp") or datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO access_logs 
            (time, timestamp, user_name, card_uid, reg_no, role, status, door, place, snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_dict.get("Time", ""),
            now_ts,
            log_dict.get("User", ""),
            log_dict.get("Card UID", ""),
            log_dict.get("RegNo", ""),
            log_dict.get("Role", ""),
            log_dict.get("Status", ""),
            log_dict.get("Door", ""),
            log_dict.get("Place", ""),
            log_dict.get("Snapshot", "")
        ))
        conn.commit()

def get_access_logs(limit=100, db_path=DB_FILE):
    """Retrieves access logs sorted newest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM access_logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            keys = r.keys()
            result.append({
                "id": r["id"],
                "Time": r["time"],
                "Timestamp": r["timestamp"] if ("timestamp" in keys and r["timestamp"]) else f"2026-10-24T{r['time']}",
                "User": r["user_name"],
                "Card UID": r["card_uid"],
                "RegNo": r["reg_no"],
                "Role": r["role"],
                "Status": r["status"],
                "Door": r["door"],
                "Place": r["place"],
                "Snapshot": r["snapshot"]
            })
        return result

def add_security_violation(viol_dict, db_path=DB_FILE):
    """Inserts a new event into security_violations."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        now_ts = viol_dict.get("Timestamp") or datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO security_violations 
            (time, timestamp, user_name, card_uid, reg_no, violation_type, details, severity, door, place, snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            viol_dict.get("Time", ""),
            now_ts,
            viol_dict.get("User", ""),
            viol_dict.get("Card UID", ""),
            viol_dict.get("RegNo", ""),
            viol_dict.get("ViolationType", ""),
            viol_dict.get("Details", ""),
            viol_dict.get("Severity", "HIGH"),
            viol_dict.get("Door", ""),
            viol_dict.get("Place", ""),
            viol_dict.get("Snapshot", "")
        ))
        conn.commit()

def get_security_violations(limit=100, db_path=DB_FILE):
    """Retrieves security violations sorted newest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM security_violations ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            keys = r.keys()
            result.append({
                "id": r["id"],
                "Time": r["time"],
                "Timestamp": r["timestamp"] if ("timestamp" in keys and r["timestamp"]) else f"2026-10-24T{r['time']}",
                "User": r["user_name"],
                "Card UID": r["card_uid"],
                "RegNo": r["reg_no"],
                "ViolationType": r["violation_type"],
                "Details": r["details"],
                "Severity": r["severity"],
                "Door": r["door"],
                "Place": r["place"],
                "Snapshot": r["snapshot"]
            })
        return result

def get_config_val(key, default=None, db_path=DB_FILE):
    """Gets a configuration setting from SQLite."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is not None:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return default

def set_config_val(key, val, db_path=DB_FILE):
    """Stores a configuration setting in SQLite."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, json.dumps(val)))
        conn.commit()

def get_hardware_status(db_path=DB_FILE):
    """Returns real-time hardware connection status dictionary."""
    status = get_config_val("hardware_bridge_status", None, db_path)
    if not status or not isinstance(status, dict):
        return {
            "connected": False,
            "port": None,
            "status": "DISCONNECTED",
            "reader": "NO HARDWARE",
            "last_heartbeat": 0
        }
    last_hb = float(status.get("last_heartbeat", 0))
    # If heartbeat is older than 6 seconds, the bridge process is offline / stopped
    if time.time() - last_hb > 6.0:
        return {
            "connected": False,
            "port": status.get("port"),
            "status": "OFFLINE",
            "reader": "BRIDGE STOPPED",
            "last_heartbeat": last_hb
        }
    return status

def set_hardware_status(connected, port, status_str, reader_str, db_path=DB_FILE):
    """Updates hardware bridge heartbeat and connection status."""
    payload = {
        "connected": bool(connected),
        "port": port,
        "status": status_str,
        "reader": reader_str,
        "last_heartbeat": time.time()
    }
    set_config_val("hardware_bridge_status", payload, db_path)

def clear_logs_and_violations(db_path=DB_FILE):
    """Deletes all logs and violations while preserving users and configuration."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM access_logs")
        cursor.execute("DELETE FROM security_violations")
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('json_migration_completed', ?)", (json.dumps(True),))
        conn.commit()
    # Synchronize wipe to JSON backup file
    try:
        if os.path.exists(JSON_BACKUP):
            with open(JSON_BACKUP, "r", encoding="utf-8") as f:
                j_data = json.load(f)
            j_data["logs"] = []
            j_data["violations"] = []
            with open(JSON_BACKUP, "w", encoding="utf-8") as f:
                json.dump(j_data, f, indent=2)
    except Exception:
        pass

def delete_all_users(db_path=DB_FILE):
    """Deletes all registered users while preserving logs and configuration."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users")
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('json_migration_completed', ?)", (json.dumps(True),))
        conn.commit()
    set_config_val("pending_registration_uid", None, db_path)
    set_config_val("registration_mode", False, db_path)
    # Synchronize wipe to JSON backup file
    try:
        if os.path.exists(JSON_BACKUP):
            with open(JSON_BACKUP, "r", encoding="utf-8") as f:
                j_data = json.load(f)
            j_data["users"] = []
            j_data["pending_registration_uid"] = None
            j_data["registration_mode"] = False
            with open(JSON_BACKUP, "w", encoding="utf-8") as f:
                json.dump(j_data, f, indent=2)
    except Exception:
        pass

def reset_all_occupancy(db_path=DB_FILE):
    """Resets occupancy of all users to OUTSIDE without modifying user profiles."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET occupancy = 'OUTSIDE', current_building = 'None', last_location = 'None', last_swipe_time = NULL
        """)
        conn.commit()
    set_config_val("active_door", "Campus Main Gate", db_path)

# =============================================================================
# Full-Dictionary Adapter Layer (100% Drop-In Replacement for load_data / save_data)
# =============================================================================

def load_data(db_path=DB_FILE):
    """
    Returns the complete system state as a Python dictionary.
    Drop-in replacement for the former json-based load_data().
    """
    init_database(db_path)

    sec_cfg = {
        "zone_containment_enabled": get_config_val("zone_containment_enabled", True, db_path),
        "enforce_perimeter_gate": get_config_val("enforce_perimeter_gate", True, db_path),
        "face_verification_enabled": get_config_val("face_verification_enabled", True, db_path),
        "geolocation_guard_enabled": get_config_val("geolocation_guard_enabled", True, db_path),
        "geofence_radius_meters": float(get_config_val("geofence_radius_meters", 200.0, db_path)),
        "phone_gps_mode": get_config_val("phone_gps_mode", "CO_LOCATED", db_path),
        "custom_phone_lat": float(get_config_val("custom_phone_lat", 12.96918, db_path)),
        "custom_phone_lon": float(get_config_val("custom_phone_lon", 79.15593, db_path))
    }

    return {
        "users": get_all_users(db_path),
        "logs": get_access_logs(limit=100, db_path=db_path),
        "violations": get_security_violations(limit=100, db_path=db_path),
        "active_door": get_config_val("active_door", "Campus Main Gate", db_path),
        "pending_registration_uid": get_config_val("pending_registration_uid", None, db_path),
        "registration_mode": get_config_val("registration_mode", False, db_path),
        "security_config": sec_cfg
    }

def save_data(data, db_path=DB_FILE):
    """
    Persists modified state dictionary into SQLite.
    Drop-in replacement for the former json-based save_data().
    """
    init_database(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Update users
        if "users" in data:
            cursor.execute("DELETE FROM users")
            for u in data["users"]:
                cursor.execute("""
                    INSERT OR REPLACE INTO users 
                    (uid, name, reg_no, role, status, occupancy, current_building, last_location, last_swipe_time, photo,
                     phone_number, telegram_chat_id, phone_device_name, phone_gps_mode, phone_lat, phone_lon, phone_last_ping)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    u.get("UID", "").strip().upper(),
                    u.get("Name", "Unknown"),
                    u.get("RegNo", "N/A"),
                    u.get("Role", "Student"),
                    u.get("Status", "Active"),
                    u.get("Occupancy", "OUTSIDE"),
                    u.get("CurrentBuilding", "None"),
                    u.get("LastLocation", "None"),
                    u.get("LastSwipeTime"),
                    u.get("Photo"),
                    u.get("PhoneNumber", "N/A"),
                    u.get("TelegramChatId", "None"),
                    u.get("PhoneDeviceName", "Mobile Device"),
                    u.get("PhoneGpsMode", "CO_LOCATED"),
                    float(u.get("PhoneLat", 12.96918)),
                    float(u.get("PhoneLon", 79.15593)),
                    u.get("PhoneLastPing", "Never")
                ))

        # Update logs
        logs_to_sync = []
        if "logs" in data:
            cursor.execute("DELETE FROM access_logs")
            logs_to_sync = data["logs"][:150]
            # data["logs"] is maintained newest-first (index 0 is the newest swipe event).
            # Inserting in reversed order ensures the newest swipe (index 0) is inserted LAST,
            # which guarantees it receives the highest auto-increment ID.
            for l in reversed(logs_to_sync):
                now_ts = l.get("Timestamp") or f"2026-10-24T{l.get('Time', '00:00:00')}"
                cursor.execute("""
                    INSERT INTO access_logs 
                    (time, timestamp, user_name, card_uid, reg_no, role, status, door, place, snapshot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    l.get("Time", ""),
                    now_ts,
                    l.get("User", ""),
                    l.get("Card UID", ""),
                    l.get("RegNo", ""),
                    l.get("Role", ""),
                    l.get("Status", ""),
                    l.get("Door", ""),
                    l.get("Place", ""),
                    l.get("Snapshot", "")
                ))

        # Update violations
        violations_to_sync = []
        if "violations" in data:
            cursor.execute("DELETE FROM security_violations")
            violations_to_sync = data["violations"][:150]
            # data["violations"] is maintained newest-first (index 0 is the newest violation event).
            # Inserting in reversed order ensures the newest violation is inserted LAST,
            # which guarantees it receives the highest auto-increment ID.
            for v in reversed(violations_to_sync):
                now_ts = v.get("Timestamp") or f"2026-10-24T{v.get('Time', '00:00:00')}"
                cursor.execute("""
                    INSERT INTO security_violations 
                    (time, timestamp, user_name, card_uid, reg_no, violation_type, details, severity, door, place, snapshot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    v.get("Time", ""),
                    now_ts,
                    v.get("User", ""),
                    v.get("Card UID", ""),
                    v.get("RegNo", ""),
                    v.get("ViolationType", ""),
                    v.get("Details", ""),
                    v.get("Severity", "HIGH"),
                    v.get("Door", ""),
                    v.get("Place", ""),
                    v.get("Snapshot", "")
                ))

        # Update configurations
        if "active_door" in data:
            cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("active_door", json.dumps(data["active_door"])))
        if "pending_registration_uid" in data:
            cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("pending_registration_uid", json.dumps(data["pending_registration_uid"])))
        if "registration_mode" in data:
            cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", ("registration_mode", json.dumps(data["registration_mode"])))
        if "security_config" in data:
            for k, v in data["security_config"].items():
                cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (k, json.dumps(v)))

        conn.commit()

    # Also keep access_data.json updated as a synchronized mirror/backup with newest first
    try:
        backup_data = dict(data)
        if logs_to_sync:
            backup_data["logs"] = logs_to_sync
        if violations_to_sync:
            backup_data["violations"] = violations_to_sync
        with open(JSON_BACKUP, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)
    except Exception:
        pass

# Initialize database on module load
init_database()
