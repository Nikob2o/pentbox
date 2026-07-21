#!/bin/sh
# pentbox — installeur rapide (Linux).
#
#   curl -sSL https://raw.githubusercontent.com/Nikob2o/pentbox/main/install.sh | sh
#   # ou :  sh install.sh [saveur]      (saveur = kali (défaut) | blackarch)
#
# Ne touche pas au système : vérifie Docker + pipx (guide si absents), installe le
# CLI via pipx depuis le repo, et récupère l'image publiée. Aucune config requise
# (le namespace Docker Hub officiel est le défaut).
set -eu

REPO="git+https://github.com/Nikob2o/pentbox.git"
FLAVOR="${1:-kali}"

echo "== pentbox : installation =="

# 1. Docker présent et joignable
if ! command -v docker >/dev/null 2>&1; then
    echo "✗ Docker introuvable. Installe-le puis relance :"
    echo "    Arch          : sudo pacman -S docker && sudo systemctl enable --now docker"
    echo "    Debian/Ubuntu : sudo apt install docker.io && sudo systemctl enable --now docker"
    echo "    puis : sudo usermod -aG docker \"\$USER\"  (et reconnecte-toi)"
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "✗ Le démon Docker ne répond pas (service arrêté ou user hors du groupe docker)."
    echo "    sudo systemctl start docker   /   sudo usermod -aG docker \"\$USER\" puis reconnecte-toi"
    exit 1
fi

# 2. pipx présent
if ! command -v pipx >/dev/null 2>&1; then
    echo "✗ pipx introuvable. Installe-le puis relance :"
    echo "    Arch          : sudo pacman -S python-pipx"
    echo "    Debian/Ubuntu : sudo apt install pipx"
    exit 1
fi

# 3. CLI pentbox (install ou réinstall si déjà présent)
echo "→ installation du CLI (pipx)…"
pipx install "$REPO" 2>/dev/null || pipx install --force "$REPO"
export PATH="$HOME/.local/bin:$PATH"

# 4. Image publiée (aucune config à écrire : namespace par défaut)
echo "→ récupération de l'image « $FLAVOR » (peut être long, plusieurs Go)…"
pentbox install "$FLAVOR"

echo
echo "✓ pentbox prêt. Pour démarrer :"
echo "    pentbox create mission1 --image $FLAVOR"
echo "    pentbox shell mission1"
