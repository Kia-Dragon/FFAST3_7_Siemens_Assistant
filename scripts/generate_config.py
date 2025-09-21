
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

def find_tia_portal_v17():
    """
    Scans for TIA Portal V17 installations.
    """
    common_paths = [
        "C:\\Siemens\\Portal V17\\PublicAPI\\V17",
        "C:\\Program Files\\Siemens\\Automation\\Portal V17\\PublicAPI\\V17",
    ]

    for path in common_paths:
        if Path(path).exists() and "Siemens.Engineering.dll" in [f.name for f in Path(path).iterdir()]:
            return Path(path)

    for drive in [f"{d}:" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{d}:").exists()]:
        for root, dirs, files in os.walk(drive):
            if "Siemens.Engineering.dll" in files and "PublicAPI" in root and "V17" in root:
                return Path(root)
    return None

def generate_config(public_api_dir: Path, output_path: Path):
    """
    Generates the python.exe.config file.
    """
    assemblies = []
    for root, _, files in os.walk(public_api_dir):
        for file in files:
            if file.startswith("Siemens.") and file.endswith(".dll"):
                assemblies.append(Path(root) / file)

    # Create the XML structure
    configuration = ET.Element("configuration")
    runtime = ET.SubElement(configuration, "runtime")
    assembly_binding = ET.SubElement(runtime, "assemblyBinding", xmlns="urn:schemas-microsoft-com:asm.v1")

    # Add Siemens.Engineering.dll first
    se_dll = public_api_dir / "Siemens.Engineering.dll"
    if se_dll in assemblies:
        assemblies.remove(se_dll)
        assemblies.insert(0, se_dll)

    for assembly_path in assemblies:
        dependent_assembly = ET.SubElement(assembly_binding, "dependentAssembly")
        assembly_identity = ET.SubElement(dependent_assembly, "assemblyIdentity", name=assembly_path.stem, publicKeyToken="d29ec89bac048f84", culture="neutral")
        code_base = ET.SubElement(dependent_assembly, "codeBase", href=f"file:///{str(assembly_path).replace('\\', '/')}")

    tree = ET.ElementTree(configuration)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    venv_path = project_root / ".venv"
    config_path = venv_path / "Scripts" / "python.exe.config"
    
    print(f"Project root: {project_root}")
    print(f"Virtual environment path: {venv_path}")
    print(f"Will generate config file at: {config_path}")

    print("Searching for TIA Portal V17 installation...")
    public_api_path = find_tia_portal_v17()

    if public_api_path:
        print(f"Found PublicAPI directory: {public_api_path}")
        generate_config(public_api_path, config_path)
        print(f"Successfully generated {config_path}")
    else:
        print("Could not find TIA Portal V17 installation.")
