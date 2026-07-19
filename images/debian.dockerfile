# pentbox — image « debian » (base apt).
#
# PROFILE=core (défaut) : arsenal offensif curated depuis les dépôts Debian.
#   Build léger, vérifiable en local (quelques minutes).
# PROFILE=full : ajoute le dépôt Kali + kali-linux-headless (arsenal complet).
#   Build lourd (plusieurs Go) → destiné à la CI, non validé en local.
#
# Rien d'Exegol n'est repris (licence ESL) : construction from scratch, outils
# open-source. Les UID/GID de l'host sont injectés → pas de fichiers root:root
# dans le workspace bind-monté.
FROM debian:12-slim

ARG PROFILE=core
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG USERNAME=pentbox

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PENTBOX_USER=${USERNAME}

# --- Base système + confort + arsenal 'core' (dépôts Debian) ---------------- #
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg git sudo \
      zsh tmux vim less \
      iproute2 iputils-ping dnsutils whois netcat-openbsd socat \
      openssh-client \
      python3 python3-pip pipx asciinema \
      nmap masscan hydra medusa john sqlmap wfuzz dirb whatweb dnsrecon proxychains4 \
    && rm -rf /var/lib/apt/lists/*

# --- Arsenal complet (optionnel, PROFILE=full) → CI de préférence ----------- #
RUN if [ "$PROFILE" = "full" ]; then set -eux; \
      wget -qO- https://archive.kali.org/archive-key.asc | gpg --dearmor \
        -o /usr/share/keyrings/kali-archive-keyring.gpg; \
      echo "deb [signed-by=/usr/share/keyrings/kali-archive-keyring.gpg] http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware" \
        > /etc/apt/sources.list.d/kali.list; \
      apt-get update; \
      apt-get install -y --no-install-recommends kali-linux-headless; \
      rm -rf /var/lib/apt/lists/*; \
    fi

# --- Utilisateur non-root (UID/GID alignés sur l'host) ---------------------- #
RUN groupadd -g "$HOST_GID" "$USERNAME" \
    && useradd -m -u "$HOST_UID" -g "$HOST_GID" -s /usr/bin/zsh "$USERNAME" \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/pentbox \
    && chmod 0440 /etc/sudoers.d/pentbox \
    && mkdir -p /workspace && chown "$HOST_UID:$HOST_GID" /workspace

# --- Assets communs (config partagée, base-agnostique) ---------------------- #
COPY assets/skel/ /home/${USERNAME}/
COPY assets/entrypoint.sh /usr/local/bin/pentbox-entrypoint
COPY assets/pentbox-shell /usr/local/bin/pentbox-shell
RUN chmod +x /usr/local/bin/pentbox-entrypoint /usr/local/bin/pentbox-shell \
    && chown -R "$HOST_UID:$HOST_GID" /home/${USERNAME}

LABEL org.opencontainers.image.title="pentbox-debian" \
      org.opencontainers.image.description="pentbox — image de pentest base Debian"

USER ${USERNAME}
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/pentbox-entrypoint"]
CMD ["sleep", "infinity"]
