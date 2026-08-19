#!/usr/bin/env python3
from pathlib import Path
from src.import_export.csv_contracts import FIELDSETS, template_csv

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'data'/'templates'
out.mkdir(parents=True,exist_ok=True)
for name in FIELDSETS:
    (out/f'{name}.csv').write_text(template_csv(name),encoding='utf-8')
    print(f'WROTE {out/f"{name}.csv"}')
