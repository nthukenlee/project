from __future__ import annotations

import json
from pathlib import Path

from .constants import I18N_DIR


class Localizer:
    supported = ("zh_TW", "en")

    def __init__(self, language: str = "zh_TW", data_dir: Path = I18N_DIR) -> None:
        self.data_dir = data_dir
        self.catalogs: dict[str, dict[str, str]] = {}
        for code in self.supported:
            with (data_dir / f"{code}.json").open("r", encoding="utf-8") as handle:
                self.catalogs[code] = json.load(handle)
            for revision in ('v5','v6','v7'):
                supplement = data_dir / f"{code}_{revision}.json"
                if supplement.exists():
                    with supplement.open("r", encoding="utf-8") as handle:
                        self.catalogs[code].update(json.load(handle))
        self.language = language if language in self.supported else "zh_TW"

    def set_language(self, language: str) -> None:
        if language not in self.supported:
            raise ValueError(f"Unsupported language: {language}")
        self.language = language

    def t(self, key: str, **values: object) -> str:
        text = self.catalogs[self.language].get(key)
        if text is None:
            text = self.catalogs["zh_TW"].get(key, f"[{key}]")
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            return text

    def missing_keys(self) -> dict[str, set[str]]:
        all_keys = set().union(*(catalog.keys() for catalog in self.catalogs.values()))
        return {code: all_keys - set(catalog) for code, catalog in self.catalogs.items()}
