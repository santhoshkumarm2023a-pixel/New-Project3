# Lab Report Submission

## 1. Title
**IoT-Based Smart RFID Authentication and Access Control Management System**

---

## 2. What's your website do? (in 2 lines)
> A centralized security dashboard that authenticates RFID card scans from an Arduino reader in real time, granting or denying entry based on authorized credentials. It provides live access logs, card registration, and manual security controls for monitoring secure access points.

---

## 3. Website Screenshots & User Interface

### Screenshot 1: Main Overview & Live Access Logs
* **Description**: Displays the system header, top telemetry KPIs (Total Scans, Access Granted, Access Denied, Registered Cards), hardware connection indicators (`Arduino UNO COM3`, `RC522 Active`), simulation swipe controls, and the real-time access log feed.
* *(Insert Screenshot 1 here)*

### Screenshot 2: User & Card Registration Registry
* **Description**: Shows the interactive card enrolment form allowing administrators to register new users (Name, RFID Card UID, Role) and immediately see the updated authorized credentials database table.
* *(Insert Screenshot 2 here)*

### Screenshot 3: Access Analytics & Verification Breakdown
* **Description**: Visualizes access control metrics using dynamic bar charts, including Access Verification Breakdown (Granted vs. Denied swiping ratios) and User Demographics categorized by assigned Role (Student, Faculty, Security/Staff).
* *(Insert Screenshot 3 here)*

---

## 4. Backend Architecture
The system follows a four-tier embedded IoT architecture:
1. **Edge Hardware Layer**: Arduino UNO interfaced via SPI protocol with the RC522 RFID reader module (reads 13.56 MHz RFID tags) and output actuators (LED / Relay / Buzzer).
2. **Communication Bridge Layer**: Serial communication (UART over USB at 9600 baud) bridges hardware tag scan events to the host computer.
3. **Application & Verification Layer**: Python core backend processes UID packets, validates permissions against the user database, and triggers access grant/deny responses back to the microcontroller.
4. **Presentation Layer**: Python Streamlit web frontend displaying real-time access telemetry, user management, and security audit metrics.

```
[RFID Tag] 
    │ (Radio Frequency: 13.56 MHz)
    ▼
[RC522 Module] ──(SPI Bus)──> [Arduino UNO]
                                   │
                                   │ (USB Serial / UART @ 9600 baud)
                                   ▼
                            [Python Backend] 
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
           [Local Database]                [Python Web Frontend]
        (Authorized UIDs & Logs)          (Live Streamlit Dashboard)
```

---

## 5. Are you hosting? If yes, where are you hosting?
> **No**, the dashboard is currently hosted on **Localhost (`http://localhost:8501`)**. Since it directly interfaces with the physical Arduino UNO board through local hardware serial COM ports, running locally ensures low latency and secure offline access control.

---

## Appendix: Hardware & Serial Specifications

### RC522 to Arduino UNO Pinout
| RC522 Pin | Arduino UNO Pin | Function |
|-----------|-----------------|----------|
| **VCC**   | 3.3V            | Power (Do NOT use 5V) |
| **RST**   | D9              | Reset |
| **GND**   | GND             | Ground |
| **MISO**  | D12             | SPI Master In Slave Out |
| **MOSI**  | D11             | SPI Master Out Slave In |
| **SCK**   | D13             | SPI Serial Clock |
| **SDA (SS)** | D10          | SPI Slave Select |

### Local Execution Instructions
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the Streamlit dashboard:
   ```bash
   streamlit run app.py
   ```
3. Open `http://localhost:8501` in your browser.
