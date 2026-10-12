"""Atomic records for a single process owner; file and directory are synced."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from gv100h.spec_qa.source_binding.strict_json import strict_object


def read(path):
    return strict_object(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_directory(path):
    """Create a private leaf or reject an unsafe existing directory, unchanged."""
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Ledger directory must be owned and mode 0700; existing permissions are not changed.")
    return path


def open_private(path, mode):
    """Exclusive record creation or appendable lock, owned regular mode 0600."""
    flags = {"xb": os.O_WRONLY | os.O_CREAT | os.O_EXCL,
             "a+": os.O_RDWR | os.O_CREAT | os.O_APPEND}[mode]
    descriptor = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("Record must be owned and mode 0600; existing permissions are not changed.")
        return os.fdopen(descriptor, mode)
    except BaseException:
        os.close(descriptor)
        raise


def persist(path, value):
    path = Path(path)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    descriptor, name = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    temporary = Path(name)  # mkstemp always uses 0600, independent of umask.
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
