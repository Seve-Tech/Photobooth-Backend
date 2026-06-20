# Photobooth System Deployment & Handover Guide

This guide explains how to package your Python backend, database, and frontend kiosk application into a clean, "one-tap" installer folder for your client's Windows Mini PC.

---

## Deployment Architecture Overview
Once deployed, the system is fully automated:
* **Database (PostgreSQL):** Runs silently as a standard Windows service.
* **Backend Services (`photobooth-backend.exe` and `arduino-bridge.exe`):** Registered in **Windows Task Scheduler** to auto-start silently on boot.
* **Frontend Kiosk (`photobooth-frontend.exe`):** Accessible via a **"Start Photobooth"** desktop icon for the client to open when they are ready.

---

## 🛠️ Step 1: Pre-Deployment Preparations (On Your Dev Machine)

Before going to the client's site, you need to compile your Python scripts into executables.

1. **Activate your virtual environment:**
   ```powershell
   .\.venv\Scripts\activate
   ```
2. **Compile the Python services:**
   Run the build automation script:
   ```powershell
   .\build.ps1
   ```
   This will clean your build folders, verify your dependencies, and output two compiled `.exe` files into the `dist/` directory:
   * `dist\photobooth-backend.exe`
   * `dist\arduino-bridge.exe`

3. **Package your Frontend:**
   * Build/compile your frontend application into a standalone Windows executable. 
   * Name the compiled file `photobooth-frontend.exe` (or whatever you set in `$FRONTEND_EXE` inside the setup script).

4. **Download the PostgreSQL Offline Installer:**
   * Go to [PostgreSQL Windows Downloads](https://www.postgresql.org/download/windows/) and download the interactive installer for **Windows x86-64** (v16.x recommended).
   * Save the downloaded `.exe` file (e.g. `postgresql-16.3-1-windows-x64.exe`).

---

## 📦 Step 2: Preparing the Delivery Folder
Create a clean directory on a USB flash drive (or in your project folder) named `Photobooth-Delivery` and copy the following files into it:

```
📁 Photobooth-Delivery/
├── 📄 photobooth-backend.exe      (Copy from your project's dist/ folder)
├── 📄 arduino-bridge.exe          (Copy from your project's dist/ folder)
├── 📄 photobooth-frontend.exe     (Your compiled frontend kiosk app)
├── 📄 postgresql-16-installer.exe (The PostgreSQL installer you downloaded)
└── 📄 setup_tasks.ps1             (Copy from the root of this project)
```

---

## ⚙️ Step 3: Configure Deployment Values
Open the copy of `setup_tasks.ps1` that is inside your `Photobooth-Delivery` folder using any text editor (like Notepad) and edit the **CONFIGURATION** block at the top:

```powershell
# --- CONFIGURATION (EDIT BEFORE DEPLOYMENT) ---
$PG_PASSWORD   = "your-custom-db-password"  # Database superuser password
$API_KEY       = "your-secret-api-key"      # API Key matching your requirements
$BRANCH_ID     = 1                          # Branch ID for this machine
$UNIT_ID       = 1                          # Photobooth Unit ID
$DSLR_PASSWORD = "Z-crRWyKaYgFLZyn"         # Password configured in DSLRBooth API
$FRONTEND_URL  = "http://localhost:3000"     # Frontend URL (CORS origin policy)
$PORT          = 8000                        # Port the backend runs on
$FRONTEND_EXE  = "photobooth-frontend.exe"  # Must match your frontend executable name
# ----------------------------------------------
```
*Save and close the file.*

---

## 🚀 Step 4: Installation on the Client's Mini PC

Once you are at the client's site:

1. Copy the `Photobooth-Delivery` folder from your USB drive onto the Mini PC (e.g. paste it on the Desktop).
2. Open the folder, right-click **`setup_tasks.ps1`**, and select **Run with PowerShell** (or run PowerShell as Administrator and execute it).

**What the script does automatically:**
1. Installs PostgreSQL silently without prompt (engine-only; no pgAdmin).
2. Copies all executables to `C:\Photobooth\`.
3. Auto-generates `C:\Photobooth\.env` using your config block variables.
4. Performs DB initialization (`migrate` and `seed` tasks) via the backend `.exe`.
5. Wires the background tasks to run silently at Windows Startup.
6. Places the **"Start Photobooth"** shortcut on the Windows desktop.

---

## 🔄 Step 5: Post-Install Verification & Management

### How to check if services are running:
Because the services run silently in the background, you won't see terminal windows. You can check their status using PowerShell as Administrator:

* **Check Status:**
  ```powershell
  Get-ScheduledTask -TaskName "Photobooth-*"
  ```
* **Manually Restart Backend:**
  ```powershell
  Restart-ScheduledTask -TaskName "Photobooth-Backend"
  ```
* **Manually Restart Serial Bridge:**
  ```powershell
  Restart-ScheduledTask -TaskName "Photobooth-ArduinoBridge"
  ```

### ⚠️ Troubleshooting: What if a service is down?

If a service shows a status other than `Running` (such as `Ready` or `Disabled`), here is what will happen and how to fix it:

#### 1. If Backend Service (`Photobooth-Backend`) is Down:
* **Symptom:** Kiosk frontend screen shows a network connection error, or DSLRBooth integration fails to trigger/print.
* **Fix:** Run this in PowerShell as Administrator:
  ```powershell
  Start-ScheduledTask -TaskName "Photobooth-Backend"
  ```

#### 2. If Serial Bridge Service (`Photobooth-ArduinoBridge`) is Down:
* **Symptom:** Customers can insert paper bills into the bill acceptor, but the screen does NOT update or credit their session. (The hardware accepts bills but the software doesn't receive the count).
* **Fix:** Run this in PowerShell as Administrator:
  ```powershell
  Start-ScheduledTask -TaskName "Photobooth-ArduinoBridge"
  ```

*Note: You can also fix both by simply **restarting the Mini PC**, which forces Windows to launch them fresh at boot.*

### How to change config values later:
If you need to change settings (e.g. changing DSLRBooth password or Branch ID) after the script has run:
1. Open `C:\Photobooth\.env` with Notepad.
2. Edit your values and save.
3. Restart the Mini PC (or restart the scheduled tasks using the commands above) to apply changes.

---

## 🖥️ Step 6: Client Daily Operations Guide (Cheat Sheet)

You can copy and paste this section to print or send to the client as their daily operational guide.

### ☀️ Morning Routine: Starting the Photobooth
1. **Turn on the PC:** Press the physical power button on the Mini PC.
2. **Wait for Desktop:** Wait for Windows to boot up to the desktop screen.
   * *Note: The system's automated billing, DB, and bill acceptor listener will automatically load in the background (silently).*
3. **Do Daily Checks (Optional):** Check your printer paper/ink levels, ensure the DSLR camera is plugged in and turned on, and ensure internet is connected if cloud sync is needed.
4. **Launch Kiosk:** Double-tap the **"Start Photobooth"** icon on the Desktop.
5. **Start DSLRBooth:** If not configured to auto-start, open your DSLRBooth application as usual.

### 🌙 Night Routine: Shutting Down the Kiosk
1. **Exit the Kiosk Screen:** Tap the hidden admin gesture on the touch screen and enter your PIN, then press **Exit to Desktop** (or use your app's exit button).
2. **Shut Down Windows:** Go to the Windows Start Menu and select **Shut Down**.
   * *Alternatively:* If configured, press the physical power button on the Mini PC once to shut down the machine gracefully.

---

## 🔍 Step 7: Handover Verification & Kiosk Settings

Follow these instructions during deployment to ensure maximum background runtime stability and prevent common Windows kiosk issues.

### 🔋 1. Recommended Windows settings (Do this on-site)
Windows by default tries to save power by turning off USB ports if idle. This will break the Arduino bridge. Change this setting:
1. Open **Device Manager** on the Mini PC.
2. Expand the **Universal Serial Bus controllers** section.
3. For each entry named **USB Root Hub** (and **Generic USB Hub** if present):
   * Right-click $\rightarrow$ **Properties**.
   * Go to the **Power Management** tab.
   * **Uncheck** the box: `"Allow the computer to turn off this device to save power"`.
   * Click **OK**.

### 📋 2. On-Site Handover Checklist
Before leaving the client, execute these three tests to guarantee the background automation is rock-solid:

* [ ] **Test 1: System Reboot Test**
  * Restart the Mini PC. Wait for the Windows Desktop to load.
  * *Pass Criteria:* Open `http://localhost:8000/health` (or your health route) in a browser. The API should respond immediately. The services must start without you touching them.
* [ ] **Test 2: USB Disconnect & Recovery Test**
  * Open the frontend app and make sure it is connected. Unplug the Arduino USB cable, wait 5 seconds, then plug it back in.
  * *Pass Criteria:* Try inserting cash. The bridge should automatically re-establish the serial connection and correctly register cash on the screen without restarting any software.
* [ ] **Test 3: Sudden Power-Loss Test**
  * Pull the physical power plug of the Mini PC out of the wall while the photobooth is idle. Plug it back in and turn it on.
  * *Pass Criteria:* Windows should boot, background services start, and the PostgreSQL database should recover its state without errors or locks.


