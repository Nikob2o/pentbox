# pentbox — Plan de faisabilité

> Environnement de hacking conteneurisé, façon Exegol, mais maison, auto-hébergé et sans paywall.
> Nom de travail : `pentbox`. Statut : **plan, pas encore construit.**
> Rédigé le 2026-07-18.

---

## Contexte — pourquoi ce projet

Exegol est passé d'une licence **GPL3 à une licence propriétaire (ESL)**, avec un modèle
**Community / Pro / Enterprise**. En gratuit, on n'a plus accès qu'à l'image `free` :
équivalente à `full` mais **volontairement quelques versions en retard**. Les images à jour et
thématiques sont derrière le paywall.

L'objectif est donc de reconstruire **un équivalent maison** : définitions versionnées, images à
jour, hébergées chez soi, zéro dépendance à un abonnement — tout en apprenant l'architecture et en
l'adaptant à l'infra existante (GitHub, Docker Hub, éventuellement le cluster k3s).

> ⚠️ **Licence** : on ne réutilise **aucune** définition d'image Exegol (désormais ESL). Tout est
> reconstruit *from scratch*, à partir de bases publiques et d'outils **open-source uniquement**.

---

## Vision produit

Un **wrapper CLI** qui pilote des **images de conteneur pré-construites**, riches en outils
offensifs, avec les extras qui font le confort d'Exegol (workspaces persistants, GUI, logging de
session, desktop, VPN…). L'utilisateur **télécharge l'image** (`pull`) plutôt que de la builder.

Deux bases, un seul produit :

- **Debian** (apt) — inclut la possibilité de tirer les dépôts/métapaquets Kali. Image « full ».
- **BlackArch** (pacman) — l'alternative Arch, des milliers d'outils via les groupes `blackarch-*`.

---

## Principes d'architecture

### 1. Wrapper agnostique
Le wrapper ne sait **rien** du contenu de l'image : il fait `create / start / exec / stop / list /
rm / install` sur un **tag** qu'on lui donne. Conséquence : ajouter une base = **un Dockerfile +
un tag de plus**, sans toucher au wrapper.

Deux règles pour tenir ça :
- **Aucun nom d'outil hardcodé** dans le wrapper (les binaires diffèrent d'une base à l'autre →
  rester sur du shell générique, pas de `pentbox exec bloodhound`).
- **Un dossier `assets/` commun** (config zsh/tmux, aliases, entrypoint, resources) copié dans
  **chaque** image quelle que soit la base → **une seule UX** pour N bases.

**Feature = logique partagée dans le wrapper/assets + un paquet à installer par base.**
C'est ce qui rend 2 bases et 13 features gérables. Quand on ajoutera une base, elle **hérite** de
toutes les features (il suffit d'installer les paquets équivalents).

### 2. Stack technique
- **Wrapper** : Python + **Typer** (CLI + autocomplétion), piloté par le **Docker SDK Python**
  (pas de shell-out), packagé **pyproject.toml + pipx**.
- Config **YAML** sous `~/.config/pentbox/`, données sous `~/.local/share/pentbox/` (norme XDG).

### 3. Chaîne de distribution
```
GitHub (source: Dockerfiles + wrapper + assets)
   └─ GitHub Actions (build sur push / cron hebdo)
         └─ push image pré-construite → Docker Hub
                                          └─ wrapper `pull` par défaut  (+ `--build` en option)
```
**Pourquoi stocker l'image pré-construite** (et pas juste livrer le Dockerfile) :
- **Vitesse** — `pull` de couches au lieu de 30 min–1 h+ de build.
- **Reproductibilité** — tout le monde a **l'image identique** (crucial pour un env de pentest).
- **Robustesse** — le build a déjà réussi, figé ; il ne casse pas si un upstream disparaît.
- Le build coûteux est payé **une fois** (en CI), pas par chaque utilisateur.

C'est exactement le modèle d'Exegol (base `debian:12-slim` hand-rollée, images pré-construites sur
Docker Hub `nwodtuhs/exegol`, `exegol install` qui pull, `exegol build` en option).

---

## Les deux images

| | **Debian** | **BlackArch** |
|---|---|---|
| Base | `debian:12-slim` (+ dépôts/métapaquets Kali au besoin) | `archlinux` / `blackarchlinux` |
| Gestionnaire | `apt` | `pacman` + repo BlackArch |
| Contenu « full » | `kali-linux-large` ou set curated + pipx/git | groupes `blackarch-*` |
| Effort Dockerfile | 🟠 moyen (hand-roll possible) à 🟢 faible (métapaquets) | 🟠 moyen (toolchain à réécrire) |

> BlackArch est un **chantier à part** (pacman ≠ apt, scripting d'install à réécrire). On le traite
> comme un second temps, une fois le pipeline prouvé sur Debian.

---

## Catalogue des features (inspiré d'Exegol)

| Feature | Rôle | Où ça vit | Coût | Phase |
|---|---|---|---|---|
| Workspaces | Dossier persistant par mission, perms synchro | wrapper (bind mount) | 🟢 | MVP |
| X11 sharing | GUI du conteneur affichées sur le host | wrapper | 🟢 (XWayland déjà prêt) | MVP |
| Container info/comments | Métadonnées via `info` | wrapper (labels docker) | 🟢 | MVP |
| Network modes | host / bridge / nat / isolé | wrapper (flags run) | 🟢 | MVP |
| Port publishing | Exposer un service hors host-mode | wrapper (`-p`) | 🟢 | MVP |
| Env vars + timezone | Config persistante, TZ du host | wrapper (`-e`, mount) | 🟢 | MVP |
| Device passthrough | Accès matériel (wifi, Proxmark…) | wrapper (`--device`) | 🟢 | MVP |
| My-resources | Scripts/configs perso, partagés à tous les conteneurs | wrapper + convention setup | 🟡 | MVP+ |
| Shared resources | Wordlists/outils communs montés en RO | wrapper (volume) | 🟡 | MVP+ |
| **Shell logging** | Sessions enregistrées en **asciinema** (relecture, timestamps, gzip) | wrapper + `asciinema` dans l'image | 🟡 | **tôt** (killer feature reporting) |
| VPN | Tunnel **OpenVPN/WireGuard** auto au démarrage | wrapper + `openvpn`/`wg` + `NET_ADMIN`/tun | 🟡 | phase 2 |
| **Desktop** | DE graphique via **navigateur (noVNC)** ou VNC, auth PAM | wrapper (port/auth) + **DE+VNC dans l'image** | 🔴 | phase 2 |

**Priorisation :**
- Toute la colonne 🟢 = quasi gratuit (flags `docker run` exposés par le wrapper) → à prévoir dès le MVP.
- **Shell logging tôt** : moyen coût, énorme valeur (traçabilité/reporting de pentest).
- **Desktop** = le seul gros morceau (alourdit l'image + parties mobiles) → phase 2.
- **VPN** : moyen, non bloquant → phase 2.

---

## Environnement cible (machine vérifiée le 2026-07-18)

| Brique | État | Action |
|---|---|---|
| Docker | 29.6.2, user dans groupe `docker` ✅ | service **inactive** → `sudo systemctl enable --now docker` |
| GUI (X11) | Wayland + **XWayland actif** (`:1`), `xhost` présent ✅ | rien : monter le socket + `DISPLAY=:1` |
| Python / packaging | 3.14.6 + pipx 1.15 ✅ | ⚠️ Python 3.14 très récent : surveiller les wheels ; épingler le venv de l'outil sur 3.12/3.13 si besoin |
| Emplacement | `~/Projets/pentbox/` | repo à `git init` au démarrage |
| Comptes | GitHub + Docker Hub dispos ✅ | login Docker Hub pour éviter les limites de pull anonyme |

---

## Roadmap

### MVP (wrapper + 1re image Debian)
0. Squelette projet + packaging pipx éditable — ~30 min
1. Lifecycle du wrapper (`create/start/exec/stop/list/rm`) — testable sur une image **Debian/Kali standard** — ~1–2 h
2. Dockerfile Debian « full » + `install` — ~1–2 h (surtout du build passif)
3. Workspaces + my-resources + shared resources — ~1 h
4. X11 + réseau host + features 🟢 (device, ports, env, tz, comments) — ~1 h
5. **Shell logging (asciinema)** + config YAML + polish — ~1–2 h
6. GitHub Actions : build Debian → push Docker Hub — ~1 h

> Le wrapper (lots 1→5) se teste **sur une image Debian/Kali standard** avant que l'image custom
> soit prête → outil fonctionnel dès le lot 1.

### Phase 2
- Base **BlackArch** (Dockerfile pacman + groupes `blackarch-*`) — hérite des features du wrapper.
- **VPN** (OpenVPN/WireGuard).
- **Desktop** (XFCE + VNC/noVNC + auth).

### Plus tard (optionnel)
- Wrapper packagé en **AUR / repo Arch perso** (`pacman -S pentbox`) — sinon `pipx install` depuis git.
- **Registre privé sur le k3s** (`registry:2` / Harbor) en alternative/complément à Docker Hub.

---

## Points de vigilance

- **Python 3.14** : très neuf → un `pipx install` d'une lib sans wheel 3.14 peut râler. Mitigation :
  épingler l'interpréteur du venv de l'outil sur 3.12/3.13.
- **Taille image** : une « full » fait ~0,8–1,5 Go (voire plus). Normal ; Docker Hub gratuit encaisse.
- **`--network host` + rootful** : nécessaire pour le pentest (Responder, scans). Déjà en rootful ✅.
- **Desktop** = le poste le plus lourd, à isoler en phase 2.
- **hashcat/GPU** : hors périmètre image (passthrough GPU = galère) → crack côté host.
- **BloodHound** : GUI côté host, collector dans le conteneur.

---

## Mises à jour & maintenance

Trois axes de MAJ distincts :

| Quoi | Mécanisme | Manuel ? |
|---|---|---|
| Outils dans l'image | rebuild → push nouveau tag → `pull` | ❌ auto (CI) |
| Wrapper (CLI) | `pipx upgrade pentbox` | 1 commande |
| Récupérer l'image fraîche | `pentbox update` (= `docker pull`) | 1 commande (automatisable) |

**Faut-il rebuild à chaque MAJ ? Oui, mais c'est la CI qui le fait.** Une image Docker est immuable :
les outils sont figés au build. Pour des outils plus récents → reconstruire. Ce rebuild est
**délégué à une GitHub Action planifiée** :

```yaml
on:
  schedule:
    - cron: '0 4 * * 1'   # rebuild hebdo (lundi 4h)
```

Le job rebuild depuis le Dockerfile (qui fait `apt update && apt upgrade` / `pacman -Syu` +
`pipx`/`git pull` au build → dernières versions) puis push sur Docker Hub. → **une image à jour
attend en permanence sur Docker Hub, sans intervention**. Seul geste côté user : `pentbox update`
(pull), automatisable via timer systemd mais mieux vaut manuel (pas de surprise en mission).

> **Où tourne le cron ?** Sur les **machines de GitHub** (runners hébergés), **pas sur le PC** —
> le PC peut être éteint, ça n'a aucun impact. Toute la chaîne fraîcheur est cloud (GitHub build →
> Docker Hub héberge) ; le PC n'est que consommateur (`pull`). **Aucun hébergement à prévoir** :
> repo **public** = minutes illimitées gratuites ; repo **privé** = plafonné (~2000 min/mois).
> Caveats cron GitHub : tourne en UTC, peut être retardé sous charge, et **mis en pause après ~60 j
> d'inactivité** du repo (un `push` le réactive).
> Le runner self-hosted sur k3s (plus bas) est une **option** pour le privé — lui devrait rester
> allumé, mais n'est **pas nécessaire**.

**Alternative sans rebuild** : dans un conteneur en cours, `apt upgrade` / `pacman -Syu` à la volée
→ dépannage ponctuel, mais **éphémère** et casse la reproductibilité. Le vrai canal reste le rebuild CI.

**Fraîcheur vs reproductibilité** : la CI publie **deux tags** — un **daté** (ex.
`pentbox-debian:2026-07-18`, pour figer une mission) **et** `latest` (daily driver). On épingle une
mission sur le tag daté quand on veut un toolset gelé (reporting reproductible).

**Nuances maintenance :**
- **BlackArch (rolling)** : `pacman -Syu` au build casse plus souvent qu'apt → surveiller ses rebuilds.
  Debian = plus stable/reproductible ; BlackArch = plus frais mais plus de churn.
- **Minutes GitHub Actions** : rebuild multi-Go hebdo = gourmand. Repos **publics** = minutes gratuites ;
  **privé** = plafonné. Option : **runner self-hosted sur le k3s** → builds illimités, chez soi.

---

## Vérification (quand ce sera construit)

1. `pipx install -e ~/Projets/pentbox` → `pentbox --help` répond.
2. `pentbox install debian` → l'image se `pull` depuis Docker Hub (ou `--build` en local).
3. `pentbox create test && pentbox exec test` → shell interactif dans le conteneur.
4. Créer un fichier dans le workspace → vérifier sa **persistance** côté host et les **permissions**.
5. Lancer une app GUI (ex. un outil X11) → s'affiche sur l'écran host via XWayland.
6. Vérifier que la **session est loggée** (fichier asciinema dans le workspace) et relisible.
7. Feature 🟢 : `--device`, `-p`, réseau host, `info` (métadonnées) fonctionnent.
8. Phase 2 : `--desktop` ouvre le DE dans le navigateur ; `--vpn` établit le tunnel au démarrage.

---

## Décisions encore ouvertes

- **Nom définitif** du projet (`pentbox` = provisoire).
- **Base Debian « full »** : hand-roll façon Exegol (contrôle, + de shell) **ou** métapaquets Kali
  (rapide). Reco : démarrer aux métapaquets, affiner ensuite.
- **Hébergement image** : Docker Hub (simple) vs registre privé k3s (souverain). Reco : Docker Hub
  d'abord, k3s plus tard.
