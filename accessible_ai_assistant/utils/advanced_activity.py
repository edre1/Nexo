"""Local activity journal and recoverable copies for known file changes."""
from datetime import datetime
from hashlib import file_digest
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from config.paths import DATA_ROOT


ACTIVITY_ROOT = DATA_ROOT / "advanced_activity"
BACKUP_LIMIT = 20 * 1024 * 1024


class AdvancedActivity:
    def __init__(self, root=ACTIVITY_ROOT):
        self.root = root
        self.session = uuid4().hex

    def record(self, event, **details):
        self.root.mkdir(parents=True, exist_ok=True)
        record = {"time": datetime.now().astimezone().isoformat(timespec="seconds"), "session": self.session, "event": event, **details}
        with (self.root / "actividad.txt").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def file_state(self, path: Path, *, backup=False):
        if not path.exists():
            return {"path": str(path), "exists": False}
        if not path.is_file():
            return {"path": str(path), "type": "directory_or_special"}
        stat = path.stat()
        state = {"path": str(path), "size": stat.st_size, "modified_ns": stat.st_mtime_ns}
        if stat.st_size <= BACKUP_LIMIT:
            with path.open("rb") as stream:
                state["sha256"] = file_digest(stream, "sha256").hexdigest()
            if backup:
                destination = self.root / "copias" / f"{uuid4().hex}{path.suffix}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                state["backup"] = str(destination)
        elif backup:
            state["backup_omitted"] = "file_over_20_mib"
        return state
