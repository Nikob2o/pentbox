# pentbox — image « debian » (base apt). Squelette du lot 0, étoffé au lot 2.
#
# Choix retenu : base Debian slim, outils via métapaquets Kali (rapide) ou set
# curated. User non-root, assets/ communs, entrypoint partagé. Rien d'Exegol
# n'est repris ici (licence ESL) : construction from scratch, outils open-source.
FROM debian:12-slim

LABEL org.opencontainers.image.title="pentbox-debian"
LABEL org.opencontainers.image.description="pentbox — image de pentest base Debian (WIP)"

# TODO(lot2): dépôts/métapaquets, arsenal offensif, user non-root, COPY assets/,
#             entrypoint (workspace, logging asciinema, etc.).

CMD ["/bin/bash"]
