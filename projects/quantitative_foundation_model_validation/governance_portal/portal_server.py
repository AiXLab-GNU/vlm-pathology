#!/usr/bin/env python3
"""Loopback-only web portal for P0 evidence review and approval."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from .governance import (
        EVIDENCE_FILES,
        FM1_OUTPUT_DIR,
        FM1_OUTPUTS,
        MAIN_STUDY_OUTPUTS,
        PREEXPERIMENT,
        RECORDS_DIR,
        GovernanceError,
        append_approval,
        append_fm4_scope_approval,
        finalize_fm4_scope,
        finalize_g8,
        portal_data,
    )
except ImportError:  # Direct script execution.
    from governance import (
        EVIDENCE_FILES,
        FM1_OUTPUT_DIR,
        FM1_OUTPUTS,
        MAIN_STUDY_OUTPUTS,
        PREEXPERIMENT,
        RECORDS_DIR,
        GovernanceError,
        append_approval,
        append_fm4_scope_approval,
        finalize_fm4_scope,
        finalize_g8,
        portal_data,
    )


WEB_ROOT = Path(__file__).resolve().parent / "web"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[SimpleHTTPRequestHandler]):
        super().__init__(address, handler)
        self.csrf_token = secrets.token_urlsafe(32)
        self.m9_process: subprocess.Popen[str] | None = None


class PortalHandler(SimpleHTTPRequestHandler):
    server: PortalServer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[portal] %s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GovernanceError("잘못된 요청 크기입니다.") from exc
        if length <= 0 or length > 64 * 1024:
            raise GovernanceError("요청 본문 크기가 허용 범위를 벗어났습니다.")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GovernanceError("유효한 JSON 요청이 아닙니다.") from exc
        if not isinstance(value, dict):
            raise GovernanceError("JSON object가 필요합니다.")
        return value

    def _require_csrf(self) -> None:
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            raise GovernanceError("세션 검증 토큰이 없거나 만료되었습니다. 페이지를 새로고침하십시오.")

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/status":
            try:
                payload = portal_data()
                payload["csrf_token"] = self.server.csrf_token
                if self.server.m9_process is not None:
                    payload["m9_launcher"] = {
                        "running": self.server.m9_process.poll() is None,
                        "returncode": self.server.m9_process.poll(),
                    }
                self._json(payload)
            except (GovernanceError, OSError, ValueError, KeyError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        prefix = "/api/evidence/"
        if route.startswith(prefix):
            name = unquote(route[len(prefix):])
            if name not in EVIDENCE_FILES:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = PREEXPERIMENT / name
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            content_type = "application/json" if path.suffix == ".json" else "text/plain"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        fm1_prefix = "/api/fm1/"
        if route.startswith(fm1_prefix):
            name = unquote(route[len(fm1_prefix):])
            if name not in FM1_OUTPUTS:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = FM1_OUTPUT_DIR / name
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            content_type = "application/json" if path.suffix == ".json" else "text/plain"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        study_prefix = "/api/main-study/"
        if route.startswith(study_prefix):
            parts = route[len(study_prefix):].split("/", 1)
            if len(parts) != 2 or parts[0] not in MAIN_STUDY_OUTPUTS:
                self.send_error(HTTPStatus.NOT_FOUND); return
            stage, name = parts[0], unquote(parts[1])
            directory, allowed = MAIN_STUDY_OUTPUTS[stage]
            if name not in allowed or not (directory / name).is_file():
                self.send_error(HTTPStatus.NOT_FOUND); return
            body = (directory / name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ("application/json" if name.endswith(".json") else "text/plain") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(body); return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            self._require_csrf()
            route = urlparse(self.path).path
            payload = self._body_json()
            if route == "/api/approval":
                record = append_approval(payload)
                self._json({"ok": True, "record": record}, HTTPStatus.CREATED)
                return
            if route == "/api/finalize-g8":
                if payload.get("confirmation") != "FINALIZE G8":
                    raise GovernanceError("확정 문구 FINALIZE G8이 필요합니다.")
                manifest = finalize_g8()
                self._json({"ok": True, "manifest": manifest}, HTTPStatus.CREATED)
                return
            if route == "/api/fm4-scope-approval":
                record = append_fm4_scope_approval(payload)
                self._json({"ok": True, "record": record}, HTTPStatus.CREATED)
                return
            if route == "/api/finalize-fm4-scope":
                if payload.get("confirmation") != "APPROVE FM4":
                    raise GovernanceError("확정 문구 APPROVE FM4가 필요합니다.")
                manifest = finalize_fm4_scope()
                self._json({"ok": True, "manifest": manifest}, HTTPStatus.CREATED)
                return
            if route == "/api/run-m9":
                if payload.get("confirmation") != "RUN FULL CLEAN RERUN":
                    raise GovernanceError("실행 문구 RUN FULL CLEAN RERUN이 필요합니다.")
                if self.server.m9_process is not None and self.server.m9_process.poll() is None:
                    raise GovernanceError("P0-M9 clean rerun이 이미 실행 중입니다.")
                if not (RECORDS_DIR / "g8_approval_manifest.json").is_file():
                    raise GovernanceError("P0-G8 최종 확정이 먼저 필요합니다.")
                RECORDS_DIR.mkdir(parents=True, exist_ok=True)
                log = (RECORDS_DIR / "m9_launcher.log").open("a", encoding="utf-8")
                self.server.m9_process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve().parent / "governance.py"), "run-m9"],
                    cwd=str(PREEXPERIMENT.parents[2]), stdout=log, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True,
                )
                log.close()
                self._json({"ok": True, "pid": self.server.m9_process.pid}, HTTPStatus.ACCEPTED)
                return
            self._json({"error": "알 수 없는 API 경로입니다."}, HTTPStatus.NOT_FOUND)
        except GovernanceError as exc:
            self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except (OSError, ValueError, KeyError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P0 governance portal (SSH tunnel only)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.host not in ALLOWED_HOSTS:
        raise SystemExit("보안을 위해 127.0.0.1/localhost/::1 binding만 허용합니다.")
    server = PortalServer((args.host, args.port), PortalHandler)
    print(f"P0 governance portal: http://{args.host}:{args.port}", flush=True)
    print("Remote access requires an SSH local-forward; no firewall change is needed.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
