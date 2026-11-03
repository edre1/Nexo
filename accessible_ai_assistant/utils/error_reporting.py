"""Sanitized error outbox and optional SMTP delivery. Never include exception messages."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
import logging
from pathlib import Path
import platform
import re
import smtplib
import sqlite3
import ssl
import sys
import threading
import time
import traceback

from config.paths import DATA_ROOT, RESOURCE_ROOT


def token(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:100]


def protect(password):
    import win32crypt
    return base64.b64encode(win32crypt.CryptProtectData(password.encode(), "Nexo reportes", None, None, None, 1)).decode()


def unprotect(value):
    import win32crypt
    return win32crypt.CryptUnprotectData(base64.b64decode(value), None, None, None, 1)[1].decode()


class ErrorReporter:
    def __init__(self, root=DATA_ROOT, clock=time.time):
        self.root = Path(root)
        self.folder = self.root / "error_reports"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.database = self.folder / "errors.sqlite3"
        self.settings_path = self.root / "error_reporting.json"
        self.clock = clock
        self.stop = threading.Event()
        self.send_lock = threading.Lock()
        self.thread = None
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, first_at REAL, last_at REAL, count INTEGER, sent_count INTEGER, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def capture(self, exc=None, tb=None, stage="error", event="error"):
        now = self.clock()
        frames = []
        if exc is not None:
            tb = tb or exc.__traceback__
        if tb:
            for frame in traceback.extract_tb(tb)[-12:]:
                frames.append({"file": token(Path(frame.filename).name), "function": token(frame.name), "line": frame.lineno})
        try:
            version = json.loads((RESOURCE_ROOT / "config" / "release.json").read_text(encoding="utf-8"))["version"]
        except Exception:
            version = "unknown"
        payload = {
            "schema": 1, "app": "Nexo", "version": token(version), "installed": bool(getattr(sys, "frozen", False)),
            "windows": platform.release(), "python": platform.python_version(),
            "stage": token(stage), "event": token(event), "exception": token(type(exc).__name__) if exc else "ApplicationError", "frames": frames,
        }
        status = getattr(exc, "status_code", None)
        if type(status) is int:
            payload["http_status"] = status
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code in {"invalid_api_key", "insufficient_quota", "rate_limit_exceeded", "model_not_found"}:
            payload["api_code"] = code
        causes = []
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        for _ in range(3):
            if cause is None:
                break
            causes.append(token(type(cause).__name__))
            cause = cause.__cause__ or cause.__context__
        if causes:
            payload["causes"] = causes
        if type(exc).__name__ == "ValidationError":
            try:
                fields = {"spoken_response", "type", "action", "parameters", "application", "name", "text", "key"}
                payload["validation"] = [{"fields": [part for part in e["loc"] if isinstance(part, str) and part in fields], "type": token(e["type"])} for e in exc.errors(include_input=False, include_context=False, include_url=False)[:5]]
            except Exception:
                pass
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        identity = f"{signature[:24]}-{int(now // 600)}"
        with self.connect() as db:
            db.execute("INSERT INTO reports VALUES (?, ?, ?, 1, 0, ?) ON CONFLICT(id) DO UPDATE SET count=count+1, last_at=excluded.last_at", (identity, now, now, json.dumps(payload)))
            db.execute("DELETE FROM reports WHERE count=sent_count AND last_at < ?", (now - 90 * 86400,))
        return identity

    def settings(self):
        settings = {"enabled": False, "host": "smtp.gmail.com", "port": 587, "sender": "", "recipient": "", "password_protected": ""}
        if self.settings_path.exists():
            saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
            settings.update({key: saved[key] for key in settings if key in saved})
        return settings

    def save_settings(self, settings, password=""):
        current = self.settings()
        data = {key: settings.get(key, current[key]) for key in current}
        for field in ("host", "sender", "recipient"):
            if not isinstance(data[field], str) or any(c in data[field] for c in "\r\n"):
                raise ValueError("Los datos del correo no son válidos.")
            data[field] = data[field].strip()
        data["port"] = int(data["port"])
        if data["port"] not in {465, 587}:
            raise ValueError("Usa el puerto seguro 465 o 587.")
        if password:
            data["password_protected"] = protect(password.replace(" ", "") if data["host"] == "smtp.gmail.com" else password)
        if data["enabled"]:
            self.validate_settings(data)
        temp = self.settings_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.settings_path)

    @staticmethod
    def validate_settings(settings):
        if not settings["host"] or not all(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", settings[k]) for k in ("sender", "recipient")):
            raise ValueError("Indica el remitente y el destinatario completos.")
        if not settings.get("password_protected"):
            raise ValueError("Agrega la contraseña de aplicación del correo en este equipo.")

    def reports(self, pending_only=False):
        with self.connect() as db:
            rows = db.execute("SELECT id, first_at, last_at, count, sent_count, payload FROM reports " + ("WHERE count > sent_count " if pending_only else "") + "ORDER BY first_at").fetchall()
        return [{"id": r[0], "first_at": datetime.fromtimestamp(r[1], timezone.utc).isoformat(), "last_at": datetime.fromtimestamp(r[2], timezone.utc).isoformat(), "occurrences": r[3], "sent_occurrences": r[4], "diagnostic": json.loads(r[5])} for r in rows]

    def _metadata(self, key, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", (key, str(value)))
                return value
            row = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
            return row[0] if row else ""

    def _send(self, settings, reports, test=False):
        self.validate_settings(settings)
        password = unprotect(settings["password_protected"])
        message = EmailMessage()
        message["From"], message["To"] = settings["sender"], settings["recipient"]
        message["Subject"] = "[Nexo] Prueba de reportes" if test else f"[Nexo] Reporte de errores ({len(reports)} grupos)"
        digest = hashlib.sha256(json.dumps(reports, sort_keys=True).encode()).hexdigest()[:32]
        message["Message-ID"] = f"<{digest}@nexo.local>"
        message.set_content("Reporte técnico de Nexo. No contiene conversaciones, audio, capturas ni claves.\n\n" + json.dumps(reports, ensure_ascii=False, indent=2))
        context = ssl.create_default_context()
        if settings["port"] == 465:
            server = smtplib.SMTP_SSL(settings["host"], 465, timeout=15, context=context)
        else:
            server = smtplib.SMTP(settings["host"], 587, timeout=15)
        with server:
            if settings["port"] == 587:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            server.login(settings["sender"], password)
            server.send_message(message)

    def send_pending(self, force=False):
        with self.send_lock:
            settings = self.settings()
            if not settings["enabled"] and not force:
                return 0
            last = float(self._metadata("last_sent") or 0)
            if not force and ((last and self.clock() - last < 3600) or self.clock() < float(self._metadata("retry_after") or 0)):
                return 0
            reports = self.reports(pending_only=True)[:20]
            if not reports:
                return 0
            try:
                self._send(settings, reports)
            except Exception:
                failures = int(self._metadata("failures") or 0) + 1
                self._metadata("failures", failures)
                self._metadata("retry_after", self.clock() + min(3600, 30 * 2 ** min(failures, 7)))
                raise
            with self.connect() as db:
                for report in reports:
                    db.execute("UPDATE reports SET sent_count=? WHERE id=?", (report["occurrences"], report["id"]))
            self._metadata("last_sent", self.clock())
            self._metadata("failures", 0)
            self._metadata("retry_after", 0)
            self._metadata("delivery_status", "Último envío completado.")
            return len(reports)

    def send_test(self):
        self._send(self.settings(), [{"test": True, "app": "Nexo", "message": "Configuración de reportes correcta."}], test=True)

    def retry_soon(self):
        self._metadata("retry_after", 0)

    def start(self):
        if self.thread:
            return
        def worker():
            while not self.stop.wait(30):
                try:
                    self.send_pending()
                except Exception as exc:
                    # Never log failures of the reporting transport into its own outbox.
                    try:
                        self._metadata("delivery_status", "Envío pendiente: " + token(type(exc).__name__))
                    except Exception:
                        pass
        self.thread = threading.Thread(target=worker, daemon=True, name="ErrorReports")
        self.thread.start()

    def close(self):
        self.stop.set()


class ErrorReportHandler(logging.Handler):
    def __init__(self, reporter):
        super().__init__(logging.WARNING)
        self.reporter = reporter

    def emit(self, record):
        if record.levelno < logging.ERROR and not record.exc_info:
            return
        try:
            exc = record.exc_info[1] if record.exc_info else None
            self.reporter.capture(exc, record.exc_info[2] if record.exc_info else None, stage=record.funcName, event=record.msg if isinstance(record.msg, str) and re.fullmatch(r"[a-z_]{1,64}", record.msg) else "handled_error")
        except Exception:
            pass


_reporter = None


def get_reporter():
    global _reporter
    if _reporter is None:
        _reporter = ErrorReporter()
    return _reporter


def install_exception_hooks():
    try:
        reporter = get_reporter()
    except Exception:
        # Diagnostics must not prevent the application from starting.
        return None
    def capture(exc, tb, stage):
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            return
        try:
            reporter.capture(exc, tb, stage=stage, event="unhandled_exception")
        except Exception:
            pass
    sys.excepthook = lambda kind, exc, tb: (capture(exc, tb, "main_thread"), sys.__excepthook__(kind, exc, tb))
    threading.excepthook = lambda args: capture(args.exc_value, args.exc_traceback, "background_thread")
    reporter.start()
    return reporter
