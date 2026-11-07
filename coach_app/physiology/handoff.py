"""Deterministic, offline file handoff for Coach manual event drafts.

Not an authenticated network transport. Only a caller-chosen outbox is written;
nothing is sent to Mother or to a notification service.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

ENVELOPE_VERSION = "1.0.0"
ENCODING = "base64"
CONTENT_TYPE = "application/vnd.coach.manual-event+json"
MAX_EVENT_BYTES = 256 * 1024
MAX_ENVELOPE_BYTES = 400 * 1024


class HandoffError(ValueError):
    """A proposed handoff cannot be represented or safely retained."""


def pack_manual_event(event: dict) -> bytes:
    """Serialize one event and wrap its exact submitted bytes with a digest."""
    if not isinstance(event, dict):
        raise HandoffError("Manual event must be an object")
    if (
        event.get("schema_version") != "1.0.0"
        or event.get("record_type") != "event"
        or event.get("source") != "coach:manual"
        or event.get("processing_version") != "coach-manual-events/0.1.0"
    ):
        raise HandoffError("Not a compatible Coach manual event draft")
    try:
        original = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HandoffError("Event is not finite JSON") from exc
    if not original or len(original) > MAX_EVENT_BYTES:
        raise HandoffError("Event exceeds bounded size")
    envelope = {
        "envelope_version": ENVELOPE_VERSION,
        "content_type": CONTENT_TYPE,
        "encoding": ENCODING,
        "event_sha256": hashlib.sha256(original).hexdigest(),
        "event_base64": base64.b64encode(original).decode("ascii"),
    }
    result = (
        json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(result) > MAX_ENVELOPE_BYTES:
        raise HandoffError("Envelope exceeds bounded size")
    return result


def save_to_outbox(directory: str | Path, envelope: bytes) -> Path:
    """Atomically publish a private, content-addressed file without overwrite.

    Uses POSIX hard-link publication to prevent replacing an existing file.
    The outbox is a user-selected local filesystem directory, not a network
    queue. The caller copies files using its own separately authorized route.
    """
    if type(envelope) is not bytes or not envelope:
        raise HandoffError("Envelope must be nonempty bytes")
    if len(envelope) > MAX_ENVELOPE_BYTES:
        raise HandoffError("Envelope exceeds bounded size")
    folder = Path(directory)
    if folder.is_symlink():
        raise HandoffError("A symlinked outbox is not supported")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not folder.is_dir() or folder.is_symlink():
        raise HandoffError("Outbox must be a directory")
    name = hashlib.sha256(envelope).hexdigest() + ".coach-event.json"
    destination = folder / name

    fd, temporary = tempfile.mkstemp(prefix=".coach-pending-", dir=folder)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(envelope)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError:
            info = destination.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_mode & 0o077
            ):
                raise HandoffError("Destination is not a private regular file")
            if destination.read_bytes() != envelope:
                raise HandoffError("Existing envelope bytes do not match")
        if os.name == "posix":
            directory_fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination
