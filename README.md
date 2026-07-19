# pentbox

> Environnement de hacking conteneurisé, façon [Exegol](https://exegol.com) — mais **maison**, auto-hébergé et **sans paywall**.

Un wrapper CLI **agnostique** qui pilote des images de pentest pré-construites
(bases **Debian** / **BlackArch**) : conteneurs par mission, workspaces persistants,
partage GUI, logging de session, etc. L'utilisateur **télécharge** l'image (`pull`)
plutôt que de la builder ; les images sont reconstruites automatiquement en CI.

📄 Conception détaillée : [`FAISABILITE.md`](./FAISABILITE.md)

## Statut

🚧 **En construction.** Lot 0 (squelette + packaging) fait ; le cycle de vie
(create / start / exec …) arrive au lot 1.

## Installation (dev, éditable)

```bash
pipx install -e ~/Projets/pentbox
pentbox --help
```

## Structure

```
src/pentbox/      # le wrapper (CLI Typer + pilotage Docker SDK)
  cli.py          #   surface des commandes
  container.py    #   cycle de vie des conteneurs (lot 1)
  config.py       #   chemins XDG / config
assets/           # config partagée, copiée dans chaque image (UX commune)
images/           # Dockerfiles par saveur (debian, blackarch)
```

## Licence

MIT — voir [`LICENSE`](./LICENSE). Aucune définition d'image n'est reprise
d'Exegol (désormais sous licence propriétaire ESL) : tout est reconstruit
*from scratch* à partir de bases publiques et d'outils open-source.
