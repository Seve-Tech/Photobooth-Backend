# Photobooth System Deployment & Handover Guide

This guide explains how to package the Python backend, PostgreSQL database, and Electron frontend kiosk into a delivery folder for the client's Windows Mini PC.

---

## Deployment Architecture Overview

Once deployed, the system is fully automated:

* **Database (PostgreSQL):** Runs silently as a standard Windows service.
* **Backend services (`paywall-server.exe` and `bill-acceptor.exe`):** Registered in **Windows Task Scheduler** to auto-start silently on boot.
* **Frontend kiosk (`Paywall dslrBooth.exe`):** An Electron desktop app installed to `C:\Photobooth\frontend-app\`. The client launches it via a **"Start Photobooth"** desktop shortcut (or `start_photobooth.ps1 -LaunchFrontend`).

---

## 🛠️ Step 1: Build Everything (On Your Dev Machine)

### 1. Build the backend executables

From the `backend` folder, activate the virtual environment and run the build script:

```powershell
cd backend
.\.venv\Scripts\activate
cd deployment
.\build.ps1
```

This compiles two standalone `.exe` files into `backend\dist\`:

* `dist\paywall-server.exe` — FastAPI backend
* `dist\bill-acceptor.exe` — Arduino serial bridge

### 2. Build the frontend Electron app

From the `frontend` folder, run the desktop build:

```powershell
cd frontend
npm install   # first time only
npm run dist
```

`electron-builder` outputs the unpacked Windows app to:

```
frontend\dist-app\win-unpacked\
```

This is a **full application folder**, not a single file. It includes `Paywall dslrBooth.exe` plus all Electron runtime files (`resources\`, DLLs, locales, etc.) required to run the kiosk. Do not copy only the `.exe` — the entire `win-unpacked` directory is needed.

The main executable inside that folder must be named `Paywall dslrBooth.exe` (matching `$FRONTEND_EXE` in `setup_tasks.ps1`). This name comes from `productName` in `frontend\package.json`.

### 3. Download the PostgreSQL offline installer

* Go to [PostgreSQL Windows Downloads](https://www.postgresql.org/download/windows/) and download the interactive installer for **Windows x86-64** (v16.x recommended).
* Save the `.exe` into `backend\deployment\` (e.g. `postgresql-16.14-2-windows-x64.exe`).

### 4. Prepare the backend `.env`

The backend reads configuration from a `.env` file in its working directory (`config.py` sets `env_file: ".env"`). Before packaging, ensure `backend\.env` exists with production values for this deployment:

```powershell
cd backend
copy .env.example .env   # first time only
# Edit .env — set API_KEY, DATABASE_URL, FRONTEND_ORIGIN, BRANCH_ID, UNIT_ID, DSLRBOOTH_* etc.
```

`package_delivery.ps1` copies this file into the delivery folder so `paywall-server.exe` has the config it needs at install time and runtime.

### 5. Assemble the delivery package

With the backend built, frontend unpacked, `.env` configured, and PostgreSQL installer in place, run:

```powershell
cd backend\deployment
.\package_delivery.ps1
```

This script:

1. Runs `build.ps1` again (use `.\package_delivery.ps1 -SkipBuild` to skip if you already built).
2. Verifies all required artifacts exist.
3. Creates a ready-to-copy folder at the **project root**: `magnified-memories\`.

To rebuild only the delivery folder without recompiling the backend:

```powershell
.\package_delivery.ps1 -SkipBuild
```

---

## 📦 Step 2: Delivery Folder Contents

After `package_delivery.ps1` completes, `magnified-memories\` contains:

```
📁 magnified-memories/
├── 📄 paywall-server.exe
├── 📄 bill-acceptor.exe
├── 📄 .env                                 (backend config — required by paywall-server.exe)
├── 📄 postgresql-16.14-2-windows-x64.exe   (your downloaded installer)
├── 📄 INSTALL.bat                          (double-click to install — requests Admin)
├── 📄 setup_tasks.ps1                      (installer script — run by INSTALL.bat)
├── 📄 start_photobooth.ps1                 (daily startup helper)
└── 📁 frontend-app/                        (entire win-unpacked Electron app)
    ├── 📄 Paywall dslrBooth.exe
    ├── 📁 resources/
    └── ... (other Electron runtime files)
```

Copy the entire `magnified-memories` folder to a USB drive for transport to the client site.

> **Manual assembly (optional):** If you cannot run `package_delivery.ps1`, create the folder above manually. Copy `frontend\dist-app\win-unpacked\*` into `frontend-app\` — the full folder contents, not just the executable.

---

## ⚙️ Step 3: Configure Deployment Values

All backend configuration lives in `backend\.env`. Edit it on your dev machine **before** running `package_delivery.ps1`:

```ini
API_KEY=your-secret-api-key
FRONTEND_ORIGIN=null
DATABASE_URL=postgresql://postgres:your-db-password@localhost:5432/photobooth_db
BRANCH_ID=1
UNIT_ID=1
DSLRBOOTH_PASSWORD=your-dslrbooth-api-pass
PORT=8000
# ... other settings — see backend\.env.example
```

`package_delivery.ps1` copies this file into the delivery folder. `setup_tasks.ps1` reads it on the client machine — including the PostgreSQL password parsed from `DATABASE_URL` for the silent installer.

If you need to tweak values after packaging, edit `.env` directly inside your `magnified-memories` copy before going on-site.

*Save and close the file.*

---

## 🚀 Step 4: Installation on the Client's Mini PC

1. Copy the `magnified-memories` folder from your USB drive onto the Mini PC (e.g. Desktop).
2. Double-click **`INSTALL.bat`** inside the folder.
3. Approve the **Administrator** UAC prompt when Windows asks.

No terminal commands are needed. `INSTALL.bat` elevates privileges and runs `setup_tasks.ps1` automatically.

> **Alternative:** Right-click `setup_tasks.ps1` → **Run with PowerShell** as Administrator.

**What the script does automatically:**

1. Installs PostgreSQL silently (engine only; no pgAdmin or Stack Builder).
2. Copies `paywall-server.exe`, `bill-acceptor.exe`, and the entire `frontend-app\` folder to `C:\Photobooth\`.
3. Copies the bundled `.env` to `C:\Photobooth\.env` (configuration is read from this file).
4. Runs database `migrate` and `seed` via `paywall-server.exe`.
5. Registers **Photobooth-Backend** and **Photobooth-ArduinoBridge** in Task Scheduler (auto-start at user logon).
6. Creates a **"Start Photobooth"** desktop shortcut pointing to `C:\Photobooth\frontend-app\Paywall dslrBooth.exe`.
7. Copies helper scripts (`run_backend.ps1`, `run_bridge.ps1`, `start_photobooth.ps1`) to `C:\Photobooth\`.
8. Starts the backend and bridge silently in the background.

**Installed layout on the Mini PC:**

```
C:\Photobooth\
├── paywall-server.exe
├── bill-acceptor.exe
├── .env
├── start_photobooth.ps1
└── frontend-app\
    ├── Paywall dslrBooth.exe
    └── ... (Electron runtime files)
```

---

## 🔄 Step 5: Post-Install Verification & Management

### How background services start

| When | What runs |
|------|-----------|
| **Windows logon** | Task Scheduler runs `run_backend.ps1` and `run_bridge.ps1`, which start the `.exe` files hidden (no terminal windows). |
| **Daily / manual** | Run `start_photobooth.ps1` — starts PostgreSQL if needed, then the same hidden background processes. |

> **Note:** Task Scheduler registers tasks during **install** (`setup_tasks.ps1` / `INSTALL.bat`). `start_photobooth.ps1` does not register tasks — it starts the services directly for daily use.

### How to check if services are running

Background services run without visible terminal windows. Check status in PowerShell (Administrator):

* **Check processes in Task Manager:** look for `paywall-server.exe` and `bill-acceptor.exe`.
* **Check status:**
  ```powershell
  Get-ScheduledTask -TaskName "Photobooth-*"
  ```
* **Manually restart backend:**
  ```powershell
  Restart-ScheduledTask -TaskName "Photobooth-Backend"
  ```
* **Manually restart serial bridge:**
  ```powershell
  Restart-ScheduledTask -TaskName "Photobooth-ArduinoBridge"
  ```

### ⚠️ Troubleshooting: What if a service is down?

#### 1. If Backend Service (`Photobooth-Backend`) is down

* **Symptom:** Kiosk shows a network connection error, or DSLRBooth integration fails to trigger/print.
* **Fix:**
  ```powershell
  Start-ScheduledTask -TaskName "Photobooth-Backend"
  ```

#### 2. If Serial Bridge Service (`Photobooth-ArduinoBridge`) is down

* **Symptom:** Bills are accepted by the hardware but the screen does not update or credit the session.
* **Fix:**
  ```powershell
  Start-ScheduledTask -TaskName "Photobooth-ArduinoBridge"
  ```

*Note: Restarting the Mini PC also relaunches both tasks at boot.*

### How to change config values later

1. Open `C:\Photobooth\.env` with Notepad.
2. Edit values and save.
3. Restart the Mini PC (or restart the scheduled tasks above) to apply changes.

---

## 🖥️ Step 6: Client Daily Operations Guide (Cheat Sheet)

You can copy this section for the client.

### ☀️ Morning routine: Starting the photobooth

1. **Turn on the PC** and wait for the Windows desktop.
   * *PostgreSQL, the backend, and the bill-acceptor bridge start automatically in the background.*
2. **Do daily checks (optional):** Printer paper/ink, DSLR camera on and connected, internet if needed.
3. **Launch the kiosk:** Double-click the **"Start Photobooth"** desktop shortcut.

   Or, from PowerShell:
   ```powershell
   C:\Photobooth\start_photobooth.ps1 -LaunchFrontend
   ```
   Without `-LaunchFrontend`, the script only verifies and starts background services.

4. **Start DSLRBooth** if it is not configured to auto-start.

### 🌙 Night routine: Shutting down

1. **Exit the kiosk:** Use the admin gesture on the touch screen, enter the PIN, and press **Exit to Desktop**.
2. **Shut down Windows** from the Start menu (or use the physical power button if configured for graceful shutdown).

---

## 🔍 Step 7: Handover Verification & Kiosk Settings

### 🔋 1. Recommended Windows settings (on-site)

Windows may power off idle USB ports, which breaks the Arduino bridge:

1. Open **Device Manager**.
2. Expand **Universal Serial Bus controllers**.
3. For each **USB Root Hub** (and **Generic USB Hub** if present):
   * Right-click → **Properties** → **Power Management**.
   * **Uncheck** *Allow the computer to turn off this device to save power*.
   * Click **OK**.

### 📋 2. On-site handover checklist

* [ ] **Test 1: System reboot**
  * Restart the Mini PC. After the desktop loads, open `http://localhost:8000/health` in a browser. The API should respond without manual intervention.
* [ ] **Test 2: USB disconnect & recovery**
  * Open the kiosk app. Unplug the Arduino USB cable, wait 5 seconds, plug it back in.
  * *Pass:* Inserting cash registers on screen without restarting software.
* [ ] **Test 3: Sudden power-loss**
  * Unplug power while idle, then restore and boot.
  * *Pass:* Windows boots, services start, and PostgreSQL recovers without errors.
