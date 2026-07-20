"""Point d'entrée CLI (Typer).

Lot 1 : le cycle de vie est branché sur la couche métier `container`. La CLI
reste mince — elle parse, appelle, et présente les erreurs proprement.

Règle d'architecture (wrapper agnostique) : aucune commande ne hardcode de nom
d'outil — on manipule des conteneurs et des tags, jamais le contenu de l'image.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

import typer
from docker.errors import DockerException
from rich.console import Console
from rich.table import Table

from pentbox import __version__, config, container

app = typer.Typer(
    name="pentbox",
    help="Environnement de hacking conteneurisé, façon Exegol — maison, sans paywall.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pentbox {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Affiche la version et quitte.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """pentbox — pilote des conteneurs de pentest (bases Debian / BlackArch)."""


@contextmanager
def _errors():
    """Transforme une PentboxError en sortie propre (rouge + code 1)."""
    try:
        yield
    except container.PentboxError as exc:
        console.print(f"[bold red]✗[/] {exc}")
        raise typer.Exit(code=1)
    except DockerException as exc:
        # Filet de sécurité : aucune erreur Docker ne doit produire de traceback.
        console.print(f"[bold red]✗[/] erreur Docker : {exc}")
        raise typer.Exit(code=1)


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #

@app.command()
def install(
    image: str = typer.Argument("kali", help="Saveur d'image : kali | blackarch."),
    build: bool = typer.Option(False, "--build", help="Builder l'image en local."),
) -> None:
    """Récupère (pull) ou build une image pentbox."""
    with _errors():
        if build:
            console.print(
                f"[cyan]Build de l'image « {image} »…[/] cela peut être long "
                "(arsenal apt + pipx)."
            )
            ref = container.build_image(image)
            console.print(f"[green]✓[/] image construite : [bold]{ref}[/]")
        elif not config.registry_namespace():
            raise container.PentboxError(
                "aucun registre configuré — construis l'image en local :\n"
                f"    pentbox install {image} --build\n"
                "  ou renseigne [registry].namespace (ton user Docker Hub) dans la config\n"
                "  une fois l'image publiée par la CI (voir `pentbox config`)."
            )
        else:
            with console.status(f"Récupération de l'image « {image} »…"):
                ref = container.pull_image(image)
            console.print(f"[green]✓[/] image récupérée : [bold]{ref}[/]")


@app.command()
def update(
    image: str = typer.Argument("kali", help="Saveur d'image à mettre à jour."),
) -> None:
    """Récupère la dernière version de l'image (pull)."""
    with _errors():
        if not config.registry_namespace():
            raise container.PentboxError(
                "aucun registre configuré — rien à mettre à jour depuis un registre.\n"
                f"  build local : pentbox install {image} --build"
            )
        with console.status(f"Mise à jour de l'image « {image} »…"):
            ref = container.pull_image(image)
    console.print(f"[green]✓[/] image à jour : [bold]{ref}[/]")


# --------------------------------------------------------------------------- #
# Cycle de vie
# --------------------------------------------------------------------------- #

@app.command()
def create(
    mission: str = typer.Argument(..., help="Nom de la mission / du conteneur."),
    image: Optional[str] = typer.Option(
        None, "--image", "-i", help="Saveur d'image (défaut : config)."
    ),
    comment: str = typer.Option("", "--comment", "-c", help="Annotation libre de la mission."),
    env: Optional[list[str]] = typer.Option(
        None, "--env", "-e", help="Variable d'env KEY=VAL (répétable)."
    ),
    port: Optional[list[str]] = typer.Option(
        None, "--port", "-p", help="Publier un port HOST:CONTAINER, proto optionnel (réseau bridge)."
    ),
    device: Optional[list[str]] = typer.Option(
        None, "--device", help="Passthrough matériel /dev/… (répétable)."
    ),
    network: str = typer.Option("host", "--network", help="host (défaut) | bridge."),
    x11: bool = typer.Option(False, "--x11", help="Partage l'affichage X11 (apps GUI)."),
    no_start: bool = typer.Option(False, "--no-start", help="Créer sans démarrer."),
) -> None:
    """Crée un conteneur pour une mission, avec son workspace persistant."""
    resolved_image = image or config.load_config()["defaults"]["image"]
    with _errors():
        workspace = container.create_mission(
            mission,
            resolved_image,
            start=not no_start,
            comment=comment or None,
            env=env,
            ports=port,
            devices=device,
            network=network,
            x11=x11,
        )
    console.print(f"[green]✓[/] mission [bold]{mission}[/] créée (workspace : {workspace})")
    if not no_start:
        console.print(f"  → shell : [bold]pentbox exec {mission}[/]")


@app.command()
def start(mission: str = typer.Argument(..., help="Mission à démarrer.")) -> None:
    """Démarre le conteneur d'une mission."""
    with _errors():
        container.start_mission(mission)
    console.print(f"[green]✓[/] mission [bold]{mission}[/] démarrée")


@app.command()
def stop(mission: str = typer.Argument(..., help="Mission à arrêter.")) -> None:
    """Arrête le conteneur d'une mission."""
    with _errors():
        container.stop_mission(mission)
    console.print(f"[green]✓[/] mission [bold]{mission}[/] arrêtée")


@app.command("exec")
def run_exec(
    mission: str = typer.Argument(..., help="Mission cible."),
    command: str = typer.Argument("", help="Commande à exécuter (défaut : shell interactif)."),
    log: Optional[bool] = typer.Option(
        None, "--log/--no-log", help="Enregistrer la session en asciinema (défaut : config)."
    ),
) -> None:
    """Ouvre un shell (ou lance une commande) dans le conteneur d'une mission."""
    do_log = config.load_config()["logging"]["enabled"] if log is None else log
    with _errors():
        code = container.exec_mission(mission, command, log=do_log)
    raise typer.Exit(code=code)


@app.command()
def logs(
    mission: str = typer.Argument(..., help="Mission dont on veut les enregistrements."),
    play: bool = typer.Option(False, "--play", help="Rejouer le dernier enregistrement."),
) -> None:
    """Liste (ou rejoue avec --play) les sessions asciinema d'une mission."""
    if play:
        with _errors():
            code = container.play_log(mission)
        raise typer.Exit(code=code)
    with _errors():
        recs = container.list_logs(mission)
    if not recs:
        console.print(f"[dim]aucun enregistrement pour « {mission} ».[/]")
        return
    table = Table("ENREGISTREMENT", "TAILLE", title=f"Sessions — {mission}")
    for r in recs:
        table.add_row(r.name, f"{r.stat().st_size} o")
    console.print(table)
    console.print(f"[dim]rejouer le dernier : pentbox logs {mission} --play[/]")


def _show_missions() -> None:
    """Affiche la table des missions (ou un message s'il n'y en a aucune)."""
    with _errors():
        rows = container.list_missions()
    if not rows:
        console.print("[dim]aucune mission — `pentbox create <nom>` pour commencer.[/]")
        return
    table = Table(title="Missions pentbox")
    for col in ("MISSION", "SAVEUR", "ÉTAT", "IMAGE", "CRÉÉE", "COMMENT"):
        table.add_column(col)
    for r in rows:
        color = "green" if r["status"] == "running" else "yellow"
        table.add_row(
            r["mission"],
            r["flavor"],
            f"[{color}]{r['status']}[/]",
            r["image"],
            r["created"],
            r["comment"] or "[dim]-[/]",
        )
    console.print(table)


@app.command("list")
def list_missions() -> None:
    """Liste les missions / conteneurs pentbox."""
    _show_missions()


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def _show_images() -> None:
    """Catalogue : images Docker Hub + état local (vert si déjà pull, avec version)."""
    with _errors():
        data = container.list_images()
    ns = data["namespace"]
    title = (
        f"Images pentbox — namespace : {ns}"
        if ns else "Images pentbox — local (aucun registre configuré)"
    )
    table = Table("SAVEUR", "TAG", "PUSH (Docker Hub)", "TAILLE", "LOCAL (version)", title=title)
    for fl in data["flavors"]:
        if not fl["rows"]:
            note = "aucune image publiée" if fl["hub_ok"] else "registre injoignable / non publié"
            table.add_row(fl["flavor"], f"[dim]{note}[/]", "", "", "")
            continue
        first = True
        for r in fl["rows"]:
            local = r["local"]
            tag = f"[green]{r['tag']}[/]" if local else r["tag"]
            pushed = r["pushed"] or "[dim]—[/]"
            size = _human_size(r["size"]) if r["size"] else "[dim]—[/]"
            local_cell = (
                f"[green]✓ {local['created']} ({local['id']})[/]" if local else "[dim]—[/]"
            )
            table.add_row(fl["flavor"] if first else "", tag, pushed, size, local_cell)
            first = False
    console.print(table)
    if not ns:
        console.print("[dim]Renseigne [registry].namespace pour voir les images Docker Hub.[/]")


@app.command()
def info(
    mission: Optional[str] = typer.Argument(
        None, help="Mission à inspecter (vide = catalogue des images)."
    ),
) -> None:
    """Détaille une mission — ou, sans argument, un récap images + missions."""
    if mission is None:
        _show_images()
        console.print()
        _show_missions()
        return
    with _errors():
        data = container.mission_info(mission)
    table = Table(show_header=False, title=f"Mission « {mission} »")
    for key in (
        "mission", "flavor", "status", "image", "network",
        "workspace", "my_resources", "resources", "comment", "created", "container",
    ):
        table.add_row(f"[bold]{key}[/]", str(data[key]))
    console.print(table)


@app.command()
def resources() -> None:
    """Affiche (et crée) les dossiers partagés my-resources et resources."""
    with _errors():
        paths = container.ensure_shared_dirs()
    console.print("Dossiers partagés, montés dans [bold]chaque[/] mission :")
    console.print(
        f"  [bold]my-resources[/] (rw, {container.MY_RESOURCES_MOUNT}) : {paths['my_resources']}"
    )
    console.print(
        f"  [bold]resources[/]    (ro, {container.RESOURCES_MOUNT}) : {paths['resources']}"
    )


@app.command("config")
def show_config() -> None:
    """Affiche (et crée au besoin) la configuration pentbox."""
    with _errors():
        path = config.ensure_config()
        cfg = config.load_config()
    console.print(f"Config : [bold]{path}[/]")
    table = Table("SECTION", "CLÉ", "VALEUR")
    for section, values in cfg.items():
        for key, value in values.items():
            table.add_row(section, key, str(value))
    console.print(table)


@app.command()
def rm(
    mission: str = typer.Argument(..., help="Mission à supprimer."),
    force: bool = typer.Option(False, "--force", "-f", help="Forcer même si en cours."),
) -> None:
    """Supprime le conteneur d'une mission (le workspace est conservé)."""
    with _errors():
        workspace = container.remove_mission(mission, force=force)
    console.print(f"[green]✓[/] mission [bold]{mission}[/] supprimée")
    console.print(f"  [dim]workspace conservé : {workspace}[/]")


if __name__ == "__main__":  # pragma: no cover
    app()
