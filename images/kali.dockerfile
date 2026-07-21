# pentbox — image « kali » (base Debian + arsenal offensif, façon Exegol).
#
# Aucun dépôt kali-rolling : chaque outil est posé depuis sa meilleure source
# (apt / pipx / git), ce qui garde une base Debian stable sans conflit de libs
# (contrairement à kali-linux-headless qui casse le userland). Arsenal
# extensible dans le temps, comme Exegol a grandi.
#
# UID/GID de l'host injectés → pas de fichiers root:root dans le workspace.
FROM debian:12-slim

ARG HOST_UID=1000
ARG HOST_GID=1000
ARG USERNAME=pentbox

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PENTBOX_USER=${USERNAME} \
    PIPX_HOME=/opt/pipx \
    PIPX_BIN_DIR=/usr/local/bin

# --- Base système + confort + arsenal apt (dépôts Debian) ------------------ #
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg git sudo perl \
      zsh tmux vim less ncurses-bin asciinema \
      iproute2 iputils-ping dnsutils whois netcat-openbsd socat tcpdump \
      smbclient ldap-utils snmp openssh-client \
      build-essential python3 python3-dev python3-pip pipx libffi-dev libssl-dev \
      nmap masscan hydra medusa john hashcat sqlmap wfuzz dirb gobuster whatweb dnsrecon proxychains4 \
    && rm -rf /var/lib/apt/lists/*

# --- Arsenal Python (pipx, à l'échelle système via PIPX_BIN_DIR) ----------- #
# Résilient façon Exegol : un outil qui échoue n'interrompt pas le build.
RUN for pkg in \
      impacket certipy-ad mitm6 ldapdomaindump coercer \
      "git+https://github.com/cddmp/enum4linux-ng" name-that-hash hashid updog; do \
      pipx install "$pkg" || echo "WARN: pipx install $pkg a échoué"; \
    done && rm -rf /root/.cache

# --- NetExec (dépendance Rust récente) ------------------------------------- #
# rustup temporaire, build, puis purge dans le MÊME layer → le toolchain Rust
# ne reste pas dans l'image (l'extension est déjà compilée dans le venv).
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && . "$HOME/.cargo/env" \
    && (pipx install "git+https://github.com/Pennyw0rth/NetExec" \
        || echo "WARN: pipx install NetExec a échoué") \
    && rustup self uninstall -y \
    && rm -rf "$HOME/.cargo" "$HOME/.rustup" /root/.cache

# --- Outils git non packagés ----------------------------------------------- #
RUN (git clone --depth 1 https://github.com/sullo/nikto /opt/nikto \
      && ln -sf /opt/nikto/program/nikto.pl /usr/local/bin/nikto) \
    || echo "WARN: installation de nikto échouée"

# --- Bureau graphique (XFCE + VNC + noVNC), activé à la demande par --desktop  #
RUN apt-get update && apt-get install -y --no-install-recommends \
      xfce4 xfce4-terminal tigervnc-standalone-server novnc websockify dbus-x11 xfonts-base \
      firefox-esr materia-gtk-theme \
    && rm -rf /var/lib/apt/lists/*

# --- VPN (OpenVPN + WireGuard), activé à la demande par --vpn -------------- #
# wireguard-go = implémentation userspace : wg-quick bascule dessus quand le
# module noyau wireguard n'est pas exposé au conteneur (cas courant) → aucun
# modprobe requis côté hôte, le tunnel monte avec /dev/net/tun + NET_ADMIN.
RUN apt-get update && apt-get install -y --no-install-recommends \
      openvpn wireguard-tools wireguard-go \
    && rm -rf /var/lib/apt/lists/*

# --- Utilisateur non-root (UID/GID alignés sur l'host) --------------------- #
RUN groupadd -g "$HOST_GID" "$USERNAME" \
    && useradd -m -u "$HOST_UID" -g "$HOST_GID" -s /usr/bin/zsh "$USERNAME" \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/pentbox \
    && chmod 0440 /etc/sudoers.d/pentbox \
    && mkdir -p /workspace && chown "$HOST_UID:$HOST_GID" /workspace

# --- Assets communs -------------------------------------------------------- #
COPY assets/skel/ /home/${USERNAME}/
COPY assets/entrypoint.sh /usr/local/bin/pentbox-entrypoint
COPY assets/pentbox-shell /usr/local/bin/pentbox-shell
COPY assets/pentbox-desktop /usr/local/bin/pentbox-desktop
COPY assets/pentbox-vpn /usr/local/bin/pentbox-vpn
COPY assets/history-templates /opt/pentbox/history-templates
COPY assets/pentbox-wallpaper.png /opt/pentbox/wallpaper.png
COPY assets/pentbox-logo.png /opt/pentbox/logo.png
COPY assets/pentbox-run /usr/local/bin/pentbox-run
COPY assets/menu/applications/ /usr/share/applications/
COPY assets/menu/desktop-directories/ /usr/share/desktop-directories/
RUN chmod +x /usr/local/bin/pentbox-entrypoint /usr/local/bin/pentbox-shell /usr/local/bin/pentbox-desktop /usr/local/bin/pentbox-run /usr/local/bin/pentbox-vpn \
    && chown -R "$HOST_UID:$HOST_GID" /home/${USERNAME}

LABEL org.opencontainers.image.title="pentbox-kali" \
      org.opencontainers.image.description="pentbox — image de pentest (Debian + arsenal façon Exegol)"

USER ${USERNAME}
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/pentbox-entrypoint"]
CMD ["sleep", "infinity"]
