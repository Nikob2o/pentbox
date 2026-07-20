# pentbox — zshrc minimal (étoffé aux lots suivants).
autoload -Uz compinit && compinit -u 2>/dev/null

# Édition de ligne façon emacs + flèches liées à l'historique. Sans ça,
# EDITOR=vim bascule ZLE en mode vi et les flèches insèrent des caractères au
# lieu de parcourir l'historique. On lie les deux variantes de séquences
# (curseur normal ^[[A et mode application ^[OA) + terminfo → robuste, y
# compris sous asciinema.
bindkey -e
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey '^[[A' up-line-or-beginning-search
bindkey '^[[B' down-line-or-beginning-search
bindkey '^[OA' up-line-or-beginning-search
bindkey '^[OB' down-line-or-beginning-search
zmodload zsh/terminfo 2>/dev/null
[[ -n "${terminfo[kcuu1]}" ]] && bindkey "${terminfo[kcuu1]}" up-line-or-beginning-search
[[ -n "${terminfo[kcud1]}" ]] && bindkey "${terminfo[kcud1]}" down-line-or-beginning-search

# Historique.
export HISTSIZE=50000
export SAVEHIST=50000
export HISTFILE=~/.zsh_history
setopt SHARE_HISTORY HIST_IGNORE_DUPS HIST_IGNORE_SPACE

setopt PROMPT_SUBST
PROMPT='%F{cyan}pentbox%f:%F{blue}%~%f %# '

alias ll='ls -lah --color=auto'
alias la='ls -A --color=auto'
alias l='ls -CF --color=auto'

export EDITOR=vim

# Personnalisation utilisateur — appliquée À CHAUD depuis my-resources (partagé
# entre toutes les missions), sans rebuild. Édite côté host :
#   ~/.local/share/pentbox/my-resources/zsh/zshrc
[[ -f /opt/my-resources/zsh/zshrc ]] && source /opt/my-resources/zsh/zshrc

# Templates de commandes chargés dans l'historique (↑ / Ctrl-R) : défauts bakés
# + tes modèles perso dans my-resources/history (à chaud). Lignes vides/# ignorées.
_pentbox_load_templates() {
  local f tmp
  for f in /opt/pentbox/history-templates /opt/my-resources/history; do
    [[ -r $f ]] || continue
    tmp=$(mktemp) || continue
    grep -vE '^[[:space:]]*(#|$)' "$f" > "$tmp" 2>/dev/null
    fc -R "$tmp"
    rm -f "$tmp"
  done
}
_pentbox_load_templates
unfunction _pentbox_load_templates 2>/dev/null
