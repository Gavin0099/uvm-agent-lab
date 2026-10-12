"""Caller-owned deployment paths, never historical experiment defaults."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat

ASSETS = {"/": ("index.html", "text/html"),
          "/index.html": ("index.html", "text/html"),
          "/styles.css": ("styles.css", "text/css"),
          "/app.js": ("app.js", "text/javascript"),
          "/saved-cases.js": ("saved-cases.js", "text/javascript")}


@dataclass(frozen=True)
class WebPaths:
    """The host supplies reviewed assets and the existing ledger explicitly.

    No raw corpus, credentials, evidence jobs or saved answers are packaged.
    Assets are trusted executable UI code; this class does not review them.
    """
    ledger: Path
    assets: Path

    def __post_init__(self):
        object.__setattr__(self, "ledger", Path(self.ledger).resolve())
        object.__setattr__(self, "assets", Path(self.assets).resolve())
        for name, _kind in set(ASSETS.values()):
            path = self.assets / name
            if not path.is_file() or path.is_symlink():
                raise ValueError("Reviewed web assets must be regular files.")
        if self.ledger == self.assets or self.assets in self.ledger.parents or self.ledger in self.assets.parents:
            raise ValueError("Web assets and private ledger must be separate.")


def read_secret(path):
    """Existing external relay secret-file ownership/mode boundary."""
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("Secret file must be an owned regular file with mode 0600.")
    return path.read_text(encoding="utf-8").strip()
