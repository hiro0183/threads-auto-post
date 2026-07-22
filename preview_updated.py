# -*- coding: utf-8 -*-
import json
from pathlib import Path

POSTS_DIR = Path(r"C:\Users\tujid\threads_tool\posts")
OUT = Path(r"C:\Users\tujid\OneDrive\Desktop\コンサル投稿確認\preview_updated_0616-0618.txt")

UPDATED_SLOTS = {
    "2026-06-16": {"06:30","08:30","09:00","10:15","10:30","15:00","18:00","19:30"},
    "2026-06-17": {"05:00","05:15","09:00","10:30","19:00"},
    "2026-06-18": {"05:15","06:00","09:30","11:30","14:30","19:30"},
}

lines = []
for date in ["2026-06-16", "2026-06-17", "2026-06-18"]:
    data = json.loads((POSTS_DIR / f"{date}.json").read_text(encoding="utf-8"))
    lines.append(f"\n{'='*60}")
    lines.append(f"  {date}")
    lines.append(f"{'='*60}")
    for slot, content in sorted(data.items()):
        mark = "★" if slot in UPDATED_SLOTS.get(date, set()) else "  "
        if isinstance(content, list):
            lines.append(f"\n{mark} {slot}")
            lines.append(f"    (1) {content[0]}")
            lines.append(f"    (2) {content[1]}")
            lines.append(f"    (3) {content[2]}")
        else:
            lines.append(f"\n{mark} {slot}: {content}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"出力: {OUT}")
print("★=今回差し替え")
