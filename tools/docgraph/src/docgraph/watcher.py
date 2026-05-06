"""File watcher with debounced reindex.

Each FileWatcher is bound to a single corpus. The MCP server spawns one
watcher per configured corpus, each scoped to its own docs_root, each
reindexing only its own rows.

Watches a docs_root directory for *.md changes (create/modify/delete/move)
and triggers a per-corpus reindex via `index()` after a debounce window. Also
runs a periodic full rescan as a safety net for missed filesystem events
(common on WSL inotify).

Each reindex opens its own SQLite connection, safe under WAL mode.

Public surface:
    FileWatcher(db_path, docs_root, *, corpus="default",
                debounce_seconds=0.3, rescan_seconds=300.0)
        .start() / .stop()        or use as a context manager
        .reindex_count            observable counter
"""

import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from docgraph.db import connect
from docgraph.indexer import index


class _MarkdownHandler(FileSystemEventHandler):
    def __init__(self, on_event):
        self._on_event = on_event

    @staticmethod
    def _is_md(event: FileSystemEvent) -> bool:
        if event.is_directory:
            return False
        return str(event.src_path).endswith(".md")

    def on_created(self, event):
        if self._is_md(event):
            self._on_event()

    def on_modified(self, event):
        if self._is_md(event):
            self._on_event()

    def on_deleted(self, event):
        if self._is_md(event):
            self._on_event()

    def on_moved(self, event):
        # Renames cross the .md boundary in both directions: foo.md -> bar.txt
        # (src is markdown) and foo.txt -> bar.md (dest is markdown). We need
        # to reindex either way, so check both paths.
        if event.is_directory:
            return
        src_md = str(event.src_path).endswith(".md")
        dest_md = str(getattr(event, "dest_path", "")).endswith(".md")
        if src_md or dest_md:
            self._on_event()


class FileWatcher:
    def __init__(
        self,
        db_path: Path | str,
        docs_root: Path | str,
        *,
        corpus: str = "default",
        task_domains: dict[str, str] | None = None,
        debounce_seconds: float = 0.3,
        rescan_seconds: float = 300.0,
    ):
        self.db_path = Path(db_path)
        self.docs_root = Path(docs_root)
        self.corpus = corpus
        self.task_domains = task_domains or {}
        self.debounce_seconds = debounce_seconds
        self.rescan_seconds = rescan_seconds

        self._observer: Observer | None = None
        self._debounce_timer: threading.Timer | None = None
        self._rescan_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._reindex_count = 0

    @property
    def reindex_count(self) -> int:
        return self._reindex_count

    def start(self) -> None:
        if self._observer is not None:
            return
        self._stopped.clear()
        handler = _MarkdownHandler(self._trigger)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.docs_root), recursive=True)
        self._observer.start()
        self._schedule_rescan()

    def stop(self) -> None:
        self._stopped.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            if self._rescan_timer is not None:
                self._rescan_timer.cancel()
                self._rescan_timer = None

    def __enter__(self) -> "FileWatcher":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _trigger(self) -> None:
        """Called from watchdog event thread on any *.md change.

        Resets the debounce timer, the most-recent event wins, callback
        fires `debounce_seconds` after the *last* event in a burst.
        """
        if self._stopped.is_set():
            return
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            timer = threading.Timer(self.debounce_seconds, self._do_reindex)
            timer.daemon = True
            self._debounce_timer = timer
        timer.start()

    def _do_reindex(self) -> None:
        if self._stopped.is_set():
            return
        with self._lock:
            self._debounce_timer = None
        conn = connect(self.db_path)
        try:
            index(
                conn,
                self.docs_root,
                corpus=self.corpus,
                task_domains=self.task_domains,
            )
            with self._lock:
                self._reindex_count += 1
        finally:
            conn.close()

    def _schedule_rescan(self) -> None:
        if self._stopped.is_set():
            return
        timer = threading.Timer(self.rescan_seconds, self._on_rescan)
        timer.daemon = True
        self._rescan_timer = timer
        timer.start()

    def _on_rescan(self) -> None:
        if self._stopped.is_set():
            return
        self._do_reindex()
        self._schedule_rescan()
