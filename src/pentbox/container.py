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

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

from pentbox import config

IMAGE_FLAVORS = ("debian", "blackarch")

# Nos images custom (lot 2). Tags locaux tant qu'aucun registre n'est configuré ;
# le lot 6 les repointera vers Docker Hub (ex. docker.io/<user>/pentbox-debian)
# sans que le reste du code ne bouge.
FLAVOR_IMAGES = {
    "debian": "pentbox-debian:local",
    "blackarch": "pentbox-blackarch:local",
}
FLAVOR_DOCKERFILE = {
    "debian": "debian.dockerfile",
    "blackarch": "blackarch.dockerfile",
}

# Racine du repo (contexte de build, pour COPY assets/). Fonctionne en install
# éditable ; le build est une activité dev/CI, l'utilisateur final fait un pull.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGES_DIR = PROJECT_ROOT / "images"

CONTAINER_PREFIX = "pentbox-"
LABEL_MISSION = "pentbox.mission"
LABEL_FLAVOR = "pentbox.flavor"
LABEL_CREATED = "pentbox.created"

WORKSPACE_MOUNT = "/workspace"          # propre à la mission (rw)
MY_RESOURCES_MOUNT = "/opt/my-resources"  # partagé entre missions (rw)
RESOURCES_MOUNT = "/opt/resources"        # bibliothèque partagée (ro)

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
    try:
        client.images.pull(repo, tag=tag)
    except (ImageNotFound, NotFound):
        raise PentboxError(
            f"image « {image} » introuvable dans un registre — pas encore publiée "
            "(le pull arrivera au lot 6).\n"
            f"    construis-la en local : pentbox install {flavor} --build"
        )
    except APIError as exc:
        raise PentboxError(f"échec du pull de « {image} » : {exc}") from exc
    return image


def build_image(flavor: str, profile: str = "core") -> str:
    """Build l'image custom depuis images/<flavor>.dockerfile. Retourne le tag.

    Délégué à `docker build` (streaming + BuildKit). Contexte = racine du repo
    (pour COPY assets/). Les UID/GID de l'host sont injectés pour que les
    fichiers du workspace n'appartiennent pas à root. Réservé au dev/CI.
    """
    if flavor not in FLAVOR_DOCKERFILE:
        raise PentboxError(
            f"saveur inconnue « {flavor} » (dispo : {', '.join(FLAVOR_DOCKERFILE)})."
        )
    dockerfile = IMAGES_DIR / FLAVOR_DOCKERFILE[flavor]
    if not dockerfile.exists():
        raise PentboxError(f"Dockerfile absent : {dockerfile} (saveur pas encore prête ?).")
    tag = FLAVOR_IMAGES[flavor]
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "-t", tag,
        "--build-arg", f"PROFILE={profile}",
        "--build-arg", f"HOST_UID={os.getuid()}",
        "--build-arg", f"HOST_GID={os.getgid()}",
        str(PROJECT_ROOT),
    ]
    if subprocess.call(cmd) != 0:
        raise PentboxError("le build a échoué (voir la sortie docker ci-dessus).")
    return tag


# --------------------------------------------------------------------------- #
# Ressources partagées (montées dans TOUTES les missions)
# --------------------------------------------------------------------------- #

_SHARED_READMES = {
    "my_resources": (
        config.MY_RESOURCES_DIR,
        "# my-resources\n\n"
        "Ton espace **personnel**, partagé entre **toutes** les missions pentbox "
        f"et monté en lecture/écriture sur `{MY_RESOURCES_MOUNT}` dans chaque "
        "conteneur.\n\n"
        "Mets-y tes scripts, configs, notes, outils perso : ils persistent et "
        "sont dispo partout.\n",
    ),
    "resources": (
        config.RESOURCES_DIR,
        "# resources\n\n"
        "Bibliothèque **partagée en lecture seule**, montée sur "
        f"`{RESOURCES_MOUNT}` dans chaque conteneur.\n\n"
        "Mets-y tes wordlists, binaires et payloads communs. Lecture seule côté "
        "conteneur pour protéger la biblio ; édite-la depuis l'host.\n",
    ),
}


def ensure_shared_dirs() -> dict[str, str]:
    """Crée les dossiers partagés (+ un README au 1er passage). Retourne leurs chemins."""
    paths: dict[str, str] = {}
    for key, (path, readme) in _SHARED_READMES.items():
        path.mkdir(parents=True, exist_ok=True)
        marker = path / "README.md"
        if not marker.exists():
            marker.write_text(readme, encoding="utf-8")
        paths[key] = str(path)
    return paths


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
    ensure_shared_dirs()

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
        volumes={
            str(workspace): {"bind": WORKSPACE_MOUNT, "mode": "rw"},
            str(config.MY_RESOURCES_DIR): {"bind": MY_RESOURCES_MOUNT, "mode": "rw"},
            str(config.RESOURCES_DIR): {"bind": RESOURCES_MOUNT, "mode": "ro"},
        },
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
        "my_resources": mounts.get(MY_RESOURCES_MOUNT, "?"),
        "resources": mounts.get(RESOURCES_MOUNT, "?"),
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
