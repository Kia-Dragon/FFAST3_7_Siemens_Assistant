# FFAST3.7 Siemens Assistant — TIA Tags Exporter

A Windows desktop GUI for extracting data from **Siemens TIA Portal V17 / V18** projects via the Openness API. Attach to a running TIA Portal instance, select devices, and export to Excel, CSV, or Google Sheets.

## Features

- **DLL Discovery Wizard** — automatically locates Siemens Openness assemblies across all fixed drives, with quality scoring and multi-folder resolution
- **TIA Portal V17 & V18** — profile-based support for both versions with one-click switching
- **Controller Tags Export** — PLC tag tables with optional comment, retentive, and address columns
- **Program Blocks Export** — block metadata and source code files (OB, FB, FC, DB)
- **HMI Information Export** — WinCC text lists, screens, alarms, and recipes as raw AML or flattened Excel
- **Devices & Networks Export** — device names, types, IP addresses, subnets, and IO systems
- **Output Formats** — Excel (.xlsx), CSV, and Google Sheets (with sharing)
- **Dark Mode** — toggle between light and dark themes

## Requirements

| Requirement | Version |
|---|---|
| Windows | 10 or 11 (x64) |
| Python | 3.12 x64 |
| .NET Framework | 4.8+ |
| TIA Portal | V17 or V18 with Openness installed |

Your Windows user account must be a member of the **"Siemens TIA Openness"** group.

## Installation

### PowerShell

```powershell
# Create the virtual environment (once)
py -3.12 -m venv .venv

# Activate
.\.venv\Scripts\activate.ps1

# Install dependencies (once)
pip install -r requirements.txt
```

> If activation fails with a script execution error, run once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Command Prompt (cmd.exe)

```cmd
:: Create the virtual environment (once)
py -3.12 -m venv .venv

:: Activate
.\.venv\Scripts\activate.bat

:: Install dependencies (once)
pip install -r requirements.txt
```

## Running the Application

The recommended entry point uses the boot-first loader, which prepares Siemens Openness DLL resolution before the GUI starts:

```
python -m tia_tags_exporter.app_boot
```

Alternatively, you can launch directly (requires a configured DLL profile):

```
python -m tia_tags_exporter.app
```

## First Run

On first launch the **DLL Discovery Wizard** opens automatically. It scans your drives for Siemens Openness assemblies, ranks candidates by quality, and saves a profile. You can also provide priority directories to speed up the scan.

If Windows shows an **Openness access prompt**, select **"Yes to all"**.

## Usage

1. **Configure** — Run the DLL Wizard for V17 or V18 to locate Openness assemblies
2. **Attach** — Click the Attach button for your TIA Portal version; the app connects to the running instance
3. **Select devices** — Choose one or more PLCs / HMI targets from the device list
4. **Export** — Pick an export type and output format, then export

### Export Types

| Export | Description | Formats |
|---|---|---|
| **Controller Tags** | PLC tag tables — name, data type, address, comment, retentive flag, scope | Excel, CSV, Google Sheets |
| **Program Blocks** | Block metadata (type, language, attributes, interface) plus source code files | Excel, CSV, Google Sheets |
| **HMI Information** | WinCC assets — text lists, screens, alarms, recipes | Raw AML/ZIP or flattened Excel |
| **Devices & Networks** | Device names, types, network interfaces, IP addresses, subnets, IO systems | Excel, CSV, Google Sheets |

## Project Structure

```
src/tia_tags_exporter/
├── app.py                      # Main entry point (QApplication)
├── app_boot.py                 # Boot-first loader — prepares CLR before GUI
├── openness_bridge.py          # pythonnet CLR loading & Siemens DLL binding
├── loader_multi.py             # Multi-directory assembly resolver
├── session.py                  # TiaSession — attach/detach to TIA Portal
├── discovery.py                # Drive scanning for Openness DLLs
├── validation.py               # Candidate ranking & DLL validation
├── config_store.py             # Profile persistence (~/.tia-tags-exporter/)
├── settings.py                 # DllProfile & AppConfig dataclasses
├── tag_extractor.py            # PLC tag table extraction
├── block_exporter.py           # Program block extraction
├── block_writer.py             # Block export to Excel/CSV/Google Sheets
├── devices_networks_exporter.py # Device & network config extraction
├── hmi_exporter.py             # HMI asset export (AML/XML)
├── hmi_flatteners.py           # AML/XML → flat tables
├── excel_writer.py             # Tag & device export writers
├── logging_utils.py            # Logging configuration
└── gui/
    ├── main_window.py          # Primary application window
    ├── dll_wizard_window.py    # DLL wizard host & tutorial
    ├── wizard.py               # Discovery wizard dialog
    └── hmi_export_window.py    # HMI export window
```

## Troubleshooting

- **DLL resolution fails** — The boot-first loader (`app_boot.py`) sanitises PATH and installs an `AppDomain.AssemblyResolve` handler. If you still get `FileLoadException` or `TypeInitializationException`, ensure no conflicting `bin` directories appear early in your system PATH.
- **Openness access prompt** — Select "Yes to all" when Windows asks for Openness permissions.
- **No devices listed after attach** — Verify your TIA project is open and contains at least one PLC or HMI device.
- **Google Sheets export** — Requires `gspread` and `google-auth` with valid Google service account credentials.
