# pentbox — image « blackarch » (base BlackArch/Arch, arsenal via pacman).
#
# Contrairement à kali (Debian, où impacket/netexec passent par pipx), BlackArch
# package nativement quasi tout l'arsenal — y compris netexec et impacket — donc
# tout s'installe via pacman, sans pipx ni toolchain Rust.
#
# Assets communs (entrypoint, pentbox-shell, dotfiles) partagés avec kali :
# le wrapper est agnostique, seule la couche paquets change.
# UID/GID de l'host injectés → pas de fichiers root:root dans le workspace.
FROM blackarchlinux/blackarch:latest

ARG HOST_UID=1000
ARG HOST_GID=1000
ARG USERNAME=pentbox

ENV LANG=C.UTF-8 \
    PENTBOX_USER=${USERNAME}

# --- Système à jour (keyrings d'abord) + arsenal (pacman) ------------------ #
# Arch = rolling : upgrade complet obligatoire (pas de partial upgrade).
RUN pacman -Sy --noconfirm --needed archlinux-keyring blackarch-keyring \
    && pacman -Syu --noconfirm --needed \
         ca-certificates curl wget git sudo openssh \
         zsh tmux vim less which asciinema ncurses \
         iproute2 iputils bind whois openbsd-netcat socat tcpdump net-snmp openldap smbclient \
         python python-pip python-pipx \
         nmap masscan hydra medusa john hashcat sqlmap wfuzz gobuster whatweb dnsrecon proxychains-ng nikto \
         impacket netexec certipy mitm6 coercer enum4linux-ng python-ldapdomaindump \
    && pacman -Scc --noconfirm

# --- Utilisateur non-root (UID/GID alignés sur l'host) --------------------- #
RUN groupadd -g "$HOST_GID" "$USERNAME" \
    && useradd -m -u "$HOST_UID" -g "$HOST_GID" -s /usr/bin/zsh "$USERNAME" \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/pentbox \
    && chmod 0440 /etc/sudoers.d/pentbox \
    && mkdir -p /workspace && chown "$HOST_UID:$HOST_GID" /workspace

# --- Assets communs (identiques à kali) ------------------------------------ #
COPY assets/skel/ /home/${USERNAME}/
COPY assets/entrypoint.sh /usr/local/bin/pentbox-entrypoint
COPY assets/pentbox-shell /usr/local/bin/pentbox-shell
RUN chmod +x /usr/local/bin/pentbox-entrypoint /usr/local/bin/pentbox-shell \
    && chown -R "$HOST_UID:$HOST_GID" /home/${USERNAME}

LABEL org.opencontainers.image.title="pentbox-blackarch" \
      org.opencontainers.image.description="pentbox — image de pentest (BlackArch, arsenal pacman)"

USER ${USERNAME}
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/pentbox-entrypoint"]
CMD ["sleep", "infinity"]
