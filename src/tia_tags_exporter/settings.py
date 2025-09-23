
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class DllProfile:
    tia_version: str = "V17"
    public_api_dir: Path | None = None
    assemblies: list[str] = field(default_factory=lambda: [
        "Siemens.Engineering.dll",
        "Siemens.Engineering.Hmi.dll",
        "Siemens.Engineering.AddIn.dll",
    ])
    public_key_token: str | None = "d29ec89bac048f84"  # Siemens strong-name token (doc examples)
    file_version: str | None = None
    last_validated: str | None = None

@dataclass
class AppConfig:
    profiles_dir: Path
    active_profile: Optional[DllProfile] = None
    priority_dirs: List[Path] = field(default_factory=list)
