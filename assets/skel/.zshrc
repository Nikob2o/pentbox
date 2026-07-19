# pentbox — zshrc minimal (étoffé aux lots suivants).
autoload -Uz compinit && compinit -u 2>/dev/null

setopt PROMPT_SUBST
PROMPT='%F{cyan}pentbox%f:%F{blue}%~%f %# '

alias ll='ls -lah --color=auto'
alias la='ls -A --color=auto'
alias l='ls -CF --color=auto'

export EDITOR=vim
export HISTSIZE=50000
export SAVEHIST=50000
export HISTFILE=~/.zsh_history
