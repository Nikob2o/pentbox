"""Chemins et configuration (norme XDG).

Squelette du lot 0 : on fige uniquement les emplacements. Le chargement d'une
config (format à décider — TOML via stdlib pour éviter le souci de wheel PyYAML
sur Python 3.14) arrive au lot 2/5.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "pentbox"


def _xdg(env: str, default: Path) -> Path:
    value = os.environ.get(env)
    return Path(value) if value else default


CONFIG_DIR: Path = _xdg("XDG_CONFIG_HOME", Path.home() / ".config") / APP_NAME
DATA_DIR: Path = _xdg("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_NAME

# Données runtime (créées à la demande par le lot 1+).
WORKSPACES_DIR: Path = DATA_DIR / "workspaces"       # un dossier par mission
RESOURCES_DIR: Path = DATA_DIR / "resources"         # bibliothèque partagée (ro)
MY_RESOURCES_DIR: Path = DATA_DIR / "my-resources"   # espace perso partagé (rw)
