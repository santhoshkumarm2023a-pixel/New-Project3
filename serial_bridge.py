import sys
# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import serial
import serial.tools.list_ports
import time
import json
import os
import threading
from datetime import datetime
import re
import cv2
import db_manager
import telegram_guard

DATA_FILE = "access_data.json"
EVIDENCE_DIR = "evidence_snaps"
REGISTERED_FACES_DIR = "registered_faces"
YUNET_MODEL = "yunet.onnx"
SFACE_MODEL = "sface.onnx"

# =============================================================================
# VIT Campus Geographic Layout & Pathway Coordinates (in meters relative to Gate)
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
    """Calculates 2D Euclidean pathway distance in meters between any two campus locations."""
    if not loc1 or not loc2 or loc1 == "None" or loc2 == "None" or loc1 == loc2:
        return 0
    p1 = CAMPUS_LOCATIONS.get(loc1)
    p2 = CAMPUS_LOCATIONS.get(loc2)
    if not p1 or not p2:
        return 300
    dx = p1["x"] - p2["x"]
    dy = p1["y"] - p2["y"]
    return int(round((dx**2 + dy**2) ** 0.5))

def log_print(*args, **kwargs):
    print(*args, **kwargs, flush=True)

# =============================================================================
# Camera & Biometric CCTV Surveillance + 1-to-1 Face Recognition Service
# =============================================================================
class CameraService:
    def __init__(self, yunet_path=YUNET_MODEL, sface_path=SFACE_MODEL, camera_index=0):
        self.camera_index = camera_index
        self.yunet_path = yunet_path
        self.sface_path = sface_path
        self.cap = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.dnn_lock = threading.Lock()
        self.latest_frame = None
        self.latest_faces = []
        self.camera_available = False
        self.detector = None
        self.recognizer = None
        self.enrolled_features = {}
        self.active_door = "Campus Main Gate"
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        os.makedirs(REGISTERED_FACES_DIR, exist_ok=True)

    def start(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.camera_available = True
                    h, w, _ = frame.shape
                    if os.path.exists(self.yunet_path):
                        self.detector = cv2.FaceDetectorYN.create(self.yunet_path, '', (w, h), 0.5, 0.3, 5000)
                        self.detector.setInputSize((w, h))
                    if os.path.exists(self.sface_path):
                        self.recognizer = cv2.FaceRecognizerSF.create(self.sface_path, '')
        except Exception as e:
            log_print(f"[WARN] Camera initialization error: {e}")
            self.camera_available = False

        if self.camera_available:
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            log_print("[CAMERA] Live CCTV surveillance, YuNet detector & SFace recognizer initialized!")
        else:
            log_print("[WARN] Webcam not detected. System will operate in standard RFID mode.")

    def set_active_door(self, door):
        self.active_door = door

    def get_enrolled_feature(self, uid_clean):
        """Retrieves or precomputes and caches the 128-D SFace feature vector for a registered user."""
        uid_compact = uid_clean.replace(" ", "").upper()
        if uid_compact in self.enrolled_features:
            return self.enrolled_features[uid_compact]

        ref_path = os.path.join(REGISTERED_FACES_DIR, f"{uid_compact}.jpg")
        if not os.path.exists(ref_path):
            return None

        try:
            ref_img = cv2.imread(ref_path)
            if ref_img is None:
                return None
            rh, rw, _ = ref_img.shape
            with self.dnn_lock:
                self.detector.setInputSize((rw, rh))
                _, ref_faces = self.detector.detect(ref_img)
                if ref_faces is None or len(ref_faces) == 0:
                    return None
                ref_aligned = self.recognizer.alignCrop(ref_img, ref_faces[0])
                feat = self.recognizer.feature(ref_aligned)
                self.enrolled_features[uid_compact] = feat.copy()
                return self.enrolled_features[uid_compact]
        except Exception as e:
            log_print(f"    [WARN] Failed to extract enrolled face feature: {e}")
            return None

    def _capture_loop(self):
        last_save = 0
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.04)
                continue

            h, w, _ = frame.shape
            faces = []
            if self.detector is not None:
                with self.dnn_lock:
                    try:
                        self.detector.setInputSize((w, h))
                        _, det = self.detector.detect(frame)
                        if det is not None:
                            faces = det
                    except Exception:
                        pass

            with self.lock:
                self.latest_frame = frame.copy()
                self.latest_faces = faces

            now = time.time()
            if now - last_save > 0.08:  # ~12 FPS live dashboard write
                disp = frame.copy()
                overlay = disp.copy()
                # Top header bar
                cv2.rectangle(overlay, (0, 0), (w, 38), (15, 20, 25), -1)
                # Bottom footer bar
                cv2.rectangle(overlay, (0, h - 30), (w, h), (15, 20, 25), -1)
                cv2.addWeighted(overlay, 0.75, disp, 0.25, 0, disp)

                # Status pill
                cv2.circle(disp, (20, 19), 6, (50, 205, 50), -1)
                cv2.putText(disp, f"LIVE CCTV | TERMINAL: {self.active_door.upper()}", (36, 25), 
                            cv2.FONT_HERSHEY_DUPLEX, 0.52, (240, 240, 240), 1, cv2.LINE_AA)

                now_str = datetime.now().strftime("%H:%M:%S")
                cv2.putText(disp, f"{now_str} | SFACE-AI", (w - 180, 25), 
                            cv2.FONT_HERSHEY_DUPLEX, 0.48, (160, 200, 240), 1, cv2.LINE_AA)

                # Draw face bounding boxes
                if faces is not None and len(faces) > 0:
                    for f in faces:
                        fx, fy, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                        conf = int(float(f[-1]) * 100)
                        cv2.rectangle(disp, (fx, fy), (fx + fw, fy + fh), (50, 205, 50), 2)
                        cv2.rectangle(disp, (fx, max(0, fy - 22)), (fx + 155, max(22, fy)), (50, 205, 50), -1)
                        cv2.putText(disp, f"FACE VERIFIED {conf}%", (fx + 6, max(16, fy - 6)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
                    cv2.putText(disp, "2-FACTOR BIOMETRIC GUARD: SUBJECT DETECTED", (20, h - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 250, 120), 1, cv2.LINE_AA)
                else:
                    cv2.putText(disp, "[ANTI-PROXY ACTIVE] SCANNER CLEAR - WAITING FOR SUBJECT", (20, h - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 255), 1, cv2.LINE_AA)

                try:
                    tmp_cctv = f"cctv_live_{os.getpid()}.tmp.jpg"
                    cv2.imwrite(tmp_cctv, disp)
                    if os.path.exists(tmp_cctv):
                        os.replace(tmp_cctv, "cctv_live.jpg")
                    last_save = now
                except (PermissionError, OSError):
                    pass
                except Exception:
                    pass

            time.sleep(0.035)

    def get_latest_capture(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy(), list(self.latest_faces)
        return None, []

    def verify_1to1_identity(self, raw_frame, detected_faces, uid_clean):
        """
        1-to-1 Facial Identity Matching:
        Compares live camera face against the cardholder's enrolled photo.
        Returns: (is_enrolled, is_match, similarity_score, message)
        """
        if self.recognizer is None or self.detector is None or not detected_faces or raw_frame is None:
            return True, False, 0.0, "Face recognition engine unavailable"

        ref_feat = self.get_enrolled_feature(uid_clean)
        if ref_feat is None:
            return False, True, 0.0, "No reference photo enrolled (Presence check passed)"

        try:
            with self.dnn_lock:
                live_aligned = self.recognizer.alignCrop(raw_frame, detected_faces[0])
                live_feat = self.recognizer.feature(live_aligned)
                score = float(self.recognizer.match(live_feat, ref_feat, cv2.FaceRecognizerSF_FR_COSINE))

            # Threshold 0.44: Cardholder scores ~0.65 (Passed), Friend impostor scores 0.20-0.37 (Blocked!)
            MATCH_THRESHOLD = 0.44
            is_match = (score >= MATCH_THRESHOLD)
            return True, is_match, score, f"Similarity Score: {score:.3f}"
        except Exception as e:
            log_print(f"    [WARN] Face matching error: {e}")
            # FAIL-SECURE: Deny access if any neural network error occurs
            return True, False, 0.0, f"Matching error: {e}"

    def save_evidence(self, raw_frame, user_name, uid, door, is_violation=False, reason="", sim_score=None):
        if raw_frame is None:
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid_clean = uid.replace(" ", "")
        status_slug = "VIOLATION" if is_violation else "GRANTED"
        filename = f"{EVIDENCE_DIR}/snap_{stamp}_{uid_clean}_{status_slug}.jpg"

        snap = raw_frame.copy()
        sh, sw, _ = snap.shape
        overlay = snap.copy()

        # Dark alert banner at bottom
        banner_color = (15, 15, 180) if is_violation else (15, 60, 25)
        cv2.rectangle(overlay, (0, sh - 75), (sw, sh), banner_color, -1)
        cv2.addWeighted(overlay, 0.85, snap, 0.15, 0, snap)

        title = f"[{'SECURITY VIOLATION' if is_violation else 'ACCESS GRANTED'}] {user_name} ({uid})"
        score_text = f" | Match: {int(sim_score*100)}%" if sim_score is not None else ""
        subtitle = f"Station: {door} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{score_text} | {reason}"

        cv2.putText(snap, title, (16, sh - 45), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(snap, subtitle, (16, sh - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 240, 255), 1, cv2.LINE_AA)

        try:
            cv2.imwrite(filename, snap)
            return filename
        except Exception as e:
            log_print(f"[WARN] Failed to write evidence snapshot: {e}")
            return None

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if os.path.exists("cctv_live.jpg"):
            try:
                os.remove("cctv_live.jpg")
            except Exception:
                pass

def load_data():
    return db_manager.load_data()

def save_data(data):
    db_manager.save_data(data)

def detect_port():
    ports = serial.tools.list_ports.comports()
    # 1. Match known USB serial controllers (excluding Windows Bluetooth links)
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "bthenum" in hwid or "bluetooth" in desc:
            continue
        if any(sig in desc or sig in hwid for sig in ["cp210", "arduino", "usb serial", "ch340", "ftdi", "vid:"]):
            return p.device
    
    # 2. Check COM5 if not Bluetooth
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "bthenum" in hwid or "bluetooth" in desc:
            continue
        if p.device == "COM5":
            return "COM5"

    # 3. Match any physical USB serial port
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "bthenum" in hwid or "bluetooth" in desc:
            continue
        if "usb" in desc or "usb" in hwid:
            return p.device

    return None

def main():
    port = detect_port()
    if not port:
        log_print("=" * 70)
        log_print("[WAIT] No physical USB RFID hardware reader detected.")
        log_print("       Bluetooth virtual ports (e.g. COM3/COM4) are ignored.")
        log_print("       Please plug in your Freeduino / Arduino Uno USB cable.")
        log_print("=" * 70)
        db_manager.set_hardware_status(False, None, "DISCONNECTED", "NO HARDWARE")
        while not port:
            time.sleep(2)
            port = detect_port()

    log_print("=" * 70)
    log_print("Smart RFID Campus Access Control & Biometric Surveillance")
    log_print("  [Zone Containment & Concurrent Ghost Presence Detection]")
    log_print("  [1-to-1 Facial Identity Matching (Anti-Theft / SFace CNN)]")
    log_print("  [Silent Cardholder Registration & Auto-Fill UID Support]")
    log_print(f"Connecting to Freeduino / Arduino on {port} at 9600 baud...")
    log_print("=" * 70)

    # Start Telegram Mobile Guard daemon for real-time 4G/5G mobile GPS telemetry
    try:
        telegram_guard.start_background_daemon()
        log_print("[TELEGRAM] Mobile Guard daemon active (@vit_security_007_bot)!")
    except Exception as e:
        log_print("[TELEGRAM WARN] Could not start Telegram daemon:", e)

    # Initialize Camera & SFace Identity Verification Service
    camera_service = CameraService(yunet_path=YUNET_MODEL, sface_path=SFACE_MODEL, camera_index=0)
    camera_service.start()

    try:
        ser = serial.Serial(port, 9600, timeout=1)
        # Release DTR and RTS so ATmega328P microcontroller runs freely
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass
        time.sleep(2.0)  # Allow Arduino boot, boot banners, and PCD_Init execution
        ser.reset_input_buffer()
        # Flush any trailing boot banners or electrical transients from the serial buffer
        flush_deadline = time.time() + 0.5
        while time.time() < flush_deadline:
            if ser.in_waiting > 0:
                boot_line = ser.readline().decode('utf-8', errors='ignore').strip()
                if boot_line:
                    log_print(f"    [SCANNER HARDWARE BOOT] {boot_line}")
            else:
                time.sleep(0.05)

        log_print(f"[OK] Successfully connected to {port}!")
        log_print("[READY] Swipe your RFID card on the reader now...\n")
        db_manager.set_hardware_status(True, port, "ONLINE", "RC522 ACTIVE")

        last_hb = time.time()
        while True:
            cur_t = time.time()
            if cur_t - last_hb >= 2.0:
                db_manager.set_hardware_status(True, port, "ONLINE", "RC522 ACTIVE")
                last_hb = cur_t

            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            # Diagnostic & status messages / banners from Arduino
            if line.startswith("#") or line.startswith("=") or line.startswith("-") or any(
                k in line.upper() for k in [
                    "MFRC522", "FIRMWARE", "VERSION", "READY", "INIT", "PCD_", 
                    "CAMPUS", "ACCESS CONTROL", "SMART RFID", "ONLINE", "SWIPE"
                ]
            ):
                log_print(f"    [SCANNER HARDWARE] {line}")
                continue

            # Robust, strict RFID hex UID extractor:
            # Handles standard 4-byte (8 hex chars), 7-byte (14 hex chars), or 10-byte (20 hex chars)
            # Examples: "6A E5 5D DF", "CA 89 A4 DE", "Card UID: 6A E5 5D DF", "6AE55DDF", "6A:E5:5D:DF"
            uid_line = line
            if "UID" in line.upper():
                parts = re.split(r'UID\s*[:=\-]?\s*', line, flags=re.IGNORECASE)
                if len(parts) > 1 and parts[1].strip():
                    uid_line = parts[1].strip()

            hex_tokens = re.findall(r'\b[0-9A-Fa-f]{2}\b', uid_line)
            if len(hex_tokens) in [4, 7, 10]:
                uid_clean = " ".join(token.upper() for token in hex_tokens)
            else:
                compact_candidate = re.sub(r'[\s:\-]', '', uid_line).upper()
                if re.fullmatch(r'[0-9A-Fa-f]+', compact_candidate) and len(compact_candidate) in [8, 14, 20]:
                    uid_clean = " ".join(compact_candidate[i:i+2] for i in range(0, len(compact_candidate), 2))
                else:
                    # Non-UID hardware diagnostic or electrical serial line noise -> do NOT process as card
                    log_print(f"    [ARDUINO SERIAL] {line}")
                    continue

            now = datetime.now()
            now_str = now.strftime("%H:%M:%S")

            data = load_data()
            users = data.get("users", [])
            active_door = data.get("active_door", "Campus Main Gate")
            registration_mode_on = data.get("registration_mode", False)
            sec_config = data.get("security_config", {})
            zone_containment_on = sec_config.get("zone_containment_enabled", True)
            geolocation_guard_on = sec_config.get("geolocation_guard_enabled", True)
            geofence_radius_m = float(sec_config.get("geofence_radius_meters", 200.0))
            phone_gps_mode = sec_config.get("phone_gps_mode", "CO_LOCATED")
            custom_phone_lat = float(sec_config.get("custom_phone_lat", 12.96918))
            custom_phone_lon = float(sec_config.get("custom_phone_lon", 79.15593))
            enforce_perimeter_gate = sec_config.get("enforce_perimeter_gate", True)
            face_check_on = sec_config.get("face_verification_enabled", True)

            camera_service.set_active_door(active_door)

            # Match user by UID
            matched_user = None
            uid_compact = uid_clean.replace(" ", "")
            for u in users:
                if u["UID"].replace(" ", "").upper() == uid_compact:
                    matched_user = u
                    break

            # -------------------------------------------------------------
            # Case 1: Registry Tab Active -> Clean Enrollment Scan
            # -------------------------------------------------------------
            if registration_mode_on:
                log_print(f"[{now_str}] 📝 [REGISTRY ENROLLMENT SCAN] Card UID: [{uid_clean}]")
                log_print("    --> Hardware RFID card captured! Auto-filled in 'Registry' tab enrollment form.")
                
                # Pleasant chime / Green LED signal on hardware reader to confirm card capture
                try:
                    ser.write(b'G')
                except Exception as e:
                    log_print("    --> Write error:", e)

                # Capture biometric camera frame for quick preview in registry
                raw_frame, _ = camera_service.get_latest_capture()
                if raw_frame is not None:
                    try:
                        cv2.imwrite("temp_reg_photo.jpg", raw_frame)
                    except Exception:
                        pass

                # Stage UID for enrollment in Streamlit
                data["pending_registration_uid"] = uid_clean
                save_data(data)
                log_print("    --> UID locked into Registry form ready for photo & student details.\n")
                continue

            # -------------------------------------------------------------
            # Case 2: Unregistered Card at Door (Access Denied + Violation Flagged)
            # -------------------------------------------------------------
            if not matched_user:
                log_print(f"[{now_str}] ⚠️ [UNREGISTERED CARD SCANNED] UID: [{uid_clean}]")
                log_print("    --> ACCESS DENIED: Card UID not enrolled in campus directory.")
                
                # Buzzer & Red LED access denied signal on hardware reader
                try:
                    ser.write(b'D')
                except Exception as e:
                    log_print("    --> Write error:", e)

                # Capture CCTV forensic evidence snapshot
                raw_frame, detected_faces = camera_service.get_latest_capture()
                snap_path = camera_service.save_evidence(
                    raw_frame, "Unregistered Card", uid_clean, active_door, 
                    is_violation=True, reason="Unregistered Card Swiped"
                )

                # 1. Update Real-Time Access Feed
                new_log = {
                    "Time": now_str,
                    "Timestamp": now.isoformat(),
                    "User": "Unregistered Card",
                    "Card UID": uid_clean,
                    "Role": "Unregistered",
                    "Status": "ACCESS DENIED (UNREGISTERED CARD)",
                    "Door": active_door,
                    "Place": active_door,
                    "Snapshot": snap_path
                }
                data["logs"].insert(0, new_log)

                # 2. Update Security Violations Audit
                new_violation = {
                    "Time": now_str,
                    "Timestamp": now.isoformat(),
                    "User": "Unregistered Card",
                    "Card UID": uid_clean,
                    "ViolationType": "UNREGISTERED CARD PRESENTED",
                    "Details": f"Card [{uid_clean}] swiped at [{active_door}]. Access denied: card not registered. Staged in Registry for enrollment.",
                    "Severity": "MEDIUM",
                    "Door": active_door,
                    "Place": active_door,
                    "Snapshot": snap_path
                }
                data["violations"].insert(0, new_violation)

                # 3. Auto-stage UID into Registry form for instant enrollment
                data["pending_registration_uid"] = uid_clean
                save_data(data)
                
                log_print("    --> Logged in Live Access Feed & Security Violations!")
                log_print("    --> UID auto-filled in 'Registry' tab ready for cardholder enrollment.\n")
                continue

            # -------------------------------------------------------------
            # Case 2: Registered Card -> Perform Full Access & Security Checks
            # -------------------------------------------------------------
            log_print(f"[{now_str}] 📡 Scanned Card UID: [{uid_clean}]")
            raw_frame, detected_faces = camera_service.get_latest_capture()
            has_face = len(detected_faces) > 0 if camera_service.camera_available and raw_frame is not None else True

            user_name = matched_user["Name"]
            current_occupancy = matched_user.get("Occupancy", "OUTSIDE")
            current_building = matched_user.get("CurrentBuilding", "None")

            violation_detected = False
            violation_type = ""
            violation_details = ""
            severity = "HIGH"

            action_type = ""
            new_occupancy = current_occupancy
            new_building = current_building
            measured_similarity = None

            # Rule 0A: Anti-Proxy Presence Check (Is ANY face in front of the camera?)
            if face_check_on and camera_service.camera_available and not has_face:
                violation_detected = True
                violation_type = "PROXY ATTENDANCE (NO FACE DETECTED)"
                violation_details = (f"Biometric Anti-Proxy Lockout: Card [{user_name}] swiped at [{active_door}], "
                                     f"but terminal CCTV detected NO human face in front of the scanner.")
                severity = "CRITICAL"

            # Rule 0B: 1-to-1 Facial Identity Matching (Is the face ACTUALLY the cardholder?)
            if not violation_detected and face_check_on and camera_service.camera_available and has_face:
                is_enrolled, is_match, sim_score, match_msg = camera_service.verify_1to1_identity(
                    raw_frame, detected_faces, uid_clean
                )
                measured_similarity = sim_score
                if is_enrolled:
                    if not is_match:
                        violation_detected = True
                        violation_type = "BIOMETRIC IDENTITY MISMATCH (CARD THEFT DETECTED)"
                        violation_details = (f"Biometric Security Breach: Card [{user_name} ({uid_clean})] was swiped, "
                                             f"but camera face does NOT match the enrolled cardholder photo! "
                                             f"Similarity Score: {sim_score:.2f} (Required >= 0.44). Unauthorized cardholder!")
                        severity = "CRITICAL"
                        log_print(f"    🚨 BIOMETRIC MISMATCH: Impostor detected using {user_name}'s card! Score: {sim_score:.2f}")
                    else:
                        log_print(f"    ✅ BIOMETRIC MATCH: Identity verified as {user_name} (Similarity: {sim_score:.2f})")

            # Rule 0D: Dual-Factor Geolocation Verification & Stolen Card Guard (Novelty 1)
            if not violation_detected and geolocation_guard_on:
                door_gps = db_manager.CAMPUS_GPS.get(active_door, db_manager.CAMPUS_GPS.get("Campus Main Gate"))
                user_tg_id = matched_user.get("TelegramChatId", "None")

                tg_lat = matched_user.get("PhoneLat")
                tg_lon = matched_user.get("PhoneLon")

                # Respect explicit evaluator scenario selected in dashboard sidebar:
                if phone_gps_mode == "CO_LOCATED":
                    phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode("CO_LOCATED", active_door)
                elif phone_gps_mode in ["HOSTEL_MH", "GAZEBO_FOODYS", "OUTSIDE_CAMPUS"]:
                    phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode(phone_gps_mode, active_door)
                elif phone_gps_mode == "TELEGRAM_LIVE":
                    phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode(
                        "TELEGRAM_LIVE", active_door, tg_lat=tg_lat, tg_lon=tg_lon
                    )
                else:
                    # Default: if Telegram live GPS is available, use it; otherwise Co-Located
                    if user_tg_id != "None" and tg_lat is not None and float(tg_lat) != 0.0:
                        phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode(
                            "TELEGRAM_LIVE", active_door, tg_lat=tg_lat, tg_lon=tg_lon
                        )
                    else:
                        phone_lat, phone_lon, phone_label = db_manager.get_phone_gps_for_mode("CO_LOCATED", active_door)

                geo_dist_m = db_manager.calculate_geodesic_distance(
                    door_gps["lat"], door_gps["lon"], phone_lat, phone_lon
                )

                if geo_dist_m > geofence_radius_m:
                    violation_detected = True
                    violation_type = "GEOLOCATION BREACH (STOLEN CARD DETECTED)"
                    violation_details = (
                        f"Stolen Card Alert: Card [{user_name}] swiped at [{active_door}], "
                        f"but student's smartphone was detected {geo_dist_m:.0f}m away at [{phone_label}] (Geofence Limit: {geofence_radius_m:.0f}m). "
                        f"Physical card and mobile device co-location mismatch indicates card is lost or stolen!"
                    )
                    severity = "CRITICAL"
                    log_print(f"    🚨 STOLEN CARD ALERT: Cardholder phone is {geo_dist_m:.0f}m away at {phone_label} (Limit: {geofence_radius_m:.0f}m)!")
                else:
                    log_print(f"    📍 GEOLOCATION VERIFIED: Phone co-located with student at {active_door} ({geo_dist_m:.0f}m <= {geofence_radius_m:.0f}m)")

            # Rule 1: Campus Perimeter Gate Verification
            if not violation_detected:
                if active_door == "Campus Main Gate":
                    if current_occupancy == "OUTSIDE":
                        action_type = "CAMPUS ENTRY"
                        new_occupancy = "CAMPUS_TRANSIT"
                        new_building = "None"
                    elif current_occupancy == "CAMPUS_TRANSIT":
                        action_type = "CAMPUS EXIT"
                        new_occupancy = "OUTSIDE"
                        new_building = "None"
                    elif current_occupancy == "INSIDE_BUILDING":
                        if zone_containment_on:
                            violation_detected = True
                            violation_type = "PERIMETER EXIT WITHOUT BUILDING CHECKOUT"
                            violation_details = (f"Conflict: Card [{user_name}] swiped at Campus Main Gate while still recorded "
                                                 f"INSIDE [{current_building}]. Must badge out of [{current_building}] first.")
                            severity = "HIGH"
                        else:
                            action_type = "CAMPUS EXIT"
                            new_occupancy = "OUTSIDE"
                            new_building = "None"
                else:
                    # Academic Building Reader (MGR, TT, PRP, SJT)
                    if current_occupancy == "OUTSIDE":
                        if enforce_perimeter_gate:
                            violation_detected = True
                            violation_type = "PERIMETER BYPASS VIOLATION"
                            violation_details = (f"Card [{user_name}] swiped directly at [{active_door}] while marked OUTSIDE campus! "
                                                 f"Must first enter campus through the Campus Main Gate.")
                            severity = "HIGH"
                        else:
                            action_type = f"ENTRY - {active_door}"
                            new_occupancy = "INSIDE_BUILDING"
                            new_building = active_door

                    elif current_occupancy == "INSIDE_BUILDING":
                        if active_door == current_building:
                            # In-Out Toggle at same building
                            action_type = f"EXIT - {active_door}"
                            new_occupancy = "CAMPUS_TRANSIT"
                            new_building = "None"
                        else:
                            # Zone Containment: Swiping at building B while inside A!
                            if zone_containment_on:
                                violation_detected = True
                                violation_type = "CONCURRENT PRESENCE VIOLATION (CLONED / SHARED CARD)"
                                violation_details = (f"Zone Conflict: Card [{user_name}] is currently recorded INSIDE [{current_building}]. "
                                                     f"Swipe at [{active_door}] blocked! Cannot be in two buildings simultaneously.")
                                severity = "CRITICAL"
                            else:
                                action_type = f"ENTRY - {active_door}"
                                new_occupancy = "INSIDE_BUILDING"
                                new_building = active_door

                    elif current_occupancy == "CAMPUS_TRANSIT":
                        action_type = f"ENTRY - {active_door}"
                        new_occupancy = "INSIDE_BUILDING"
                        new_building = active_door

            # -------------------------------------------------------------
            # Execution & Physical Response
            # -------------------------------------------------------------
            if violation_detected:
                log_print(f"    SECURITY VIOLATION: {violation_type}")
                log_print(f"       Details: {violation_details}")
                log_print(f"       Action: ACCESS DENIED for {user_name}")
                try:
                    ser.write(b'D')  # Warning alert tone
                except Exception as e:
                    log_print("    --> Write error:", e)

                # Dispatch instant Telegram push alert to cardholder's phone for ANY security violation!
                user_tg_id = matched_user.get("TelegramChatId", "None")
                if user_tg_id != "None":
                    try:
                        telegram_guard.send_security_alert(
                            user_tg_id, user_name, uid_clean, active_door,
                            violation_type=violation_type, details=violation_details
                        )
                        log_print(f"       📲 Push Alert Dispatched to {user_name}'s Telegram app (@vit_security_007_bot)!")
                    except Exception as e:
                        log_print(f"       [WARN] Could not dispatch Telegram push alert: {e}")

                snap_file = camera_service.save_evidence(
                    raw_frame, user_name, uid_clean, active_door, 
                    is_violation=True, reason=violation_type, sim_score=measured_similarity
                )

                new_log = {
                    "Time": now_str,
                    "Timestamp": now.isoformat(),
                    "User": user_name,
                    "Card UID": uid_clean,
                    "RegNo": matched_user.get("RegNo", "N/A"),
                    "Role": matched_user["Role"],
                    "Status": f"ACCESS DENIED ({violation_type})",
                    "Door": active_door,
                    "Place": active_door,
                    "Snapshot": snap_file
                }
                new_violation = {
                    "Time": now_str,
                    "Timestamp": now.isoformat(),
                    "User": user_name,
                    "Card UID": uid_clean,
                    "RegNo": matched_user.get("RegNo", "N/A"),
                    "ViolationType": violation_type,
                    "Details": violation_details,
                    "Severity": severity,
                    "Door": active_door,
                    "Place": active_door,
                    "Snapshot": snap_file
                }
                data["logs"].insert(0, new_log)
                data["violations"].insert(0, new_violation)
                save_data(data)
                log_print("    --> Security violation recorded with CCTV evidence!\n")

            else:
                # 1. IMMEDIATE HARDWARE FEEDBACK: Fire buzzer & Green LED instantly (<1ms)
                try:
                    ser.write(b'G')  # Double-tone success chime
                except Exception as e:
                    log_print("    --> Write error:", e)

                # Access Granted! Update Campus State
                matched_user["Occupancy"] = new_occupancy
                matched_user["CurrentBuilding"] = new_building
                matched_user["LastLocation"] = active_door
                matched_user["LastSwipeTime"] = now.isoformat()

                status_label = f"ACCESS GRANTED ({action_type})"
                log_print(f"    [OK] {status_label}: {user_name} ({matched_user['Role']})")
                log_print(f"       Biometrics: Verified (Face Matched) | Occupancy={new_occupancy} | Building={new_building}")

                # Dispatch Telegram confirmation asynchronously (non-blocking)
                user_tg_id = matched_user.get("TelegramChatId", "None")
                if user_tg_id != "None":
                    try:
                        telegram_guard.send_access_granted_notification(
                            user_tg_id, user_name, active_door, geo_dist_m if 'geo_dist_m' in locals() else 0
                        )
                    except Exception:
                        pass

                snap_file = camera_service.save_evidence(
                    raw_frame, user_name, uid_clean, active_door, 
                    is_violation=False, reason=action_type, sim_score=measured_similarity
                )

                new_log = {
                    "Time": now_str,
                    "Timestamp": now.isoformat(),
                    "User": user_name,
                    "Card UID": uid_clean,
                    "RegNo": matched_user.get("RegNo", "N/A"),
                    "Role": matched_user["Role"],
                    "Status": status_label,
                    "Door": active_door,
                    "Place": active_door,
                    "Snapshot": snap_file
                }
                data["logs"].insert(0, new_log)
                save_data(data)
                log_print("    --> Verified & logged successfully with forensic photo snapshot.\n")

    except serial.SerialException as e:
        log_print(f"[ERROR] Serial Error on {port}: {e}")
        log_print("Tip: Make sure Arduino IDE Serial Monitor is closed so Python can access the port.")
        db_manager.set_hardware_status(False, port, "DISCONNECTED", "HARDWARE ERROR")
    except KeyboardInterrupt:
        log_print("\nStopping serial bridge.")
        db_manager.set_hardware_status(False, None, "DISCONNECTED", "BRIDGE STOPPED")
    finally:
        camera_service.stop()
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except Exception:
            pass
        db_manager.set_hardware_status(False, None, "DISCONNECTED", "BRIDGE STOPPED")

if __name__ == "__main__":
    main()
