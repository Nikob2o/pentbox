# pentbox

> Environnement de hacking conteneurisé, façon [Exegol](https://exegol.com) — mais **maison**, auto-hébergé et **sans paywall**.

Un wrapper CLI **agnostique** qui pilote des images de pentest pré-construites
(bases **Debian** / **BlackArch**) : conteneurs par mission, workspaces persistants,
partage GUI, logging de session, etc. L'utilisateur **télécharge** l'image (`pull`)
plutôt que de la builder ; les images sont reconstruites automatiquement en CI.

📄 Conception détaillée : [`FAISABILITE.md`](./FAISABILITE.md)

## Statut

MVP fonctionnel : cycle de vie complet (create / start / exec / stop / list /
info / rm), image **Debian** custom (user non-root), ressources partagées
(my-resources + resources), options docker (env, x11, device, réseau/ports,
comment), **logging asciinema**, config TOML, et **CI de publication**. Base
**BlackArch** et desktop/VPN à venir.

## Installation (dev, éditable)

```bash
pipx install -e ~/Projets/pentbox
pentbox --help
```

## Usage rapide

```bash
pentbox install debian --build   # build local (ou pull si un registre est configuré)
pentbox create mission1          # crée + démarre une mission (workspace persistant)
pentbox exec mission1            # shell interactif (enregistré en asciinema)
pentbox list                     # missions actives
pentbox logs mission1 --play     # rejoue la dernière session
pentbox rm mission1              # supprime le conteneur (workspace conservé)
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

## Publication / CI

Les images sont construites et publiées sur Docker Hub par GitHub Actions
([`.github/workflows/build.yml`](./.github/workflows/build.yml)) : à chaque push
touchant `images/` ou `assets/`, chaque semaine (fraîcheur des outils), ou à la
demande. Le build tourne sur les runners GitHub — ton PC n'a pas à être allumé.

**Brancher la publication :**

1. Pousse ce repo sur GitHub.
2. Repo → Settings → Secrets and variables → Actions, ajoute :
   - `DOCKERHUB_USERNAME` — ton user Docker Hub
   - `DOCKERHUB_TOKEN` — un token (Docker Hub → Account Settings → Security)
3. Côté client, renseigne ton namespace dans `~/.config/pentbox/config.toml` :
   ```toml
   [registry]
   namespace = "ton-user-dockerhub"
   tag = "latest"     # ou "full" pour l'arsenal complet
   ```

Ensuite `pentbox install debian` (sans `--build`) et `pentbox update` **pull**
l'image depuis Docker Hub. Tags publiés : `:core` (= `:latest`, fiable),
`:full` (arsenal Kali), plus des tags datés.

## Licence

MIT — voir [`LICENSE`](./LICENSE). Aucune définition d'image n'est reprise
d'Exegol (désormais sous licence propriétaire ESL) : tout est reconstruit
*from scratch* à partir de bases publiques et d'outils open-source.
