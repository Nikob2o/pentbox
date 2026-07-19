"""Pilotage des conteneurs via le Docker SDK Python.

Squelette du lot 0 : ce module hébergera la logique de cycle de vie
(create/start/exec/stop/rm) au lot 1. On ne shell-out pas vers `docker` — on
passe par le SDK pour une gestion d'erreurs propre.

Wrapper agnostique : rien ici ne connaît le *contenu* d'une image ; on ne
manipule que des conteneurs, des tags et des mounts.
"""

from __future__ import annotations

# import docker  # activé au lot 1

IMAGE_FLAVORS = ("debian", "blackarch")
