from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from .constants import APP_FOLDER
from .state import GameState


class SaveManager:
    def __init__(self, save_dir: Path | None = None) -> None:
        if save_dir is None:
            base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            save_dir = base / APP_FOLDER
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, slot: int | str) -> Path:
        name = "autosave" if slot == "auto" else f"slot_{int(slot)}"
        return self.save_dir / f"{name}.json"

    def save(self, state: GameState, slot: int | str = "auto") -> Path:
        target = self.path_for(slot)
        temporary = target.with_suffix(".tmp")
        payload = state.to_dict()
        payload["saved_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Windows antivirus/indexing can briefly hold the destination open.
        # Keep the previous JSON intact if the atomic replacement still fails.
        for attempt in range(4):
            try:
                temporary.replace(target)
                break
            except PermissionError:
                if attempt==3: raise
                time.sleep(.025*(attempt+1))
        return target

    def load(self, slot: int | str = "auto") -> GameState | None:
        target = self.path_for(slot)
        if not target.exists():
            return None
        try:
            return GameState.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            corrupt = target.with_name(f"{target.stem}.corrupt-{stamp}.json")
            try:
                shutil.copy2(target, corrupt)
            except OSError:
                pass
            return None

    def newest_available(self) -> int | str | None:
        choices: list[tuple[float, int | str]] = []
        for slot in ("auto", 1, 2, 3):
            path = self.path_for(slot)
            if path.exists():
                choices.append((path.stat().st_mtime, slot))
        return max(choices)[1] if choices else None

    def metadata(self, slot: int | str) -> dict[str, object] | None:
        target = self.path_for(slot)
        if not target.exists():
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return {
                "saved_at": data.get("saved_at", ""),
                "visited": len(data.get("visited_zones", [])),
                "photos": len(data.get("photos", [])),
                "seconds": int(data.get("play_seconds", 0)),
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
