#!/bin/sh
# pentbox — entrypoint commun (base-agnostique, copié dans chaque image).
# Point unique de setup runtime, puis exec de la commande du conteneur
# (sleep infinity par défaut, cf. CMD du Dockerfile).
set -e

# Bureau graphique (noVNC) optionnel, activé par PENTBOX_DESKTOP=1.
if [ "${PENTBOX_DESKTOP:-0}" = "1" ] && command -v pentbox-desktop >/dev/null 2>&1; then
    pentbox-desktop >/tmp/pentbox-desktop.log 2>&1 &
fi

# VPN optionnel (OpenVPN/WireGuard), activé par PENTBOX_VPN=<config>. Lancé en
# root (sudo) car créer l'interface/les routes du tunnel nécessite les privilèges.
if [ -n "${PENTBOX_VPN:-}" ] && command -v pentbox-vpn >/dev/null 2>&1; then
    sudo -n pentbox-vpn "$PENTBOX_VPN" >/tmp/pentbox-vpn-launch.log 2>&1 &
fi

exec "$@"
