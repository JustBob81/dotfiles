#!/usr/bin/env bash
#
# idempotent installation of non-package software

if [ -d ~/.emacs.d ]; then
    echo 'emacs configuration - already installed'
else
    git clone https://github.com/purcell/emacs.d.git ~/.emacs.d
fi

if [ -d ~/.fzf ]; then
    echo 'fzf - already downloaded.'
else
    git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
fi

if command -v fzf &> /dev/null; then
    echo 'fzf - already installed.'
else
    ~/.fzf/install
fi

if command -v calibre &> /dev/null; then
   echo 'calibre - already installed.'
else
    wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh \
        | sh /dev/stdin
fi

if command -v pipx &> /dev/null; then
   echo 'pipx - already installed.'
else
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
fi

if command -v yamllint &> /dev/null; then
    echo 'yamllint - already installed.'
else
    pipx install yamllint
fi

if [ -d ~/.antigen ]; then
    echo 'antigen - already installed.'
else
    curl -L git.io/antigen.zsh
fi

if [ -d ~/.renv ]; then
    echo 'renv-installer - already installed.'
else
    git clone https://github.com/jcrodriguez1989/renv-installer.git ~/.renv
fi


if [ -d ~/.pyenv ]; then
    echo 'pyenv - already installed'
else
    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
fi

if [ -d ~/.tmux ]; then
    echo 'tmux configuration - already installed'
else
    git clone https://github.com/gpakosz/.tmux.git ~/.tmux
    ln -s -f ~/.tmux/.tmux.conf ~/.tmux.conf
    cp ~/.tmux/.tmux.conf.local ~/.tmux.conf.local
fi

if [ -d ~/.nvm ]; then
    echo 'nvm already installed'
else
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.37.2/install.sh \
        | bash
fi

if [ -d ~/.krew ]; then
    echo 'krew already installed.'
else
    set -x
    cd "$(mktemp -d)" \
        && OS="$(uname | tr '[:upper:]' '[:lower:]')" \
        && ARCH="$(uname -m \
        | sed -e 's/x86_64/amd64/' \
        -e 's/\(arm\)\(64\)\?.*/\1\2/' \
        -e 's/aarch64$/arm64/')" \
        && curl -fsSLO "https://github.com/kubernetes-sigs/krew/releases/latest/download/krew.tar.gz" \
        && tar zxvf krew.tar.gz \
        && KREW=./krew-"${OS}_${ARCH}" \
        && "$KREW" install krew
    set +x
fi

if kubectl plugin list | grep -q krew; then
    kubectl krew update
    kubectl krew install ctx
    kubectl krew install ns
    kubectl krew upgrade
fi
