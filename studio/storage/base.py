from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")


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
        if not _SAFE_ID_PATTERN.match(object_id):
            raise ValueError(f"object_id contains unsafe characters: {object_id!r}")
        return object_id

    def _path_for(self, object_id: str) -> Path:
        safe_object_id = self._validate_object_id(object_id)
        return self.root / f"{safe_object_id}.json"

    def save(self, model: ModelT) -> ModelT:
        payload = model.model_dump()
        object_id = self._validate_object_id(str(payload["id"]))
        path = self._path_for(object_id)
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        return model

    def get(self, object_id: str) -> ModelT:
        path = self._path_for(object_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self.model_type.model_validate(payload)

    def list_all(self) -> list[ModelT]:
        items: list[ModelT] = []
        for path in sorted(self.root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(self.model_type.model_validate(payload))
        return items
