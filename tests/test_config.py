"""Tests de la config (chemins XDG + chargement TOML)."""
from __future__ import annotations

import pytest

from pentbox import config


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Redirige CONFIG_DIR / CONFIG_FILE vers un dossier temporaire."""
    cfg_dir = tmp_path / "pentbox"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.toml")
    return cfg_dir


def _write(cfg_dir, content):
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(content, encoding="utf-8")


def test_load_config_defaults_when_absent(tmp_config):
    cfg = config.load_config()
    assert cfg["defaults"]["image"] == "kali"
    assert cfg["logging"]["enabled"] is True
    # Défaut = namespace officiel → pull des images publiées sans config.
    assert cfg["registry"]["namespace"] == config.DEFAULT_NAMESPACE


def test_load_config_can_clear_namespace(tmp_config):
    _write(tmp_config, '[registry]\nnamespace = ""\n')
    assert config.load_config()["registry"]["namespace"] == ""


def test_load_config_user_overrides(tmp_config):
    _write(tmp_config, '[defaults]\nimage = "blackarch"\n[registry]\nnamespace = "nocoblas"\n')
    cfg = config.load_config()
    assert cfg["defaults"]["image"] == "blackarch"
    assert cfg["registry"]["namespace"] == "nocoblas"
    # Clé non fournie dans la section → défaut conservé (merge, pas remplacement).
    assert cfg["registry"]["tag"] == "latest"
    # Section non touchée → défaut.
    assert cfg["logging"]["enabled"] is True


def test_load_config_malformed_falls_back(tmp_config):
    _write(tmp_config, "ceci n'est pas du = toml [valide")
    cfg = config.load_config()  # ne doit jamais lever
    assert cfg["defaults"]["image"] == "kali"


def test_ensure_config_creates_then_preserves(tmp_config):
    assert not config.CONFIG_FILE.exists()
    assert config.ensure_config() == config.CONFIG_FILE
    assert config.CONFIG_FILE.exists()
    # Un 2e appel ne doit PAS écraser un fichier existant.
    config.CONFIG_FILE.write_text("# perso\n", encoding="utf-8")
    config.ensure_config()
    assert config.CONFIG_FILE.read_text(encoding="utf-8") == "# perso\n"


def test_registry_namespace_default_and_strip(tmp_config):
    # Sans config → namespace officiel par défaut.
    assert config.registry_namespace() == config.DEFAULT_NAMESPACE
    # Override + espaces superflus retirés.
    _write(tmp_config, '[registry]\nnamespace = "  monorga  "\n')
    assert config.registry_namespace() == "monorga"
