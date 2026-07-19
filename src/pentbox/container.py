"""Pilotage des conteneurs via le Docker SDK Python.

Couche métier du wrapper (lot 1). On passe par le SDK pour tout ce qui gagne à
une gestion d'erreurs propre (pull / create / start / stop / rm / list / inspect).

Seule exception : le **shell interactif** (`exec`), où le SDK gère mal le TTY —
on délègue alors à `docker exec -it`, qui rend la main au terminal proprement.

Wrapper agnostique : rien ici ne connaît le *contenu* d'une image. On ne
manipule que des conteneurs, des tags et des mounts. Docker (labels) est la
seule source de vérité sur l'état des missions — pas de fichier d'état parallèle.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from pentbox import config

IMAGE_FLAVORS = ("debian", "blackarch")

# Lot 1 : on pointe sur des images standard pour pouvoir tester le wrapper tout
# de suite. Lot 2 : repointer vers nos images custom
# (ex. docker.io/<user>/pentbox-debian). Le reste du code ne bouge pas.
FLAVOR_IMAGES = {
    "debian": "debian:12-slim",
    "blackarch": "blackarchlinux/blackarch:latest",
}

CONTAINER_PREFIX = "pentbox-"
LABEL_MISSION = "pentbox.mission"
LABEL_FLAVOR = "pentbox.flavor"
LABEL_CREATED = "pentbox.created"

WORKSPACE_MOUNT = "/workspace"

# Choisit le meilleur shell dispo dans l'image (zsh quand on l'ajoutera, sinon
# bash, sinon sh) — garde `exec` fonctionnel quelle que soit la base.
_SHELL_PICKER = (
    "if command -v zsh >/dev/null 2>&1; then exec zsh; "
    "elif command -v bash >/dev/null 2>&1; then exec bash; "
    "else exec sh; fi"
)


class PentboxError(Exception):
    """Erreur métier, présentée proprement à l'utilisateur (pas de traceback)."""


# --------------------------------------------------------------------------- #
# Client & helpers
# --------------------------------------------------------------------------- #

def _client() -> "docker.DockerClient":
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as exc:
        raise PentboxError(
            "impossible de joindre le démon Docker. Il est peut-être arrêté :\n"
            "    sudo systemctl start docker\n"
            f"  (détail : {exc})"
        ) from exc


def container_name(mission: str) -> str:
    return f"{CONTAINER_PREFIX}{mission}"


def resolve_image(flavor: str) -> str:
    if flavor not in FLAVOR_IMAGES:
        raise PentboxError(
            f"saveur inconnue « {flavor} » (dispo : {', '.join(FLAVOR_IMAGES)})."
        )
    return FLAVOR_IMAGES[flavor]


def _split_ref(ref: str) -> tuple[str, str]:
    """Sépare « repo:tag » proprement (gère les repos avec slash)."""
    if ":" in ref.rsplit("/", 1)[-1]:
        repo, tag = ref.rsplit(":", 1)
        return repo, tag
    return ref, "latest"


def _get_container(client, mission: str):
    try:
        return client.containers.get(container_name(mission))
    except NotFound:
        raise PentboxError(
            f"mission « {mission} » introuvable — `pentbox create {mission}` d'abord ?"
        )


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #

def pull_image(flavor: str) -> str:
    """Récupère l'image d'une saveur (bloquant). Retourne la référence tirée."""
    client = _client()
    image = resolve_image(flavor)
    repo, tag = _split_ref(image)
    client.images.pull(repo, tag=tag)
    return image


# --------------------------------------------------------------------------- #
# Cycle de vie
# --------------------------------------------------------------------------- #

def create_mission(mission: str, flavor: str, *, start: bool = True) -> str:
    """Crée (et démarre) le conteneur d'une mission avec son workspace persistant."""
    client = _client()
    name = container_name(mission)

    try:
        client.containers.get(name)
        raise PentboxError(f"la mission « {mission} » existe déjà.")
    except NotFound:
        pass

    image = resolve_image(flavor)
    try:
        client.images.get(image)
    except ImageNotFound:
        raise PentboxError(
            f"image « {image} » absente — lance d'abord `pentbox install {flavor}`."
        )

    workspace = config.WORKSPACES_DIR / mission
    workspace.mkdir(parents=True, exist_ok=True)

    labels = {
        LABEL_MISSION: mission,
        LABEL_FLAVOR: flavor,
        LABEL_CREATED: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    container = client.containers.create(
        image,
        command=["sleep", "infinity"],  # garde le conteneur vivant pour `exec`
        name=name,
        labels=labels,
        volumes={str(workspace): {"bind": WORKSPACE_MOUNT, "mode": "rw"}},
        network_mode="host",  # indispensable pour le pentest (scans, Responder…)
        tty=True,
        stdin_open=True,
        detach=True,
    )
    if start:
        container.start()
    return str(workspace)


def start_mission(mission: str) -> None:
    _get_container(_client(), mission).start()


def stop_mission(mission: str) -> None:
    _get_container(_client(), mission).stop()


def remove_mission(mission: str, *, force: bool = False) -> str:
    """Supprime le conteneur. Le workspace (données host) est CONSERVÉ."""
    container = _get_container(_client(), mission)
    container.remove(force=force)
    return str(config.WORKSPACES_DIR / mission)


def list_missions() -> list[dict]:
    client = _client()
    containers = client.containers.list(all=True, filters={"label": LABEL_MISSION})
    rows = []
    for c in containers:
        rows.append(
            {
                "mission": c.labels.get(LABEL_MISSION, "?"),
                "flavor": c.labels.get(LABEL_FLAVOR, "?"),
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "created": c.labels.get(LABEL_CREATED, "?"),
            }
        )
    rows.sort(key=lambda r: r["mission"])
    return rows


def mission_info(mission: str) -> dict:
    container = _get_container(_client(), mission)
    mounts = {
        m.get("Destination"): m.get("Source") for m in container.attrs.get("Mounts", [])
    }
    net = container.attrs.get("HostConfig", {}).get("NetworkMode", "?")
    return {
        "mission": container.labels.get(LABEL_MISSION, mission),
        "flavor": container.labels.get(LABEL_FLAVOR, "?"),
        "status": container.status,
        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
        "created": container.labels.get(LABEL_CREATED, "?"),
        "network": net,
        "workspace": mounts.get(WORKSPACE_MOUNT, "?"),
        "container": container.name,
    }


def exec_mission(mission: str, command: str = "") -> int:
    """Ouvre un shell (ou lance une commande) dans le conteneur.

    Délégué à `docker exec` : le SDK gère mal l'interactif. Retourne le code de
    sortie de la commande.
    """
    container = _get_container(_client(), mission)
    if container.status != "running":
        raise PentboxError(
            f"mission « {mission} » arrêtée — `pentbox start {mission}` d'abord."
        )

    docker_cmd = ["docker", "exec", "-w", WORKSPACE_MOUNT]
    docker_cmd.append("-it" if sys.stdin.isatty() else "-i")
    docker_cmd.append(container_name(mission))
    if command:
        docker_cmd += ["sh", "-c", command]
    else:
        docker_cmd += ["sh", "-c", _SHELL_PICKER]
    return subprocess.call(docker_cmd)
