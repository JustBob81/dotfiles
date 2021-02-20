#!/usr/bin/env bash
#
# idempotent installation of non-package software

if [ -d ~/.emacs.d ]; then
    echo "emacs configuration - already installed"
else
    git clone https://github.com/purcell/emacs.d.git ~/.emacs.d
fi

if [ -d ${ZSH} ]; then
    echo "oh-my-zsh already installed"
else
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"
fi

if [ -d ~/.antigen ]; then
    echo "antigen - already installed"
else
    curl -L git.io/antigen.zsh
fi

if [ -d ~/.renv ]; then
    echo "renv-installer - already installed"
else
    git clone https://github.com/jcrodriguez1989/renv-installer.git ~/.renv
fi


if [ -d ~/.pyenv ]; then
    echo "pyenv - already installed"
else
    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
fi

if [ -d ~/.tmux ]; then
    echo "tmux configuration - already installed"
else
    git clone https://github.com/gpakosz/.tmux.git ~/.tmux
    ln -s -f ~/.tmux/.tmux.conf ~/.tmux.conf
    cp ~/.tmux/.tmux.conf.local ~/.tmux.conf.local
fi

if [ -d ~/.nvm ]; then
    echo "nvm already installed"
else
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.37.2/install.sh \
        | bash
fi
