# pentbox

> Environnement de hacking conteneurisé, façon [Exegol](https://exegol.com) — mais **maison**, auto-hébergé et **sans paywall**.

Un wrapper CLI **agnostique** qui pilote des images de pentest pré-construites :

- **kali** — base Debian slim, arsenal façon Exegol (apt + pipx + NetExec).
- **blackarch** — base Arch/BlackArch, arsenal pacman (netexec/impacket natifs).

Une mission = un conteneur, avec workspace persistant, arsenal offensif, shell
enregistré, bureau graphique optionnel et VPN optionnel. L'utilisateur
**télécharge** l'image (`pull`) plutôt que de la builder ; les images sont
reconstruites et publiées automatiquement en CI (GitHub Actions → Docker Hub).

📄 Conception détaillée : [`FAISABILITE.md`](./FAISABILITE.md)

## Statut

MVP complet et stable sur les **deux bases**. Cycle de vie complet, ressources
partagées, options docker, logging asciinema, config TOML, **bureau XFCE**
(noVNC, thème sombre, logo, menu d'outils, Firefox), **VPN** (OpenVPN/WireGuard),
mot de passe VNC, cohabitation de plusieurs bureaux, et **CI de publication**.

## Installation

```bash
pipx install -e ~/Projets/pentbox      # installe la commande `pentbox`
pentbox --help
```

Une fois un registre configuré (voir [Publication / CI](#publication--ci)),
`pentbox install kali` **pull** l'image publiée — pas besoin de builder en local.

## Usage rapide

```bash
pentbox install kali                # pull l'image (ou --build pour builder en local)
pentbox create mission1             # crée + démarre une mission (workspace persistant)
pentbox shell mission1              # ouvre un shell (démarre la mission si besoin)
pentbox list                        # missions actives
pentbox info                        # catalogue des images + missions
pentbox logs mission1 --play        # rejoue la dernière session enregistrée
pentbox rm mission1                 # supprime le conteneur (workspace conservé)
```

## Commandes

| Commande | Rôle |
|---|---|
| `install <saveur> [--build]` | Pull (ou build local) de l'image `kali` / `blackarch`. |
| `update <saveur>` | Met à jour l'image depuis le registre. |
| `create <mission> [options]` | Crée (et démarre) une mission. Voir options ci-dessous. |
| `shell <mission>` | Ouvre un shell — **démarre la mission si elle est arrêtée**. |
| `exec <mission> [cmd]` | Exécute une commande (ou un shell) dans une mission en cours. |
| `start` / `stop <mission>` | Démarre / arrête le conteneur. |
| `list` | Missions (état, saveur, image, commentaire). |
| `info [mission]` | Sans argument : catalogue des images + missions. Avec : détails d'une mission. |
| `logs <mission> [--play]` | Liste (ou rejoue) les sessions asciinema. |
| `resources` | Chemins des dossiers partagés (my-resources / resources). |
| `config` | Affiche la config effective. |
| `rm <mission> [-f]` | Supprime le conteneur (le workspace host est conservé). |

### Options de `create`

| Option | Effet |
|---|---|
| `-i, --image <saveur>` | Saveur d'image (défaut : config). |
| `-c, --comment <texte>` | Annotation libre (visible dans `list` / `info`). |
| `-e, --env KEY=VAL` | Variable d'environnement (répétable). |
| `--network host\|bridge` | Réseau (défaut : host). |
| `-p, --port H:C` | Publie un port (réseau bridge). |
| `--device /dev/…` | Passthrough matériel (répétable). |
| `--x11` | Partage l'affichage X11 (apps GUI de l'hôte). |
| `--desktop [--desktop-port N]` | Bureau XFCE via navigateur (noVNC). |
| `--desktop-password <pw>` | Mot de passe VNC (défaut : généré aléatoirement). |
| `--vpn <config>` | Connecte un VPN OpenVPN (`.ovpn`) ou WireGuard (`.conf`) au démarrage. |
| `--no-start` | Crée sans démarrer. |

## Fonctionnalités

**Arsenal** — outils offensifs prêts à l'emploi, dans le même esprit qu'Exegol et
enrichis au fil de l'eau : recon/scan (nmap, masscan, gobuster, ffuf,
feroxbuster, whatweb, dnsrecon), Active Directory (impacket, netexec, certipy,
mitm6, coercer, bloodhound-python, kerbrute, enum4linux-ng), poisoning/MITM
(responder, mitm6), web (sqlmap, wfuzz, nikto), et cassage (john, hashcat,
hydra, medusa). Identique sur les deux bases (installé via apt/pipx/binaires côté
kali, pacman côté blackarch).

**Workspaces persistants** — chaque mission a un dossier `~/.local/share/pentbox/workspaces/<mission>`
monté sur `/workspace`. Les fichiers survivent à `rm` (seul le conteneur part).
UID/GID de l'hôte injectés au build → pas de fichiers `root:root`.

**Ressources partagées** — `my-resources` (rw, perso, partagé entre missions) et
`resources` (ro, wordlists/binaires perso). Les dotfiles (`.zshrc`, `.tmux.conf`)
et l'historique de commandes se personnalisent **à chaud** via `my-resources`,
sans rebuild.

**Wordlists** — **SecLists complet** est baké dans l'image
(`/usr/share/seclists`), avec `rockyou.txt` décompressé au chemin standard
(`/usr/share/wordlists/rockyou.txt`). Les listes de référence sont donc prêtes à
l'emploi hors-ligne. Les wordlists **perso** passent par le volume `resources`.

**Logging de session** — les shells interactifs sont enregistrés en asciinema
(`--log` / config), rejouables avec `pentbox logs`.

**Bureau graphique** — `create --desktop` lance un bureau XFCE (thème sombre,
fond d'écran + logo pentbox, menu d'outils, Firefox) accessible sur
`http://localhost:6080/vnc.html`, protégé par un **mot de passe VNC**. Plusieurs
bureaux peuvent tourner en parallèle (display + port choisis libres
automatiquement).

**VPN** — `create --vpn <config>` monte la config en lecture seule et connecte le
tunnel au démarrage (OpenVPN ou WireGuard **auto-détecté**). Le réseau bascule en
bridge pour **isoler le tunnel** (pas de fuite du trafic de l'hôte). WireGuard
tombe sur son implémentation userspace si le module noyau n'est pas exposé — aucun
`modprobe` requis côté hôte.

**Desktop sur bridge & VPN + desktop** — `--desktop` marche en réseau host
(défaut) comme en `--network bridge` (le port noVNC est alors publié sur le
localhost de l'hôte). `--vpn` et `--desktop` sont donc **combinables** : les deux
tournent sur bridge, tunnel isolé + bureau accessible. (Un VPN qui redirige *tout*
le trafic — `0.0.0.0/0` — peut gêner l'accès noVNC ; préférer un split-tunnel.)

## Structure

```
src/pentbox/      # le wrapper (CLI Typer + pilotage Docker SDK)
  cli.py          #   surface des commandes
  container.py    #   cycle de vie des conteneurs
  config.py       #   chemins XDG / config
assets/           # config partagée, copiée dans chaque image (UX commune)
images/           # Dockerfiles par saveur (kali, blackarch)
```

## Publication / CI

Les images sont construites et publiées sur Docker Hub par GitHub Actions
([`.github/workflows/build.yml`](./.github/workflows/build.yml)) : matrice
`[kali, blackarch]`, à chaque push touchant `images/` ou `assets/`, chaque semaine
(fraîcheur des outils), ou à la demande. Le build tourne sur les runners
GitHub — ton PC n'a pas à être allumé.

**Brancher la publication :**

1. Pousse ce repo sur GitHub.
2. Repo → Settings → Secrets and variables → Actions, ajoute :
   - `DOCKERHUB_USERNAME` — ton user Docker Hub
   - `DOCKERHUB_TOKEN` — un token (Docker Hub → Account Settings → Security)
3. Côté client, renseigne ton namespace dans `~/.config/pentbox/config.toml` :
   ```toml
   [registry]
   namespace = "ton-user-dockerhub"
   tag = "latest"
   ```

Ensuite `pentbox install kali` (sans `--build`) et `pentbox update` **pull**
l'image depuis Docker Hub.

## Licence

MIT — voir [`LICENSE`](./LICENSE). Aucune définition d'image n'est reprise
d'Exegol (désormais sous licence propriétaire ESL) : tout est reconstruit
*from scratch* à partir de bases publiques et d'outils open-source.
