"""Langfuse transcript tracer — reads Claude Code JSONL transcripts and
emits traces with spans, generations, and tool observations.

This module was extracted from sam_langfuse_hook.py and refactored to be
called inline by claude_code_hook.py instead of via subprocess delegation.
"""

import json
import os
import socket
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STATE_DIR = Path.home() / ".claude" / "state"
LOG_FILE = STATE_DIR / "langfuse_hook.log"
STATE_FILE = STATE_DIR / "langfuse_state.json"
LOCK_FILE = STATE_DIR / "langfuse_state.lock"

DEBUG = os.environ.get("CC_LANGFUSE_DEBUG", "").lower() == "true"
MAX_CHARS = int(os.environ.get("CC_LANGFUSE_MAX_CHARS", "20000"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _log(level: str, message: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {message}\n")
    except Exception:
        pass


def debug(msg: str) -> None:
    if DEBUG:
        _log("DEBUG", msg)


def info(msg: str) -> None:
    _log("INFO", msg)


def warn(msg: str) -> None:
    _log("WARN", msg)


# ---------------------------------------------------------------------------
# File locking (best-effort)
# ---------------------------------------------------------------------------
class FileLock:
    def __init__(self, path: Path, timeout_s: float = 2.0):
        self.path = path
        self.timeout_s = timeout_s
        self._fh = None

    def __enter__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            import fcntl
            deadline = time.time() + self.timeout_s
            while True:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() > deadline:
                        break
                    time.sleep(0.05)
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            import fcntl
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self._fh.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------
def load_state() -> Dict[str, Any]:
    try:
        if not STATE_FILE.exists():
            return {}
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        debug(f"save_state failed: {e}")


def state_key(session_id: str, transcript_path: str) -> str:
    raw = f"{session_id}::{transcript_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class SessionState:
    offset: int = 0
    buffer: str = ""
    turn_count: int = 0


def load_session_state(global_state: Dict[str, Any], key: str) -> SessionState:
    s = global_state.get(key, {})
    return SessionState(
        offset=int(s.get("offset", 0)),
        buffer=str(s.get("buffer", "")),
        turn_count=int(s.get("turn_count", 0)),
    )


def write_session_state(
    global_state: Dict[str, Any], key: str, ss: SessionState
) -> None:
    global_state[key] = {
        "offset": ss.offset,
        "buffer": ss.buffer,
        "turn_count": ss.turn_count,
        "updated": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Hook payload parsing
# ---------------------------------------------------------------------------
def read_hook_payload(stdin_text: str) -> Dict[str, Any]:
    if not stdin_text.strip():
        return {}
    try:
        return json.loads(stdin_text)
    except Exception:
        return {}


def extract_session_and_transcript(
    payload: Dict[str, Any],
) -> Tuple[Optional[str], Optional[Path]]:
    session_id = (
        payload.get("sessionId")
        or payload.get("session_id")
        or payload.get("session", {}).get("id")
    )

    transcript = (
        payload.get("transcriptPath")
        or payload.get("transcript_path")
        or payload.get("transcript", {}).get("path")
    )

    if transcript:
        try:
            transcript_path = Path(transcript).expanduser().resolve()
        except Exception:
            transcript_path = None
    else:
        transcript_path = None

    return session_id, transcript_path


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------
def get_content(msg: Dict[str, Any]) -> Any:
    if not isinstance(msg, dict):
        return None
    if "message" in msg and isinstance(msg.get("message"), dict):
        return msg["message"].get("content")
    return msg.get("content")


def get_role(msg: Dict[str, Any]) -> Optional[str]:
    t = msg.get("type")
    if t in ("user", "assistant"):
        return t
    m = msg.get("message")
    if isinstance(m, dict):
        r = m.get("role")
        if r in ("user", "assistant"):
            return r
    return None


def is_tool_result(msg: Dict[str, Any]) -> bool:
    role = get_role(msg)
    if role != "user":
        return False
    content = get_content(msg)
    if isinstance(content, list):
        return any(
            isinstance(x, dict) and x.get("type") == "tool_result" for x in content
        )
    return False


def iter_tool_results(content: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_result":
                out.append(x)
    return out


def iter_tool_uses(content: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                out.append(x)
    return out


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                parts.append(x.get("text", ""))
            elif isinstance(x, str):
                parts.append(x)
        return "\n".join([p for p in parts if p])
    return ""


def truncate_text(s: str, max_chars: int = MAX_CHARS) -> Tuple[str, Dict[str, Any]]:
    if s is None:
        return "", {"truncated": False, "orig_len": 0}
    orig_len = len(s)
    if orig_len <= max_chars:
        return s, {"truncated": False, "orig_len": orig_len}
    head = s[:max_chars]
    return head, {
        "truncated": True,
        "orig_len": orig_len,
        "kept_len": len(head),
        "sha256": hashlib.sha256(s.encode("utf-8")).hexdigest(),
    }


def get_model(msg: Dict[str, Any]) -> str:
    m = msg.get("message")
    if isinstance(m, dict):
        return m.get("model") or "claude"
    return "claude"


def get_message_id(msg: Dict[str, Any]) -> Optional[str]:
    m = msg.get("message")
    if isinstance(m, dict):
        mid = m.get("id")
        if isinstance(mid, str) and mid:
            return mid
    return None


def get_usage(msg: Dict[str, Any]) -> Dict[str, int]:
    m = msg.get("message")
    if not isinstance(m, dict):
        return {}
    usage = m.get("usage", {})
    if not usage:
        return {}
    return {
        "input_tokens": usage.get("input_tokens", 0) or 0,
        "output_tokens": usage.get("output_tokens", 0) or 0,
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0) or 0,
    }


def get_timestamp(msg: Dict[str, Any]) -> Optional[str]:
    return msg.get("timestamp")


def parse_iso_timestamp(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.timestamp()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Incremental transcript reader
# ---------------------------------------------------------------------------
def read_new_jsonl(
    transcript_path: Path, ss: SessionState
) -> Tuple[List[Dict[str, Any]], SessionState]:
    if not transcript_path.exists():
        return [], ss

    try:
        with open(transcript_path, "rb") as f:
            f.seek(ss.offset)
            chunk = f.read()
            new_offset = f.tell()
    except Exception as e:
        debug(f"read_new_jsonl failed: {e}")
        return [], ss

    if not chunk:
        return [], ss

    try:
        text = chunk.decode("utf-8", errors="replace")
    except Exception:
        text = chunk.decode(errors="replace")

    combined = ss.buffer + text
    lines = combined.split("\n")
    ss.buffer = lines[-1]
    ss.offset = new_offset

    msgs: List[Dict[str, Any]] = []
    for line in lines[:-1]:
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except Exception:
            continue

    return msgs, ss


# ---------------------------------------------------------------------------
# Turn assembly
# ---------------------------------------------------------------------------
@dataclass
class Turn:
    user_msg: Dict[str, Any]
    assistant_msgs: List[Dict[str, Any]]
    tool_results_by_id: Dict[str, Any]


def build_turns(messages: List[Dict[str, Any]]) -> List[Turn]:
    turns: List[Turn] = []
    current_user: Optional[Dict[str, Any]] = None
    assistant_order: List[str] = []
    assistant_latest: Dict[str, Dict[str, Any]] = {}
    tool_results_by_id: Dict[str, Any] = {}

    def flush_turn():
        nonlocal current_user, assistant_order, assistant_latest, tool_results_by_id
        if current_user is None:
            return
        if not assistant_latest:
            return
        assistants = [
            assistant_latest[mid] for mid in assistant_order if mid in assistant_latest
        ]
        turns.append(
            Turn(
                user_msg=current_user,
                assistant_msgs=assistants,
                tool_results_by_id=dict(tool_results_by_id),
            )
        )

    for msg in messages:
        if is_tool_result(msg):
            for tr in iter_tool_results(get_content(msg)):
                tid = tr.get("tool_use_id")
                if tid:
                    tool_results_by_id[str(tid)] = tr.get("content")
            continue

        role = get_role(msg)
        if role == "user":
            flush_turn()
            current_user = msg
            assistant_order = []
            assistant_latest = {}
            tool_results_by_id = {}
            continue

        if role == "assistant":
            if current_user is None:
                continue
            mid = get_message_id(msg) or f"noid:{len(assistant_order)}"
            if mid not in assistant_latest:
                assistant_order.append(mid)
            assistant_latest[mid] = msg
            continue

    flush_turn()
    return turns


# ---------------------------------------------------------------------------
# Langfuse emission
# ---------------------------------------------------------------------------
def _tool_calls_from_assistants(
    assistant_msgs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for am in assistant_msgs:
        for tu in iter_tool_uses(get_content(am)):
            tid = tu.get("id") or ""
            calls.append(
                {
                    "id": str(tid),
                    "name": tu.get("name") or "unknown",
                    "input": tu.get("input")
                    if isinstance(tu.get("input"), (dict, list, str, int, float, bool))
                    else {},
                }
            )
    return calls


def _emit_turn(
    langfuse,
    session_id: str,
    turn_num: int,
    turn: Turn,
    transcript_path: Path,
    host_meta: Optional[Dict[str, str]] = None,
) -> None:
    from opentelemetry import trace as otel_trace_api
    from langfuse import propagate_attributes
    from langfuse._client.span import LangfuseGeneration, LangfuseSpan, LangfuseTool

    user_text_raw = extract_text(get_content(turn.user_msg))
    user_text, user_text_meta = truncate_text(user_text_raw)

    last_assistant = turn.assistant_msgs[-1]
    assistant_text_raw = extract_text(get_content(last_assistant))
    assistant_text, assistant_text_meta = truncate_text(assistant_text_raw)

    model = get_model(turn.assistant_msgs[0])

    total_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    for am in turn.assistant_msgs:
        usage = get_usage(am)
        for k in total_usage:
            total_usage[k] += usage.get(k, 0)

    user_ts = get_timestamp(turn.user_msg)
    assistant_ts = get_timestamp(last_assistant)
    duration_ms = None
    start_dt = None
    end_dt = None
    user_unix = None
    assistant_unix = None
    start_time_ns = None
    end_time_ns = None

    if user_ts and assistant_ts:
        user_unix = parse_iso_timestamp(user_ts)
        assistant_unix = parse_iso_timestamp(assistant_ts)
        if user_unix and assistant_unix:
            duration_ms = (assistant_unix - user_unix) * 1000
            try:
                start_dt = datetime.fromisoformat(user_ts.replace("Z", "+00:00"))
                start_time_ns = int(start_dt.timestamp() * 1e9)
            except Exception:
                pass
            try:
                end_dt = datetime.fromisoformat(assistant_ts.replace("Z", "+00:00"))
                end_time_ns = int(end_dt.timestamp() * 1e9)
            except Exception:
                pass

    tool_calls = _tool_calls_from_assistants(turn.assistant_msgs)

    for c in tool_calls:
        if c["id"] and c["id"] in turn.tool_results_by_id:
            out_raw = turn.tool_results_by_id[c["id"]]
            out_str = (
                out_raw
                if isinstance(out_raw, str)
                else json.dumps(out_raw, ensure_ascii=False)
            )
            out_trunc, out_meta = truncate_text(out_str)
            c["output"] = out_trunc
            c["output_meta"] = out_meta
        else:
            c["output"] = None

    user_id = os.environ.get("CC_LANGFUSE_USER_ID")

    with propagate_attributes(
        session_id=session_id,
        user_id=user_id,
        trace_name=f"Claude Code - Turn {turn_num}",
        tags=["claude-code"],
        metadata=host_meta or None,
    ):
        tracer = langfuse._otel_tracer

        otel_trace_span = tracer.start_span(
            name=f"Claude Code - Turn {turn_num}",
            start_time=start_time_ns,
        )

        trace_span = LangfuseSpan(
            otel_span=otel_trace_span,
            langfuse_client=langfuse,
            input={"role": "user", "content": user_text},
            metadata={
                "source": "claude-code",
                "session_id": session_id,
                "turn_number": turn_num,
                "transcript_path": str(transcript_path),
                "user_text": user_text_meta,
                **(host_meta or {}),
            },
        )

        with otel_trace_api.use_span(otel_trace_span):
            otel_gen_span = tracer.start_span(
                name="Claude Response",
                start_time=start_time_ns,
            )

            gen_obs = LangfuseGeneration(
                otel_span=otel_gen_span,
                langfuse_client=langfuse,
                input={"role": "user", "content": user_text},
                output={"role": "assistant", "content": assistant_text},
                completion_start_time=start_dt,
                model=model,
                usage_details={
                    "input": total_usage["input_tokens"],
                    "output": total_usage["output_tokens"],
                    "total": total_usage["input_tokens"] + total_usage["output_tokens"],
                },
                metadata={
                    "assistant_text": assistant_text_meta,
                    "tool_count": len(tool_calls),
                    "input_tokens": total_usage["input_tokens"],
                    "output_tokens": total_usage["output_tokens"],
                    "cache_read_tokens": total_usage["cache_read_tokens"],
                    "cache_write_tokens": total_usage["cache_write_tokens"],
                    "duration_ms": duration_ms,
                    "end_time_unix": assistant_unix,
                },
            )
            gen_obs.end(end_time=end_time_ns)

            for tc in tool_calls:
                in_obj = tc["input"]
                if isinstance(in_obj, str):
                    in_obj, in_meta = truncate_text(in_obj)
                else:
                    in_meta = None

                otel_tool_span = tracer.start_span(name=f"Tool: {tc['name']}")
                tool_obs = LangfuseTool(
                    otel_span=otel_tool_span,
                    langfuse_client=langfuse,
                    input=in_obj,
                    output=tc.get("output"),
                    metadata={
                        "tool_name": tc["name"],
                        "tool_id": tc["id"],
                        "input_meta": in_meta,
                        "output_meta": tc.get("output_meta"),
                    },
                )
                tool_obs.end()

        trace_span.update(output={"role": "assistant", "content": assistant_text})
        trace_span.end(end_time=end_time_ns)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def process_transcript(stdin_text: str, environ: Optional[Dict[str, str]] = None) -> str:
    """Main processing function. Called inline by claude_code_hook.py.

    Returns a status message string. Raises no exceptions (fail-open).
    """
    from langfuse import Langfuse

    start = time.time()
    debug("Hook started")

    env = environ or dict(os.environ)
    public_key = env.get("CC_LANGFUSE_PUBLIC_KEY") or env.get("LANGFUSE_PUBLIC_KEY")
    secret_key = env.get("CC_LANGFUSE_SECRET_KEY") or env.get("LANGFUSE_SECRET_KEY")
    host = (
        env.get("CC_LANGFUSE_BASE_URL")
        or env.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    )
    environment = env.get("CC_LANGFUSE_ENVIRONMENT")
    if environment:
        os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", environment)

    if not public_key or not secret_key:
        return "Langfuse credentials missing"

    # Build host metadata
    try:
        import urllib.request
        public_ip = (
            urllib.request.urlopen("https://api.ipify.org", timeout=2)
            .read()
            .decode()
            .strip()
        )
    except Exception:
        public_ip = "unknown"
    host_meta = {
        "host_ip": public_ip,
        "host_name": socket.gethostname(),
        "host_cwd": os.getcwd(),
    }

    payload = read_hook_payload(stdin_text)
    session_id, transcript_path = extract_session_and_transcript(payload)

    if not session_id or not transcript_path:
        debug("Missing session_id or transcript_path from hook payload; exiting.")
        return "Missing session_id or transcript_path"

    if not transcript_path.exists():
        debug(f"Transcript path does not exist: {transcript_path}")
        return "Transcript path does not exist"

    try:
        langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            environment=environment,
        )
    except Exception:
        return "Langfuse client init failed"

    emitted = 0
    turn_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    try:
        with FileLock(LOCK_FILE):
            state = load_state()
            key = state_key(session_id, str(transcript_path))
            ss = load_session_state(state, key)

            msgs, ss = read_new_jsonl(transcript_path, ss)
            if not msgs:
                write_session_state(state, key, ss)
                save_state(state)
                return "No new messages"

            turns = build_turns(msgs)
            if not turns:
                write_session_state(state, key, ss)
                save_state(state)
                return "No complete turns"

            for t in turns:
                emitted += 1
                turn_num = ss.turn_count + emitted
                for am in t.assistant_msgs:
                    usage = get_usage(am)
                    turn_tokens["input"] += usage.get("input_tokens", 0)
                    turn_tokens["output"] += usage.get("output_tokens", 0)
                    turn_tokens["cache_read"] += usage.get("cache_read_tokens", 0)
                    turn_tokens["cache_write"] += usage.get("cache_write_tokens", 0)
                try:
                    _emit_turn(
                        langfuse, session_id, turn_num, t, transcript_path, host_meta
                    )
                except Exception as e:
                    debug(f"emit_turn failed: {e}")

            ss.turn_count += emitted
            write_session_state(state, key, ss)
            save_state(state)

        try:
            langfuse.flush()
        except Exception:
            pass

        dur = time.time() - start
        info(
            f"Processed {emitted} turns in {dur:.2f}s | "
            f"tokens: in={turn_tokens['input']}, out={turn_tokens['output']}, "
            f"cache_r={turn_tokens['cache_read']}, cache_w={turn_tokens['cache_write']} "
            f"(session={session_id[:8]})"
        )
        return f"Processed {emitted} turns"

    except Exception as e:
        debug(f"Unexpected failure: {e}")
        return f"Unexpected failure: {e}"

    finally:
        try:
            langfuse.shutdown()
        except Exception:
            pass
