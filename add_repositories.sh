#!/usr/bin/env bash
#
# idempotent installation of additional repositories

readonly BRAVE_NAME='Brave Browser'
readonly BRAVE_KEY_URL='https://brave-browser-apt-release.s3.brave.com/brave-core.asc'
readonly BRAVE_KEY_DEST='/etc/apt/trusted.gpg.d/brave-browser-release.gpg'
readonly BRAVE_URL='https://brave-browser-apt-release.s3.brave.com/ stable main'
readonly BRAVE_DEST='/etc/apt/sources.list.d/brave-browser-release.list'

readonly ALBERT_NAME='Albert'
readonly ALBERT_KEY_URL='https://build.opensuse.org/projects/home:manuelschneid3r/public_key'
readonly ALBERT_KEY_DEST='/etc/apt/trusted.gpg.d/home_manuelschneid3r.gpg'
readonly ALBERT_URL='http://download.opensuse.org/repositories/home:/manuelschneid3r/xUbuntu'
readonly ALBERT_DEST='/etc/apt/sources.list.d/home:manuelschneid3r.list'

readonly R_NAME='R 4.0'
readonly R_KEY='E298A3A825C0D65DFD57CBB651716619E084DAB'
readonly R_KEYSERVER='keyserver.ubuntu.com'
readonly R_URL='https://cloud.r-project.org/bin/linux/ubuntu'

readonly YARN_NAME='Yarn'
readonly YARN_KEY_URL='https://dl.yarnpkg.com/debian/pubkey.gpg'
readonly YARN_URL='https://dl.yarnpkg.com/debian/ stable main'
readonly YARN_DEST='/etc/apt/sources.list.d/yarn.list'

readonly RVM_NAME='RVM'
readonly RVM_KEY_1='409B6B1796C275462A1703113804BB82D39DC0E3'
readonly RVM_KEY_2='7D2BAF1CF37B13E2069D6956105BD0E739499BDB'
readonly RVM_KEYSERVER='hkp://pool.sks-keyservers.net'
readonly RVM_URL='ppa:rael-gc/rvm'
readonly RVM_DEST='/etc/apt/sources.list.d/rael-gc-ubuntu-rvm-'

# install brave repository
if [[ -f "${BRAVE_DEST}" ]]; then
    echo "${BRAVE_NAME} repository already added."
else
    curl -s "${BRAVE_KEY_URL}" \
        | sudo apt-key --keyring "${BRAVE_KEY_DEST}" add - \
        & echo "deb [arch=$(dpkg-architecture -q DEB_BUILD_ARCH)] ${BRAVE_URL}" \
            | sudo tee "${BRAVE_DEST}"
fi

# install albert repository
if [[ -f "${ALBERT_DEST}" ]]; then
    echo "${ALBERT_NAME} repository already added."
else
    curl "${ALBERT_KEY_URL}" \
        | sudo apt-key add - \
        & echo "deb ${ALBERT_URL}_$(lsb_release -rs)/ /" \
            | sudo tee "${ALBERT_DEST}" \
            & curl -fsSL "${ALBERT_URL}_$(lsb_release -rs)/Release.key" \
                   | gpg --dearmor \
                   | sudo tee "${ALBERT_KEY_DEST}" > /dev/null
fi

# install R 4.0 repository
if grep -Fxq "deb ${R_URL} $(lsb_release -cs)-cran40/" '/etc/apt/sources.list'; then
    echo "${R_NAME} repository already added."
else
    apt-key adv --keyserver "${R_KEYSERVER}" --recv-keys "${R_KEY}" \
        & add-apt-repository "deb ${R_URL} $(lsb_release -cs)-cran40/"
fi

# install yarn repository
if [[ -f "${YARN_DEST}" ]]; then
    echo "${YARN_NAME} repository already added."
else
    curl -sS "${YARN_KEY_URL}" \
        | apt-key add - \
        & echo "deb ${YARN_URL}" \
            | sudo tee "${YARN_DEST}"
fi

# install rvm repository
if [[ -f "${RVM_DEST}$(lsb_release -cs).list" ]]; then
    echo "${RVM_NAME} repository already added."
else
    gpg --keyserver "${RVM_KEYSERVER}" --recv-keys "${RVM_KEY_1}" "${RVM_KEY_2}" \
        & sudo apt-add-repository -y "${RVM_URL}"
fi
