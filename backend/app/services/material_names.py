# -*- coding: utf-8 -*-
"""素材 ID → 素材名 的本地名册。

为什么需要：千川操作日志里只有「素材ID」（如 1876023120663875），
但人看的是素材名（如「种草-复刻-热点型-#2610香味专项…」）。
不建这个名册，操作日志和素材数据就是两张皮，归因不到具体素材。

来源：素材分析 / 盯盘读取素材列表时顺手落盘（都是本机数据，不进仓库）。
"""

import json
from pathlib import Path
from typing import Iterable

NAMES_PATH = Path(__file__).resolve().parents[3] / ".local" / "material_names.json"


class MaterialNameStore:
    def __init__(self, path: Path = NAMES_PATH) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}

    def upsert(self, materials: Iterable) -> int:
        """收 [{"material_id","name"} 或 MaterialMetric]，返回新增/更新的条数。"""
        current = self.load()
        changed = 0
        for item in materials:
            if isinstance(item, dict):
                material_id = str(item.get("material_id") or "")
                name = str(item.get("name") or "")
            else:
                material_id = str(getattr(item, "material_id", "") or "")
                name = str(getattr(item, "name", "") or "")
            if not material_id or not name:
                continue
            if current.get(material_id) != name:
                current[material_id] = name
                changed += 1
        if changed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return changed

    def name_of(self, material_id: str) -> str:
        return self.load().get(str(material_id), "")
