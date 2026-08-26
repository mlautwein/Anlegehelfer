"""llama.cpp-Server-Adapter: lokaler Subprozess auf 127.0.0.1, GGUF, CPU.

- Kein Modell schreibt jemals Excel-Dateien; der Adapter liefert nur
  schema-validierte Feldvorschlaege an die Fusion.
- Verbindung ausschliesslich Loopback (vertraeglich mit dem Offline-Waechter).
- Modellpfad/Hash kommen aus config.json bzw. packaging/models/manifest.json;
  es findet kein Laufzeit-Download statt.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from lims_assistant.config import LlmConfig
from lims_assistant.llm.base import LlmRowTask, LlmSuggestion, sanitize_suggestion
from lims_assistant.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from lims_assistant.llm.schema import LLM_ROWS_JSON_SCHEMA, LlmRowsOut


class LlamaServerAdapter:
    name = "llama-server"

    def __init__(self, cfg: LlmConfig) -> None:
        self.cfg = cfg
        self._proc: subprocess.Popen | None = None
        self._base = f"http://127.0.0.1:{cfg.port}"

    # ------------------------------------------------------------ Lifecycle

    def available(self) -> tuple[bool, str]:
        if not self.cfg.enabled:
            return False, "LLM in Konfiguration deaktiviert"
        model = Path(self.cfg.model_path) if self.cfg.model_path else None
        if not model or not model.is_file():
            return False, f"GGUF-Modell fehlt: {self.cfg.model_path or '(leer)'}"
        binary = Path(self.cfg.server_binary) if self.cfg.server_binary else None
        if not binary or not binary.is_file():
            return False, f"llama-server-Binary fehlt: {self.cfg.server_binary or '(leer)'}"
        return True, f"{binary.name} + {model.name}"

    def _health_ok(self) -> bool:
        try:
            with urllib.request.urlopen(self._base + "/health", timeout=2) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def start(self) -> bool:
        ok, _ = self.available()
        if not ok:
            return False
        if self._health_ok():
            return True
        if self._proc is None or self._proc.poll() is not None:
            args = [
                self.cfg.server_binary,
                "-m",
                self.cfg.model_path,
                "--host",
                "127.0.0.1",
                "--port",
                str(self.cfg.port),
                "--ctx-size",
                str(self.cfg.ctx_size),
                "--no-webui",
            ]
            if self.cfg.threads > 0:
                args += ["-t", str(self.cfg.threads)]
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        deadline = time.monotonic() + max(30, self.cfg.timeout_s)
        while time.monotonic() < deadline:
            if self._health_ok():
                return True
            if self._proc is not None and self._proc.poll() is not None:
                return False
            time.sleep(0.5)
        return False

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    # ------------------------------------------------------------ Inferenz

    def _chat(self, tasks: list[LlmRowTask], hint_text: str) -> LlmRowsOut | None:
        body = {
            "model": "local",
            "temperature": 0.1,
            "max_tokens": 900,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(tasks, hint_text)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "rows", "strict": True, "schema": LLM_ROWS_JSON_SCHEMA},
            },
        }
        req = urllib.request.Request(
            self._base + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
            return None
        try:
            content = data["choices"][0]["message"]["content"]
            return LlmRowsOut.model_validate(json.loads(content))
        except Exception:  # noqa: BLE001 - jede Schemaverletzung => verwerfen
            return None

    def suggest(self, tasks: list[LlmRowTask], hint_text: str = "") -> list[LlmSuggestion]:
        if not tasks or not self.start():
            return []
        out: list[LlmSuggestion] = []
        chunk = max(1, self.cfg.max_rows_per_call)
        for i in range(0, len(tasks), chunk):
            batch = tasks[i : i + chunk]
            parsed = self._chat(batch, hint_text)
            if parsed is None:
                continue
            valid_refs = {t.row_ref: t for t in batch}
            for row in parsed.rows:
                task = valid_refs.get(row.row_ref)
                if task is None:
                    continue
                fields = sanitize_suggestion(row.field_map())
                fields = {k: v for k, v in fields.items() if k in task.missing_fields}
                if fields:
                    out.append(LlmSuggestion(row_ref=row.row_ref, fields=fields))
        return out
