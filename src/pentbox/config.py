"""Chemins et configuration (norme XDG).

Chemins figés + chargement de la config TOML (lot 5). On utilise `tomllib`
(stdlib depuis 3.11) plutôt que PyYAML pour éviter tout souci de wheel sur
Python 3.14.
"""

from __future__ import annotations

import os
import tomllib
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

CONFIG_FILE: Path = CONFIG_DIR / "config.toml"

# Namespace Docker Hub officiel des images pentbox (défaut → pull sans config).
# Vide-le dans config.toml pour builder en local, ou remplace-le par le tien.
DEFAULT_NAMESPACE = "nocoblas"

# Valeurs par défaut, surchargées par le fichier config.toml s'il existe.
_DEFAULT_CONFIG: dict = {
    "defaults": {"image": "kali"},
    "logging": {"enabled": True},
    "registry": {"namespace": DEFAULT_NAMESPACE, "tag": "latest"},
}

_DEFAULT_CONFIG_TOML = f"""\
# Configuration pentbox.

[defaults]
image = "kali"        # saveur par défaut pour `create` (kali | blackarch)

[logging]
enabled = true        # enregistrer les shells interactifs en asciinema (.cast)

[registry]
namespace = "{DEFAULT_NAMESPACE}"  # user/orga Docker Hub des images ; vide = build local uniquement
tag = "latest"        # tag à récupérer
"""


def load_config() -> dict:
    """Config effective : défauts surchargés par ~/.config/pentbox/config.toml.

    Une config illisible/malformée retombe silencieusement sur les défauts
    (l'outil ne doit jamais casser à cause du fichier de config).
    """
    cfg = {section: dict(values) for section, values in _DEFAULT_CONFIG.items()}
    if not CONFIG_FILE.exists():
        return cfg
    try:
        with CONFIG_FILE.open("rb") as fh:
            user = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    for section, values in user.items():
        if isinstance(values, dict):
            cfg.setdefault(section, {}).update(values)
        else:
            cfg[section] = values
    return cfg


def ensure_config() -> Path:
    """Crée le fichier de config par défaut s'il n'existe pas. Retourne son chemin."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(_DEFAULT_CONFIG_TOML, encoding="utf-8")
    return CONFIG_FILE


def registry_namespace() -> str:
    """User/orga Docker Hub configuré (vide si mode build local uniquement)."""
    return str(load_config().get("registry", {}).get("namespace") or "").strip()
