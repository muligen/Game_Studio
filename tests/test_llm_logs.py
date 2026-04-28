from __future__ import annotations

import json
from pathlib import Path

from studio.runtime.llm_logs import LlmRunLogger


def test_llm_logger_persists_optional_langfuse_metadata(tmp_path: Path) -> None:
    logger = LlmRunLogger(tmp_path)

    logger.append(
        run_id="run-1",
        node_name="worker",
        prompt="prompt",
        context={"safe": True},
        reply={"ok": True},
        metadata={
            "langfuse_trace_id": "trace-1",
            "langfuse_observation_id": "obs-1",
            "langfuse_url": "https://langfuse.example/project/traces/trace-1",
        },
    )

    entries = json.loads((tmp_path / "run-1.json").read_text(encoding="utf-8"))

    assert entries[0]["metadata"]["langfuse_trace_id"] == "trace-1"
    assert entries[0]["metadata"]["langfuse_observation_id"] == "obs-1"
    assert entries[0]["metadata"]["langfuse_url"].endswith("/trace-1")
