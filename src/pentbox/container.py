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

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

from pentbox import config

# Ordre d'affichage des tags dans le catalogue (nommés d'abord, puis datés).
_TAG_PRIORITY = {"latest": 0, "core": 1, "full": 2}

IMAGE_FLAVORS = ("kali", "blackarch")

# Dockerfiles par saveur. La *référence d'image* effective est calculée par
# resolve_image() : image publiée sur un registre si registry.namespace est
# configuré, sinon tag local construit via --build.
FLAVOR_DOCKERFILE = {
    "kali": "kali.dockerfile",
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
LABEL_COMMENT = "pentbox.comment"

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
    """Référence d'image effective pour une saveur.

    Si un registre est configuré (registry.namespace non vide), on vise l'image
    publiée « <namespace>/pentbox-<flavor>:<tag> » (pull possible) ; sinon le tag
    local « pentbox-<flavor>:local » (construit via `install --build`).
    """
    if flavor not in FLAVOR_DOCKERFILE:
        raise PentboxError(
            f"saveur inconnue « {flavor} » (dispo : {', '.join(FLAVOR_DOCKERFILE)})."
        )
    reg = config.load_config().get("registry", {})
    namespace = str(reg.get("namespace") or "").strip()
    if namespace:
        tag = str(reg.get("tag") or "latest").strip()
        return f"{namespace}/pentbox-{flavor}:{tag}"
    return f"pentbox-{flavor}:local"


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


def _parse_env(env: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in env or []:
        if "=" not in item:
            raise PentboxError(f"variable d'env invalide « {item} » (attendu KEY=VALEUR).")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def _parse_ports(ports: list[str]) -> dict[str, int]:
    """« HOST:CONTAINER[/proto] » → format docker-py {'CONTAINER/proto': HOST}."""
    mapping: dict[str, int] = {}
    for spec in ports:
        if ":" not in spec:
            raise PentboxError(f"port invalide « {spec} » (attendu HOST:CONTAINER[/proto]).")
        host_part, cont_part = spec.rsplit(":", 1)
        proto = "tcp"
        if "/" in cont_part:
            cont_part, proto = cont_part.split("/", 1)
        try:
            mapping[f"{int(cont_part)}/{proto}"] = int(host_part)
        except ValueError:
            raise PentboxError(f"port invalide « {spec} » (numéros attendus).")
    return mapping


def _docker_reason(exc: Exception) -> str:
    """Extrait un message lisible d'une erreur docker-py (sans le bruit HTTP)."""
    return str(getattr(exc, "explanation", None) or exc)


def _host_timezone() -> str | None:
    """Devine la timezone de l'host (TZ, /etc/timezone, ou lien /etc/localtime)."""
    tz = os.environ.get("TZ")
    if tz:
        return tz
    etc_tz = Path("/etc/timezone")
    if etc_tz.exists():
        content = etc_tz.read_text(encoding="utf-8").strip()
        if content:
            return content
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        target = os.readlink(localtime)
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    return None


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
            f"image « {image} » introuvable dans le registre — publie-la via la CI "
            f"(push GitHub) ou construis-la en local : pentbox install {flavor} --build"
        )
    except APIError as exc:
        raise PentboxError(f"échec du pull de « {image} » : {exc}") from exc
    return image


def build_image(flavor: str) -> str:
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
    tag = resolve_image(flavor)  # même réf que create/pull (local ou registre)
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "-t", tag,
        "--build-arg", f"HOST_UID={os.getuid()}",
        "--build-arg", f"HOST_GID={os.getgid()}",
        str(PROJECT_ROOT),
    ]
    if subprocess.call(cmd) != 0:
        raise PentboxError("le build a échoué (voir la sortie docker ci-dessus).")
    return tag


# --------------------------------------------------------------------------- #
# Catalogue d'images (Docker Hub + état local)
# --------------------------------------------------------------------------- #

def _hub_tags(repo: str) -> list[dict] | None:
    """Tags publiés d'un repo Docker Hub public. None si injoignable/inexistant."""
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/?page_size=100"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 (host fixe)
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return [] if exc.code == 404 else None  # 404 = repo pas encore publié
    except (urllib.error.URLError, OSError, ValueError):
        return None
    tags = [
        {
            "name": r.get("name", "?"),
            "pushed": (r.get("last_updated") or "")[:10],
            "size": r.get("full_size") or 0,
        }
        for r in data.get("results", [])
    ]
    named = sorted(
        (t for t in tags if t["name"] in _TAG_PRIORITY),
        key=lambda t: _TAG_PRIORITY[t["name"]],
    )
    dated = sorted(
        (t for t in tags if t["name"] not in _TAG_PRIORITY),
        key=lambda t: t["name"],
        reverse=True,
    )
    return named + dated


def _local_image(client, ref: str) -> dict | None:
    """Infos de l'image locale (version téléchargée) ou None si absente."""
    try:
        img = client.images.get(ref)
    except (ImageNotFound, NotFound):
        return None
    return {
        "created": (img.attrs.get("Created") or "")[:10],
        "id": img.short_id.replace("sha256:", ""),
    }


def list_images() -> dict:
    """Catalogue : tags Docker Hub (si registre configuré) + présence locale.

    Retourne {namespace, flavors:[{flavor, repo, hub_ok, rows:[{tag, pushed,
    size, local}]}]}. `local` est None si l'image n'est pas pull, sinon
    {created, id} (= la version téléchargée).
    """
    client = _client()
    namespace = str(config.load_config().get("registry", {}).get("namespace") or "").strip()
    flavors = []
    for flavor in FLAVOR_DOCKERFILE:
        if namespace:
            repo = f"{namespace}/pentbox-{flavor}"
            hub = _hub_tags(repo)
        else:
            repo = f"pentbox-{flavor}"
            hub = None

        rows = []
        if hub:
            for t in hub:
                rows.append({
                    "tag": t["name"],
                    "pushed": t["pushed"],
                    "size": t["size"],
                    "local": _local_image(client, f"{repo}:{t['name']}"),
                })
        else:
            # Pas de registre (ou injoignable) : on montre ce qui est en local.
            candidates = (
                [f"{repo}:latest", f"{repo}:core", f"{repo}:full"]
                if namespace else [f"{repo}:local"]
            )
            for ref in candidates:
                loc = _local_image(client, ref)
                if loc:
                    rows.append({
                        "tag": ref.rsplit(":", 1)[1],
                        "pushed": None,
                        "size": None,
                        "local": loc,
                    })
        flavors.append({"flavor": flavor, "repo": repo, "hub_ok": hub is not None, "rows": rows})
    return {"namespace": namespace, "flavors": flavors}


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

def create_mission(
    mission: str,
    flavor: str,
    *,
    start: bool = True,
    comment: str | None = None,
    env: list[str] | None = None,
    ports: list[str] | None = None,
    devices: list[str] | None = None,
    network: str = "host",
    x11: bool = False,
) -> str:
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

    if ports and network == "host":
        raise PentboxError(
            "publier des ports est inutile en réseau host (tous les ports sont déjà "
            "partagés) — ajoute `--network bridge`."
        )

    for dev in devices or []:
        host_dev = dev.split(":", 1)[0]
        if not Path(host_dev).exists():
            raise PentboxError(f"device introuvable sur l'host : {host_dev}")

    workspace = config.WORKSPACES_DIR / mission
    workspace.mkdir(parents=True, exist_ok=True)
    ensure_shared_dirs()

    labels = {
        LABEL_MISSION: mission,
        LABEL_FLAVOR: flavor,
        LABEL_CREATED: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if comment:
        labels[LABEL_COMMENT] = comment

    volumes = {
        str(workspace): {"bind": WORKSPACE_MOUNT, "mode": "rw"},
        str(config.MY_RESOURCES_DIR): {"bind": MY_RESOURCES_MOUNT, "mode": "rw"},
        str(config.RESOURCES_DIR): {"bind": RESOURCES_MOUNT, "mode": "ro"},
    }
    environment = _parse_env(env)

    # Timezone du host, partagée par défaut.
    tz = _host_timezone()
    if tz:
        environment.setdefault("TZ", tz)
    if Path("/etc/localtime").exists():
        volumes["/etc/localtime"] = {"bind": "/etc/localtime", "mode": "ro"}

    # Partage X11 (GUI) optionnel.
    if x11:
        volumes["/tmp/.X11-unix"] = {"bind": "/tmp/.X11-unix", "mode": "rw"}
        environment.setdefault("DISPLAY", os.environ.get("DISPLAY", ":0"))
        xauth = os.environ.get("XAUTHORITY")
        if xauth and Path(xauth).exists():
            volumes[xauth] = {"bind": xauth, "mode": "ro"}
            environment.setdefault("XAUTHORITY", xauth)

    create_kwargs = dict(
        command=["sleep", "infinity"],  # garde le conteneur vivant pour `exec`
        name=name,
        labels=labels,
        volumes=volumes,
        environment=environment,
        network_mode=network,  # host (défaut, pentest) ou bridge (ports isolés)
        tty=True,
        stdin_open=True,
        detach=True,
    )
    if devices:
        create_kwargs["devices"] = devices
    if ports:
        create_kwargs["ports"] = _parse_ports(ports)

    container = client.containers.create(image, **create_kwargs)
    if start:
        try:
            container.start()
        except DockerException as exc:
            # Rollback : ne pas laisser de conteneur fantôme si le start échoue.
            try:
                container.remove(force=True)
            except DockerException:
                pass
            raise PentboxError(f"démarrage impossible : {_docker_reason(exc)}") from exc
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
                "comment": c.labels.get(LABEL_COMMENT, ""),
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
        "comment": container.labels.get(LABEL_COMMENT, ""),
        "container": container.name,
    }


def exec_mission(mission: str, command: str = "", *, log: bool = True) -> int:
    """Ouvre un shell (ou lance une commande) dans le conteneur.

    Délégué à `docker exec` (le SDK gère mal l'interactif). Le shell interactif
    passe par `pentbox-shell` dans l'image (choix du shell + logging asciinema
    piloté par PENTBOX_LOG) ; en repli — conteneur sans le script, ex. image
    antérieure au lot 5 — on ouvre un shell simple. Retourne le code de sortie.
    """
    container = _get_container(_client(), mission)
    if container.status != "running":
        raise PentboxError(
            f"mission « {mission} » arrêtée — `pentbox start {mission}` d'abord."
        )

    name = container_name(mission)
    interactive = "-it" if sys.stdin.isatty() else "-i"

    if command:
        return subprocess.call(
            ["docker", "exec", "-w", WORKSPACE_MOUNT, interactive, name, "sh", "-c", command]
        )

    term = os.environ.get("TERM", "xterm-256color")
    code = subprocess.call([
        "docker", "exec", "-w", WORKSPACE_MOUNT,
        "-e", f"TERM={term}",
        "-e", f"PENTBOX_LOG={'1' if log else '0'}",
        interactive, name, "pentbox-shell",
    ])
    if code == 127:  # pentbox-shell absent (conteneur d'avant le lot 5) → repli
        code = subprocess.call(
            ["docker", "exec", "-w", WORKSPACE_MOUNT, interactive, name, "sh", "-c", _SHELL_PICKER]
        )
    return code


# --------------------------------------------------------------------------- #
# Enregistrements de session (asciinema)
# --------------------------------------------------------------------------- #

def list_logs(mission: str) -> list[Path]:
    """Enregistrements .cast d'une mission (côté host), du plus ancien au récent."""
    logdir = config.WORKSPACES_DIR / mission / "logs"
    if not logdir.exists():
        return []
    return sorted(logdir.glob("*.cast"))


def play_log(mission: str, cast: str | None = None) -> int:
    """Rejoue un enregistrement via l'asciinema du conteneur (dernier par défaut)."""
    logs = list_logs(mission)
    if not logs:
        raise PentboxError(f"aucun enregistrement pour la mission « {mission} ».")
    if cast is None:
        target = logs[-1]
    else:
        target = next((c for c in logs if c.name == cast), None)
        if target is None:
            raise PentboxError(f"enregistrement « {cast} » introuvable pour « {mission} ».")

    container = _get_container(_client(), mission)
    if container.status != "running":
        raise PentboxError(
            f"mission « {mission} » arrêtée — `pentbox start {mission}` d'abord."
        )
    return subprocess.call([
        "docker", "exec", "-it", container_name(mission),
        "asciinema", "play", f"{WORKSPACE_MOUNT}/logs/{target.name}",
    ])
