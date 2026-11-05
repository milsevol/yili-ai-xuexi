"""策略持久化：本地 JSON 文件，无需数据库。"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .templates import SEED_STRATEGIES


class StrategyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.is_file():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and isinstance(raw.get("strategies"), list):
                    return raw
            except (json.JSONDecodeError, OSError):
                pass
        data = {"strategies": []}
        now = datetime.now().isoformat(timespec="seconds")
        for index, tpl in enumerate(SEED_STRATEGIES):
            data["strategies"].append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "name": tpl["name"],
                    "code": tpl["code"],
                    "created_at": now,
                    "updated_at": now,
                    "order": index,
                }
            )
        self._save(data)
        return data

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict]:
        with self._lock:
            items = sorted(self._data["strategies"], key=lambda s: s.get("order", 0))
            return [
                {"id": s["id"], "name": s["name"], "updated_at": s["updated_at"]}
                for s in items
            ]

    def get(self, sid: str) -> dict | None:
        with self._lock:
            for item in self._data["strategies"]:
                if item["id"] == sid:
                    return dict(item)
        return None

    def save(self, name: str, code: str, sid: str | None = None) -> dict:
        name = (name or "").strip() or "未命名策略"
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            for item in self._data["strategies"]:
                if sid and item["id"] == sid:
                    item["name"] = name
                    item["code"] = code
                    item["updated_at"] = now
                    self._save(self._data)
                    return dict(item)
            item = {
                "id": uuid.uuid4().hex[:10],
                "name": name,
                "code": code,
                "created_at": now,
                "updated_at": now,
                "order": len(self._data["strategies"]),
            }
            self._data["strategies"].append(item)
            self._save(self._data)
            return dict(item)

    def delete(self, sid: str) -> bool:
        with self._lock:
            before = len(self._data["strategies"])
            self._data["strategies"] = [s for s in self._data["strategies"] if s["id"] != sid]
            if len(self._data["strategies"]) != before:
                self._save(self._data)
                return True
        return False
