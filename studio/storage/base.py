from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")
_WINDOWS_RESERVED_DEVICE_NAMES = frozenset(
    ("CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)))
)
_SAVE_LOCKS_GUARD = threading.Lock()
_SAVE_LOCKS: dict[str, threading.Lock] = {}
_REPLACE_RETRY_DELAYS_SECONDS = (0.01, 0.05, 0.1, 0.2, 0.5, 1.0)


def _lock_for_path(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _SAVE_LOCKS_GUARD:
        lock = _SAVE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SAVE_LOCKS[key] = lock
        return lock


class JsonRepository(Generic[ModelT]):
    def __init__(self, root: Path, model_type: type[ModelT]) -> None:
        self.root = root
        self.model_type = model_type
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_object_id(self, object_id: str) -> str:
        if not isinstance(object_id, str) or not object_id.strip():
            raise ValueError("object_id must be a non-empty string")
        if object_id in {".", ".."}:
            raise ValueError("object_id must not be '.' or '..'")
        if "/" in object_id or "\\" in object_id or ".." in object_id:
            raise ValueError("object_id must not contain path separators or '..'")
        root_name = object_id.split(".", 1)[0].upper()
        if root_name in _WINDOWS_RESERVED_DEVICE_NAMES:
            raise ValueError(f"object_id is a Windows reserved device name: {object_id!r}")
        if not _SAFE_ID_PATTERN.match(object_id):
            raise ValueError(f"object_id contains unsafe characters: {object_id!r}")
        return object_id

    def _path_for(self, object_id: str) -> Path:
        safe_object_id = self._validate_object_id(object_id)
        return self.root / f"{safe_object_id}.json"

    def save(self, model: ModelT) -> ModelT:
        payload = model.model_dump()
        if "id" not in payload:
            raise ValueError(f"{self.model_type.__name__} must define an 'id' field")
        object_id = self._validate_object_id(str(payload["id"]))
        path = self._path_for(object_id)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        with _lock_for_path(path):
            try:
                temp_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
                self._replace_with_retry(temp_path, path)
            finally:
                temp_path.unlink(missing_ok=True)
        return model

    def _replace_with_retry(self, temp_path: Path, path: Path) -> None:
        attempts = len(_REPLACE_RETRY_DELAYS_SECONDS) + 1
        for attempt in range(attempts):
            try:
                temp_path.replace(path)
                return
            except PermissionError:
                if attempt == attempts - 1:
                    raise
                time.sleep(_REPLACE_RETRY_DELAYS_SECONDS[attempt])

    def get(self, object_id: str) -> ModelT:
        path = self._path_for(object_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self.model_type.model_validate(payload)

    def list_all(self) -> list[ModelT]:
        items: list[ModelT] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items.append(self.model_type.model_validate(payload))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return items
