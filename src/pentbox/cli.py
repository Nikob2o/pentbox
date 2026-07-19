"""Point d'entrée CLI (Typer).

Squelette du lot 0 : la surface des commandes est posée, mais la logique du
cycle de vie (create/start/exec/…) arrive au lot 1. Les commandes non encore
implémentées le disent honnêtement et sortent en code 1.

Règle d'architecture (wrapper agnostique) : aucune commande ne hardcode de nom
d'outil — on manipule des conteneurs et des tags, jamais le contenu de l'image.
"""

from __future__ import annotations

import typer

from pentbox import __version__

app = typer.Typer(
    name="pentbox",
    help="Environnement de hacking conteneurisé, façon Exegol — maison, sans paywall.",
    no_args_is_help=True,
)


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


# --------------------------------------------------------------------------- #
# Cycle de vie — surface posée au lot 0, logique implémentée au lot 1.
# --------------------------------------------------------------------------- #

def _todo(command: str, lot: int) -> None:
    """Signale honnêtement une commande pas encore implémentée."""
    typer.secho(
        f"[{command}] pas encore implémenté — prévu au lot {lot}.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def install(
    image: str = typer.Argument("debian", help="Saveur d'image : debian | blackarch."),
    build: bool = typer.Option(False, "--build", help="Builder en local au lieu de pull."),
) -> None:
    """Récupère (pull) ou build une image pentbox."""
    _todo("install", lot=1)


@app.command()
def create(
    mission: str = typer.Argument(..., help="Nom de la mission / du conteneur."),
    image: str = typer.Option("debian", "--image", "-i", help="Saveur d'image."),
) -> None:
    """Crée un conteneur pour une mission, avec son workspace persistant."""
    _todo("create", lot=1)


@app.command()
def start(mission: str = typer.Argument(..., help="Mission à démarrer.")) -> None:
    """Démarre le conteneur d'une mission."""
    _todo("start", lot=1)


@app.command()
def stop(mission: str = typer.Argument(..., help="Mission à arrêter.")) -> None:
    """Arrête le conteneur d'une mission."""
    _todo("stop", lot=1)


@app.command("exec")
def run_exec(
    mission: str = typer.Argument(..., help="Mission cible."),
    command: str = typer.Argument("", help="Commande à exécuter (défaut : shell interactif)."),
) -> None:
    """Ouvre un shell (ou lance une commande) dans le conteneur d'une mission."""
    _todo("exec", lot=1)


@app.command("list")
def list_missions() -> None:
    """Liste les missions / conteneurs pentbox."""
    _todo("list", lot=1)


@app.command()
def info(mission: str = typer.Argument(..., help="Mission à inspecter.")) -> None:
    """Affiche les métadonnées d'une mission."""
    _todo("info", lot=1)


@app.command()
def rm(mission: str = typer.Argument(..., help="Mission à supprimer.")) -> None:
    """Supprime le conteneur d'une mission."""
    _todo("rm", lot=1)


@app.command()
def update(
    image: str = typer.Argument("debian", help="Saveur d'image à mettre à jour."),
) -> None:
    """Récupère la dernière image (pull) — voir section maj du FAISABILITE."""
    _todo("update", lot=6)


if __name__ == "__main__":  # pragma: no cover
    app()
