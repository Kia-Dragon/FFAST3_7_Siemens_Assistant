
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from .settings import DllProfile

class ProfileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / 'profiles.json'

    def load(self) -> dict:
        if not self.file.exists():
            return {}
        return json.loads(self.file.read_text(encoding='utf-8'))

    def save(self, data: dict) -> None:
        self.file.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def get_profile(self, version: str = 'V17') -> Optional[DllProfile]:
        data = self.load()
        prof = data.get(version)
        if not prof:
            return None
        return DllProfile(**prof)

    def set_profile(self, profile: DllProfile) -> None:


        data = self.load()


        raw = asdict(profile)




        # Convert non-JSON types (e.g., pathlib.Path) to str, recursively


        from pathlib import Path as _Path


        def _normalize(obj):


            if isinstance(obj, _Path):


                return str(obj)


            if isinstance(obj, dict):


                return {k: _normalize(v) for k, v in obj.items()}


            if isinstance(obj, (list, tuple)):


                return [_normalize(x) for x in obj]


            return obj




        data[profile.tia_version] = _normalize(raw)


        self.save(data)

