#!/usr/bin/env bash
#
# Reconcile declared third-party repositories. Default: inspect only.
set -euo pipefail

readonly BRAVE_KEY_URL='https://brave-browser-apt-release.s3.brave.com/brave-core.asc'
readonly BRAVE_URL='https://brave-browser-apt-release.s3.brave.com/ stable main'

readonly ALBERT_STUB='http://download.opensuse.org/repositories/home:/manuelschneid3r/xUbuntu'
readonly ALBERT_URL="${ALBERT_STUB}_$(lsb_release -rs)/ /"
readonly ALBERT_KEY_URL='https://build.opensuse.org/projects/home:manuelschneid3r/signing_keys/download?kind=gpg'

readonly R_KEY='E298A3A825C0D65DFD57CBB651716619E084DAB9'
readonly R_KEYSERVER='keyserver.ubuntu.com'
readonly R_STUB='https://cloud.r-project.org/bin/linux/ubuntu'
readonly R_URL="${R_STUB} $(lsb_release -cs)-cran40/"

readonly YARN_KEY_URL='https://dl.yarnpkg.com/debian/pubkey.gpg'
readonly YARN_URL='https://dl.yarnpkg.com/debian/ stable main'

# Retained for reference; this repository is not enabled.
# shellcheck disable=SC2034
readonly GITHUB_CLI_KEY_URL='https://cli.github.com/packages/githubcli-archive-keyring.gpg'
# Retained for reference; this repository is not enabled.
# shellcheck disable=SC2034
readonly GITHUB_CLI_URL='https://cli.github.com/packages stable main'

readonly MONGODB_KEY_URL='https://www.mongodb.org/static/pgp/server-5.0.asc'
readonly MONGODB_URL="https://repo.mongodb.org/apt/$(lsb_release -si |sed 's/.*/\L&/') $(lsb_release -sc)/mongodb-org/5.0 multiverse"

readonly LLVM_KEY_URL='https://apt.llvm.org/llvm-snapshot.gpg.key'
readonly LLVM_URL="http://apt.llvm.org/$(lsb_release -sc)/ llvm-toolchain-$(lsb_release -sc) main"

readonly RVM_KEY='7BE3E5681146FD4F1A40EDA28094BB14F4E3FBBE'
readonly RVM_KEYSERVER='hkps://keyserver.ubuntu.com'
readonly RVM_URL="http://ppa.launchpad.net/rael-gc/rvm/$(lsb_release -si |sed 's/.*/\L&/') $(lsb_release -sc) main"

readonly GOOGLE_CLOUD_SDK_KEY_URL='https://packages.cloud.google.com/apt/doc/apt-key.gpg'
readonly GOOGLE_CLOUD_SDK_URL='https://packages.cloud.google.com/apt cloud-sdk main'

# Retained for reference; this repository is not enabled.
# shellcheck disable=SC2034
readonly KUBERNETES_KEY_URL='https://packages.cloud.google.com/apt/doc/apt-key.gpg'
# Retained for reference; this repository is not enabled.
# shellcheck disable=SC2034
readonly KUBERNETES_URL='https://packages.kubernetes.io/ kubernetes-xenial main'

readonly KEYRING_DIRECTORY='/usr/share/keyrings'
readonly SOURCES_DIRECTORY='/etc/apt/sources.list.d'


repository_line() {
    local name=$1 url=$2 arch_specific=${5-false} options=''
    if [[ "$arch_specific" == true ]]; then
        options="arch=$(dpkg --print-architecture) "
    fi
    printf 'deb [%ssigned-by=%s/%s-archive-keyring.gpg] %s\n' \
        "$options" "$KEYRING_DIRECTORY" "$name" "$url"
}

# Each declaration is shared by inspection and application.
repositories() {
    "$@" brave-browser "$BRAVE_URL" "$BRAVE_KEY_URL" '' true
    "$@" albert "$ALBERT_URL" "$ALBERT_KEY_URL"
    "$@" r-4 "$R_URL" "$R_KEYSERVER" "$R_KEY"
    "$@" yarn "$YARN_URL" "$YARN_KEY_URL"
    "$@" rvm "$RVM_URL" "$RVM_KEYSERVER" "$RVM_KEY"
    "$@" google-cloud-sdk "$GOOGLE_CLOUD_SDK_URL" "$GOOGLE_CLOUD_SDK_KEY_URL"
    "$@" mongodb "$MONGODB_URL" "$MONGODB_KEY_URL" '' true
    "$@" llvm "$LLVM_URL" "$LLVM_KEY_URL"
}

check_repository() {
    local expected source="$SOURCES_DIRECTORY/$1.list"
    expected=$(repository_line "$@")
    if [[ -f "$source" ]] && [[ "$(cat "$source")" == "$expected" ]]; then
        printf 'SOURCE MATCHES: %s\n' "$1"
    else
        printf 'SOURCE DIFFERS: %s\n  desired: %s\n' "$source" "$expected"
    fi
    if [[ ! -s "$KEYRING_DIRECTORY/$1-archive-keyring.gpg" ]]; then
        printf 'KEY MISSING/EMPTY: %s\n' "$1"
    fi
}

stage_repository() {
    local name=$1 fingerprint=${4-} home="$staging/$1-gnupg"
    mkdir -m 700 "$home"
    if [[ -n "$fingerprint" ]]; then
        gpg --homedir "$home" --batch --no-autostart --keyserver "$3" --recv-keys "$fingerprint"
    else
        curl --fail --silent --show-error --location \
            --connect-timeout 15 --max-time 120 \
            "$3" --output "$staging/$name.download"
        gpg --homedir "$home" --batch --no-autostart --import "$staging/$name.download"
    fi
    # Export public keys: do not copy GPG's internal keybox into APT.
    gpg --homedir "$home" --batch --no-autostart --export ${fingerprint:+"$fingerprint"} \
        > "$staging/$name.gpg"
    test -s "$staging/$name.gpg"
    gpg --homedir "$home" --batch --no-autostart --show-keys "$staging/$name.gpg" >/dev/null
    repository_line "$@" > "$staging/$name.list"
}

publish_repository() {
    local name=$1 destination
    for destination in "$KEYRING_DIRECTORY/$name-archive-keyring.gpg" "$SOURCES_DIRECTORY/$name.list"; do
        local prepared="$staging/$name.gpg"
        [[ "$destination" != *.list ]] || prepared="$staging/$name.list"
        if ! cmp -s "$prepared" "$destination"; then
            # Rename on the destination filesystem to avoid truncated files.
            install -m 644 "$prepared" "$destination.dotfiles-new"
            mv -f "$destination.dotfiles-new" "$destination"
            printf 'UPDATED: %s\n' "$destination"
        fi
    done
}

main() {
    case "${1---check}" in
        --check)
            [[ $# -le 1 ]] || return 2
            repositories check_repository
            printf '\nInspection only; keys and remote repository availability were not verified.\n'
            ;;
        --apply)
            [[ $# -eq 1 ]] || return 2
            if [[ $(id -u) != 0 ]]; then
                printf 'Application requires root. Use --check for inspection.\n' >&2
                return 1
            fi
            if [[ $(lsb_release -sc) != focal ]]; then
                printf 'Application is currently limited to Ubuntu 20.04; review repository support before migration.\n' >&2
                return 1
            fi
            local prerequisite
            for prerequisite in curl gpg install cmp dpkg; do
                command -v "$prerequisite" >/dev/null
            done
            staging=$(mktemp -d)
            trap 'rm -rf -- "$staging"' EXIT
            # All downloads and key validation must succeed before any live writes.
            repositories stage_repository
            install -d -m 755 "$KEYRING_DIRECTORY" "$SOURCES_DIRECTORY"
            repositories publish_repository
            printf 'Repositories reconciled. No package refresh or upgrade was run.\n'
            ;;
        *) printf 'Usage: %s [--check|--apply]\n' "$0" >&2; return 2 ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
