#!/usr/bin/env bash
#
# idempotent installation of additional repositories

readonly BRAVE_KEY_URL='https://brave-browser-apt-release.s3.brave.com/brave-core.asc'
readonly BRAVE_URL='https://brave-browser-apt-release.s3.brave.com/ stable main'

readonly ALBERT_STUB='http://download.opensuse.org/repositories/home:/manuelschneid3r/xUbuntu'
readonly ALBERT_URL="${ALBERT_STUB}_$(lsb_release -rs)/ /"
readonly ALBERT_KEY_URL="${ALBERT_STUB}_$(lsb_release -rs)/Release.key"

readonly R_KEY='E298A3A825C0D65DFD57CBB651716619E084DAB9'
readonly R_KEYSERVER='keyserver.ubuntu.com'
readonly R_STUB='https://cloud.r-project.org/bin/linux/ubuntu'
readonly R_URL="${R_STUB} $(lsb_release -cs)-cran40/"

readonly YARN_KEY_URL='https://dl.yarnpkg.com/debian/pubkey.gpg'
readonly YARN_URL='https://dl.yarnpkg.com/debian/ stable main'

readonly GITHUB_CLI_KEY_URL='https://cli.github.com/packages/githubcli-archive-keyring.gpg'
readonly GITHUB_CLI_URL='https://cli.github.com/packages stable main'

readonly MONGODB_KEY_URL='https://www.mongodb.org/static/pgp/server-5.0.asc'
readonly MONGODB_URL="https://repo.mongodb.org/apt/$(lsb_release -si |sed 's/.*/\L&/') $(lsb_release -sc)/mongodb-org/5.0 multiverse"

readonly RVM_KEY='7BE3E5681146FD4F1A40EDA28094BB14F4E3FBBE'
readonly RVM_KEYSERVER='hkp://pool.sks-keyservers.net'
readonly RVM_URL="http://ppa.launchpad.net/rael-gc/rvm/$(lsb_release -si |sed 's/.*/\L&/') $(lsb_release -sc) main"

readonly GOOGLE_CLOUD_SDK_KEY_URL='https://packages.cloud.google.com/apt/doc/apt-key.gpg'
readonly GOOGLE_CLOUD_SDK_URL='https://packages.cloud.google.com/apt cloud-sdk main'

readonly KUBERNETES_KEY_URL='https://packages.cloud.google.com/apt/doc/apt-key.gpg'
readonly KUBERNETES_URL='https://apt.kubernetes.io/ kubernetes-xenial main'

readonly KEYRING_DIRECTORY='/usr/share/keyrings'
readonly SOURCES_DIRECTORY='/etc/apt/sources.list.d'


# ref: https://askubuntu.com/a/30157/8698
if ! [[ $(id -u) = 0 ]]; then
   echo "The script need to be run as root." >&2
   exit 1
fi

if [[ "${SUDO_USER}" ]]; then
    real_user="${SUDO_USER}"
else
    real_user=$(whoami)
fi

######################################################################
# Add repository signed with stored pgp key
# Globals:
# Arguments:
#    repository_name - name used for key and source file
#    repository_url - url where repository is located
#    repository_key_url - url where key is located
#    keyserver_fingerprint - optional key for key server
#    is_arch_specific - optional flag for specifying architecture spec
######################################################################
function add_repository() {
    key_dest="${KEYRING_DIRECTORY}/$1-archive-keyring.gpg"
    ascii_key_head='-----BEGIN PGP PUBLIC KEY BLOCK-----'
    if [[ -z "${4-}" ]]; then
        tmpfile=$(sudo -u "${real_user}" mktemp /tmp/add-repository.XXXXXX)
        sudo -u "${real_user}" curl -fsSL "$3" \
            | sudo -u "${real_user}" tee "${tmpfile}" >/dev/null
        key_first_line=$(head -n1 "${tmpfile}" | tr -d '\r' | tr -d '\n') >/dev/null
        echo -n "${key_first_line%*($'\n'|$'\r'|$'\r\n')}" | od -A n -t x1
        echo -n "${ascii_key_head}" | od -A n -t x1
        if [[ "${key_first_line}" == "${ascii_key_head}" ]]; then
            echo "dearmor"
            sudo -u "${real_user}" gpg --dearmor --output - "${tmpfile}"\
                | tee "${key_dest}" >/dev/null
        else
            cp "${tmpfile}" "${key_dest}"
            chmod a+r "${key_dest}"
        fi
        rm "${tmpfile}"
    else
        tmpfile=$(sudo -u "${real_user}" mktemp /tmp/add-repository.XXXXXX)
        echo "$4"
        read -r -a finger_prints <<< "$4"
        sudo -u "${real_user}" gpg \
             --batch \
             --no-tty \
             --no-default-keyring \
             --keyring "${tmpfile}" \
             --keyserver "$3" \
             --recv-keys "${finger_prints[@]}" \
             >/dev/null
        cp "${tmpfile}" "${key_dest}"
        chmod a+r "${key_dest}"
        rm "${tmpfile}"
    fi
    if [[ "${5-false}" = 'true' ]]; then
        repo_cmd_suffix="deb [arch=$(dpkg-architecture -q DEB_BUILD_ARCH) "
    else
        repo_cmd_suffix="deb ["
    fi
    echo "${repo_cmd_suffix}signed-by=${key_dest}] $2" \
         | tee "${SOURCES_DIRECTORY}/$1.list" >/dev/null
}

######################################################################
# Add repository signed with stored pgp key if not already added.
# Globals:
# Arguments:
#    repository_name - name used for key and source file
#    repository_url - url where repository is located
#    repository_key_url - url where key is located
#    keyserver_fingerprint - optional key for key server
#    is_arch_specific - optional flag for specifying architecture spec
######################################################################
function idempotent_add_repository(){
    if [[ -f "${SOURCES_DIRECTORY}/$1.list" ]]; then
        echo "$1 repository already added."
    else
        add_repository "$1" "$2" "$3" "${4-""}" "${5-false}"
    fi
}

# install brave repository
idempotent_add_repository 'brave-browser' "${BRAVE_URL}" "${BRAVE_KEY_URL}" '' 'true'
idempotent_add_repository 'albert' "${ALBERT_URL}" "${ALBERT_KEY_URL}"
idempotent_add_repository 'r-4' "${R_URL}" "${R_KEYSERVER}" "${R_KEY}"
idempotent_add_repository 'yarn' "${YARN_URL}" "${YARN_KEY_URL}"
idempotent_add_repository 'rvm' "${RVM_URL}" "${RVM_KEYSERVER}" "${RVM_KEY}"
idempotent_add_repository 'google-cloud-sdk' "${GOOGLE_CLOUD_SDK_URL}" "${GOOGLE_CLOUD_SDK_KEY_URL}"
idempotent_add_repository 'github-cli' "${GITHUB_CLI_URL}" "${GITHUB_CLI_KEY_URL}" '' 'true'
idempotent_add_repository 'mongodb' "${MONGODB_URL}" "${MONGODB_KEY_URL}" '' 'true'
