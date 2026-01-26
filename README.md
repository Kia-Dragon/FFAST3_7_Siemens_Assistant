# TIA Tags Exporter (V17)

A Windows desktop tool that:

1. Discovers **Siemens TIA Openness** assemblies (e.g., `Siemens.Engineering.dll`) anywhere on your machine.
2. Attaches to a **running TIA Portal V17** instance.
3. Extracts **PLC Tag Tables** (name, type, address if present, comment, retentive) and writes a compact **Excel** workbook.

## How to Run

To run the application, you must first activate the Python virtual environment (`.venv`). The command differs depending on your terminal. These commands should be run from the project root directory.

### If using PowerShell

1.  **Create and activate the environment:**
    ```powershell
    # Create the virtual environment (only needs to be done once)
    py -3.12 -m venv .venv
    
    # Activate the virtual environment
    .\.venv\Scripts\activate.ps1
    ```

2.  **Install dependencies (only needs to be done once):**
    ```powershell
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```powershell
    python -m tia_tags_exporter.app
    ```

> **Note:** If activation fails with an error about scripts being disabled, you may need to adjust your PowerShell execution policy. Run this command once to allow local scripts, then try activating again:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### If using Command Prompt (cmd.exe)

1.  **Create and activate the environment:**
    ```cmd
    :: Create the virtual environment (only needs to be done once)
    py -3.12 -m venv .venv

    :: Activate the virtual environment
    .\.venv\Scripts\activate.bat
    ```
    
2.  **Install dependencies (only needs to be done once):**
    ```cmd
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```cmd
    python -m tia_tags_exporter.app
    ```

> Ensure: Windows 10/11 x64, Python 3.12 x64, TIA Portal **V17** installed with Openness, and your user is in the **"Siemens TIA Openness"** group.

## Notes
- First run opens the **DLL Discovery & Configuration Wizard**. You can provide **priority directories**, or let it scan all fixed drives.
- If Windows shows an **Openness access** prompt, select **"Yes to all"**.
- The output is `PLC_Tags.xlsx` with a single sheet `PLC_Tags`.
