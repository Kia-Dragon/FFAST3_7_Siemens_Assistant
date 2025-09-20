
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Iterable
from openpyxl import Workbook

_DEF_HEADERS = [
    'ProjectName','PLC_Name','TagTable','TagName','DataType','Address','Comment','Retentive','Scope','TagId'
]


def write_tags_xlsx(rows: Iterable, out_path: Path) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet('PLC_Tags')
    ws.append(_DEF_HEADERS)
    for r in rows:
        if hasattr(r, '__dict__'):
            data = [getattr(r, h) for h in _DEF_HEADERS]
        else:
            data = r
        ws.append(data)
    # remove the default sheet if present
    if 'Sheet' in wb.sheetnames and len(wb.sheetnames) > 1:
        std = wb['Sheet']
        wb.remove(std)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
