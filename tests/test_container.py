"""Tests des helpers purs de container.py (sans démon Docker)."""
from __future__ import annotations

import socket

import pytest
from docker.errors import DockerException

from pentbox import config, container
from pentbox.container import PentboxError


# --- container_name --------------------------------------------------------
def test_container_name():
    assert container.container_name("htb") == "pentbox-htb"


# --- _parse_env ------------------------------------------------------------
def test_parse_env_ok():
    assert container._parse_env(["A=1", "B=x=y"]) == {"A": "1", "B": "x=y"}


def test_parse_env_none():
    assert container._parse_env(None) == {}


def test_parse_env_invalid():
    with pytest.raises(PentboxError):
        container._parse_env(["SANS_EGAL"])


# --- _parse_ports ----------------------------------------------------------
def test_parse_ports_ok():
    assert container._parse_ports(["8080:80"]) == {"80/tcp": 8080}


def test_parse_ports_proto():
    assert container._parse_ports(["53:53/udp"]) == {"53/udp": 53}


def test_parse_ports_no_colon():
    with pytest.raises(PentboxError):
        container._parse_ports(["8080"])


def test_parse_ports_non_numeric():
    with pytest.raises(PentboxError):
        container._parse_ports(["abc:def"])


# --- resolve_image ---------------------------------------------------------
@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


def test_resolve_image_published_by_default(tmp_config):
    # Sans config, le namespace par défaut vise l'image publiée sur Docker Hub.
    assert container.resolve_image("kali") == f"{config.DEFAULT_NAMESPACE}/pentbox-kali:latest"


def test_resolve_image_custom_namespace(tmp_config):
    (tmp_config / "config.toml").write_text(
        '[registry]\nnamespace = "monorga"\ntag = "latest"\n', encoding="utf-8"
    )
    assert container.resolve_image("blackarch") == "monorga/pentbox-blackarch:latest"


def test_resolve_image_local_when_namespace_empty(tmp_config):
    (tmp_config / "config.toml").write_text('[registry]\nnamespace = ""\n', encoding="utf-8")
    assert container.resolve_image("kali") == "pentbox-kali:local"


def test_resolve_image_unknown_flavor(tmp_config):
    with pytest.raises(PentboxError):
        container.resolve_image("windows")


# --- _docker_reason --------------------------------------------------------
def test_docker_reason_uses_explanation():
    exc = DockerException("bruit http")
    exc.explanation = "raison claire"
    assert container._docker_reason(exc) == "raison claire"


def test_docker_reason_fallback_str():
    assert container._docker_reason(ValueError("boom")) == "boom"


# --- free_desktop_port -----------------------------------------------------
def _raise_docker():
    raise DockerException("pas de docker")


class _FakeContainer:
    def __init__(self, port):
        self.labels = {container.LABEL_DESKTOP: str(port)}


def _fake_client(containers):
    containers_obj = type("C", (), {"list": lambda self, *a, **k: containers})()
    return type("Cl", (), {"containers": containers_obj})()


def test_free_desktop_port_skips_occupied(monkeypatch):
    # Sans Docker joignable → l'ensemble réservé reste vide (branche except).
    monkeypatch.setattr(container, "_client", _raise_docker)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))          # port libre attribué par l'OS
        s.listen(1)
        occupied = s.getsockname()[1]
        got = container.free_desktop_port(occupied)
    assert got != occupied
    assert got > occupied


def test_free_desktop_port_skips_reserved_label(monkeypatch):
    # Un port libre côté OS mais réservé par le label d'une autre mission desktop.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        target = s.getsockname()[1]        # relâché à la fermeture du with
    monkeypatch.setattr(container, "_client", lambda: _fake_client([_FakeContainer(target)]))
    got = container.free_desktop_port(target)
    assert got != target
