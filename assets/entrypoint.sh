#!/bin/sh
# pentbox — entrypoint commun (base-agnostique, copié dans chaque image).
# Point unique de setup runtime, puis exec de la commande du conteneur
# (sleep infinity par défaut, cf. CMD du Dockerfile).
#
# Lot 5 : démarrage du logging de session (asciinema) ici.
set -e
exec "$@"
