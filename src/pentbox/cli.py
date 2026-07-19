"""Point d'entrée CLI (Typer).

Lot 1 : le cycle de vie est branché sur la couche métier `container`. La CLI
reste mince — elle parse, appelle, et présente les erreurs proprement.

Règle d'architecture (wrapper agnostique) : aucune commande ne hardcode de nom
d'outil — on manipule des conteneurs et des tags, jamais le contenu de l'image.
"""

from __future__ import annotations

from contextlib import contextmanager

import typer
from rich.console import Console
from rich.table import Table

from pentbox import __version__, container

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


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #

@app.command()
def install(
    image: str = typer.Argument("debian", help="Saveur d'image : debian | blackarch."),
    build: bool = typer.Option(False, "--build", help="Builder en local (lot 2)."),
) -> None:
    """Récupère (pull) une image pentbox."""
    if build:
        console.print("[yellow]--build[/] arrivera au lot 2 ; pour l'instant on pull.")
    with _errors():
        with console.status(f"Récupération de l'image « {image} »…"):
            ref = container.pull_image(image)
    console.print(f"[green]✓[/] image prête : [bold]{ref}[/]")


@app.command()
def update(
    image: str = typer.Argument("debian", help="Saveur d'image à mettre à jour."),
) -> None:
    """Récupère la dernière version de l'image (pull)."""
    with _errors():
        with console.status(f"Mise à jour de l'image « {image} »…"):
            ref = container.pull_image(image)
    console.print(f"[green]✓[/] image à jour : [bold]{ref}[/]")


# --------------------------------------------------------------------------- #
# Cycle de vie
# --------------------------------------------------------------------------- #

@app.command()
def create(
    mission: str = typer.Argument(..., help="Nom de la mission / du conteneur."),
    image: str = typer.Option("debian", "--image", "-i", help="Saveur d'image."),
    no_start: bool = typer.Option(False, "--no-start", help="Créer sans démarrer."),
) -> None:
    """Crée un conteneur pour une mission, avec son workspace persistant."""
    with _errors():
        workspace = container.create_mission(mission, image, start=not no_start)
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
) -> None:
    """Ouvre un shell (ou lance une commande) dans le conteneur d'une mission."""
    with _errors():
        code = container.exec_mission(mission, command)
    raise typer.Exit(code=code)


@app.command("list")
def list_missions() -> None:
    """Liste les missions / conteneurs pentbox."""
    with _errors():
        rows = container.list_missions()
    if not rows:
        console.print("[dim]aucune mission — `pentbox create <nom>` pour commencer.[/]")
        return
    table = Table(title="Missions pentbox")
    for col in ("MISSION", "SAVEUR", "ÉTAT", "IMAGE", "CRÉÉE"):
        table.add_column(col)
    for r in rows:
        color = "green" if r["status"] == "running" else "yellow"
        table.add_row(
            r["mission"],
            r["flavor"],
            f"[{color}]{r['status']}[/]",
            r["image"],
            r["created"],
        )
    console.print(table)


@app.command()
def info(mission: str = typer.Argument(..., help="Mission à inspecter.")) -> None:
    """Affiche les métadonnées d'une mission."""
    with _errors():
        data = container.mission_info(mission)
    table = Table(show_header=False, title=f"Mission « {mission} »")
    for key in ("mission", "flavor", "status", "image", "network", "workspace", "created", "container"):
        table.add_row(f"[bold]{key}[/]", str(data[key]))
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
