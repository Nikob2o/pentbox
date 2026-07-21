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

# --- Bureau graphique (XFCE + VNC + noVNC), activé à la demande par --desktop  #
RUN pacman -S --noconfirm --needed \
      xfwm4 xfdesktop xfce4-panel xfce4-terminal xfce4-session xfce4-settings \
      tigervnc novnc dbus xorg-server xorg-xinit ttf-dejavu firefox materia-gtk-theme \
    && pacman -Scc --noconfirm

# --- VPN (OpenVPN + WireGuard) --------------------------------------------- #
# wireguard-go = implémentation userspace : wg-quick bascule dessus quand le
# module noyau wireguard n'est pas exposé au conteneur → aucun modprobe requis
# côté hôte, le tunnel monte avec /dev/net/tun + NET_ADMIN.
# Absent des dépôts Arch/BlackArch (AUR only) → compilé depuis les sources avec
# Go, toolchain purgé dans le MÊME layer (comme NetExec/rustup côté kali).
RUN pacman -S --noconfirm --needed openvpn wireguard-tools go \
    && git clone --depth 1 https://git.zx2c4.com/wireguard-go /tmp/wg-go \
    && ( cd /tmp/wg-go && go build -o /usr/bin/wireguard-go . ) \
    && pacman -Rns --noconfirm go \
    && rm -rf /tmp/wg-go /root/.cache/go-build \
    && pacman -Scc --noconfirm

# --- Wordlists (SecLists complet + rockyou décompressé au chemin standard) -- #
# Paquet natif seclists (→ /usr/share/seclists). Wordlists PERSO : volume `resources`.
RUN pacman -S --noconfirm --needed seclists && pacman -Scc --noconfirm \
    && mkdir -p /usr/share/wordlists \
    && ln -sf /usr/share/seclists /usr/share/wordlists/seclists \
    && rk=/usr/share/seclists/Passwords/Leaked-Databases \
    && if [ -f "$rk/rockyou.txt.tar.gz" ]; then \
           tar -xf "$rk/rockyou.txt.tar.gz" -C /usr/share/wordlists/ \
           && ln -sf /usr/share/wordlists/rockyou.txt "$rk/rockyou.txt"; \
       elif [ -f "$rk/rockyou.txt" ]; then \
           ln -sf "$rk/rockyou.txt" /usr/share/wordlists/rockyou.txt; \
       fi

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

LABEL org.opencontainers.image.title="pentbox-blackarch" \
      org.opencontainers.image.description="pentbox — image de pentest (BlackArch, arsenal pacman)"

USER ${USERNAME}
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/pentbox-entrypoint"]
CMD ["sleep", "infinity"]
