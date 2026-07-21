# Installation de pentbox

Guide complet pour installer et utiliser pentbox sur une machine Linux. Pour le
résumé express, voir la section *Installation* du [README](./README.md).

pentbox est un **CLI Python** (installé via pipx) qui **télécharge** des images
de pentest pré-construites depuis Docker Hub et les fait tourner en conteneurs.
Il n'y a donc **rien à builder** côté utilisateur : Docker + le CLI, et c'est prêt.

---

## Compatibilité

Hôte **Linux x86_64** avec Docker + Python ≥ 3.9 + pipx. Vérifié :

| Système hôte | Python | Statut |
|---|---|---|
| Arch / Manjaro | 3.13+ | ✅ |
| Debian 12+ (bookworm) | 3.11+ | ✅ |
| Ubuntu 24.04+ | 3.12+ | ✅ |
| Ubuntu 22.04 / 20.04, Debian 11 | 3.10 / 3.9 | ✅ (backport `tomli` tiré automatiquement) |
| Fedora récent | 3.12+ | ✅ |

**Limites :**

- **Architecture x86_64 (amd64) uniquement.** Les images sont buildées pour
  x86_64 et embarquent des binaires x86_64 → **pas d'ARM natif** (Raspberry Pi,
  Apple Silicon) sans émulation qemu (lente).
- **Linux seulement.** macOS / Windows ne sont pas supportés : pentbox s'appuie
  sur des mécanismes Linux (réseau `host` par défaut, mapping UID/GID,
  `/dev/net/tun` pour le VPN, partage X11) que Docker Desktop ne reproduit pas.

---

## 1. Prérequis

### Docker

Le démon Docker doit être installé, démarré, et ton utilisateur dans le groupe
`docker`.

```bash
# Arch / Manjaro
sudo pacman -S docker

# Debian / Ubuntu
sudo apt install docker.io
# (ou le paquet officiel : curl -fsSL https://get.docker.com | sh)

# Fedora
sudo dnf install docker-ce         # ou moby-engine

# Démarrer le service + s'ajouter au groupe (toutes distros)
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

> ⚠️ Après le `usermod`, **déconnecte-toi / reconnecte-toi** (ou lance `newgrp docker`)
> pour que l'appartenance au groupe prenne effet. Vérifie avec `docker info`.

### pipx (Python 3.9+)

```bash
# Arch          : sudo pacman -S python-pipx
# Debian/Ubuntu : sudo apt install pipx
# Fedora        : sudo dnf install pipx
pipx ensurepath      # ajoute ~/.local/bin au PATH (puis rouvre le terminal)
```

---

## 2. Installation

### En une commande (recommandé)

```bash
curl -sSL https://raw.githubusercontent.com/Nikob2o/pentbox/main/install.sh | sh
```

Le script vérifie Docker + pipx, installe le CLI, et récupère l'image `kali`.
Passe `blackarch` en argument pour l'autre base :
`curl -sSL …/install.sh | sh -s -- blackarch`.

### À la main

```bash
pipx install "git+https://github.com/Nikob2o/pentbox.git"
pentbox --version          # doit afficher la version
pentbox install kali       # pull l'image publiée (aucune config requise)
```

> Aucun `config.toml` à écrire : le namespace Docker Hub officiel (`nocoblas`) est
> le défaut, donc `pentbox install` pull directement l'image publiée.

---

## 3. Premier lancement

```bash
pentbox create mission1            # crée + démarre une mission (workspace persistant)
pentbox shell mission1             # shell dans le conteneur
pentbox create mission1 --desktop  # + bureau XFCE : http://localhost:6080/vnc.html
pentbox list                       # missions actives
pentbox info                       # catalogue des images + missions
```

Voir le [README](./README.md#commandes) pour la liste complète des commandes et
des options de `create` (VPN, ports, X11, mot de passe VNC, etc.).

---

## 4. Mises à jour

```bash
pentbox update kali                          # récupère la dernière image
pentbox update blackarch
pipx upgrade pentbox                          # met à jour le CLI
# (ou, pour forcer : pipx install --force "git+https://github.com/Nikob2o/pentbox.git")
```

Les images sont reconstruites automatiquement (CI hebdomadaire) pour garder les
outils frais ; un `pentbox update` suffit à en profiter.

---

## 5. Données & portabilité

Tout ce qui est propre à une machine vit sous `~/.local/share/pentbox/` :

| Dossier | Contenu | Monté dans la mission |
|---|---|---|
| `workspaces/<mission>/` | fichiers de chaque mission | `/workspace` (rw) |
| `my-resources/` | espace perso partagé entre missions | `/opt/my-resources` (rw) |
| `resources/` | wordlists / binaires perso (lecture seule) | `/opt/resources` (ro) |

Ces données **ne sont pas synchronisées** entre machines. Pour les emporter,
copie simplement le dossier `~/.local/share/pentbox/` sur l'autre PC.

La config éventuelle est dans `~/.config/pentbox/config.toml`.

---

## 6. Configuration avancée (optionnel)

Le défaut suffit à la plupart des usages. Pour surcharger, crée
`~/.config/pentbox/config.toml` :

```toml
[defaults]
image = "kali"            # saveur par défaut de `create` (kali | blackarch)

[logging]
enabled = true            # enregistrer les shells en asciinema

[registry]
namespace = "nocoblas"    # user Docker Hub des images ; "" = build local uniquement
tag = "latest"
```

- **Builder en local** au lieu de pull : mets `namespace = ""` puis
  `pentbox install kali --build` (nécessite le repo cloné, plus long).
- **Ton propre registre** (fork) : mets ton user Docker Hub dans `namespace`.

---

## 7. Dépannage

| Symptôme | Cause probable / remède |
|---|---|
| `permission denied … docker.sock` | Utilisateur hors du groupe `docker` → `sudo usermod -aG docker "$USER"` puis reconnexion. |
| `Le démon Docker ne répond pas` | Service arrêté → `sudo systemctl start docker`. |
| `pentbox: command not found` | `~/.local/bin` hors du PATH → `pipx ensurepath` puis rouvre le terminal. |
| Pull très long / gros | Normal : les images embarquent SecLists (kali ~6,7 Go, blackarch ~8 Go). Prévois débit + espace disque. |
| `image … absente` au `create` | Fais d'abord `pentbox install <saveur>`. |

---

Licence MIT — voir [`LICENSE`](./LICENSE).
