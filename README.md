# TIA Tags Exporter (V17)

A Windows desktop tool that:

1. Discovers **Siemens TIA Openness** assemblies (e.g., `Siemens.Engineering.dll`) anywhere on your machine.
2. Attaches to a **running TIA Portal V17** instance.
3. Extracts **PLC Tag Tables** (name, type, address if present, comment, retentive) and writes a compact **Excel** workbook.

## Install

```powershell
py -3.12 -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Ensure: Windows 10/11 x64, Python 3.12 x64, TIA Portal **V17** installed with Openness, and your user is in the **"Siemens TIA Openness"** group.

## Run

```powershell
python -m tia_tags_exporter.app
# or, if installed via project scripts
TIA-Tags-Exporter
```

## Notes
- First run opens the **DLL Discovery & Configuration Wizard**. You can provide **priority directories**, or let it scan all fixed drives.
- If Windows shows an **Openness access** prompt, select **"Yes to all"**.
- The output is `PLC_Tags.xlsx` with a single sheet `PLC_Tags`.
