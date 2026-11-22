# Credential and secret recovery

This document describes what should be recreated, restored, or signed into on a
new laptop. Dotfiles may declare software, directories, permissions, and lookup
configuration. It must not contain password vault exports, private SSH/GPG keys,
tokens, or decrypted authentication files. Those are restored manually from
their appropriate secure source.

## Where each secret belongs

| Data | Recovery approach | Automated setup boundary |
| --- | --- | --- |
| Website passwords and browser autofill | LastPass vault; install the Firefox extension, then sign in and complete MFA | Ansible installs the removable extension policy only; it never signs in |
| Emacs service credentials | Optional `~/.authinfo.gpg`, for services Emacs needs | Dotfiles may configure Emacs `auth-source`; the encrypted file is restored separately |
| SSH access | Prefer a new key per laptop and register its public key with each service | Ansible may create `~/.ssh`, install a reviewed `config`, and set permissions; it does not generate, upload, or copy private keys |
| GPG signing/encryption identity | Import the existing key only when continuity is required; otherwise create a new key and re-encrypt data | Never provision secret key material or passphrases from Ansible/Git |
| Codex and cloud CLI sessions | Sign in again on the new device | No token/session directories are copied or committed |

The LastPass Firefox extension comes from Mozilla Add-ons. Its installation is
declared through Firefox policy, but LastPass login and MFA are interactive
steps ([LastPass instructions](https://community.lastpass.com/kb/articles/39-install-and-log-in-to-the-lastpass-browser-extension%EF%BB%BF)).
The extension being installed does not restore browser history, cookies, or a
Firefox profile.

## Emacs `auth-source`

Emacs `auth-source` reads `~/.authinfo.gpg` by default, alongside other supported
backends ([GNU Emacs Authentication manual](https://www.gnu.org/software/emacs/manual/html_node/emacs/Authentication.html)).
Use this file only for credentials Emacs itself needs, such as a service token or
TRAMP login; keep the full website-password collection in LastPass. Treat the
unencrypted authinfo text as secret and never print it into terminal logs, shell
history, screenshots, or Git.

`~/.authinfo.gpg` needs its decryption material: a matching secret key if it is
encrypted to a public-key recipient, or the passphrase if it is symmetrically
encrypted. The GPG key used for commit signing may not have an encryption-capable
key or subkey; inspect its capabilities before relying on public-key encryption.
Choose one of these migration paths while the old laptop is still available:

1. **Preserve the GPG identity:** make a protected backup of its secret key and
   revocation certificate, store that backup separately from the encrypted
   authinfo file, and keep the key passphrase recoverable through an independent
   channel. Import and test the backup on a disposable profile before relying on
   it. GnuPG recommends protecting the secret-key backup and revocation
   certificate ([GnuPG manual](https://www.gnupg.org/gph/en/manual.pdf)).
2. **Rotate the identity:** create a new GPG key on the new laptop, decrypt the
   old authinfo file on a trusted machine, re-encrypt it to the new key, and
   verify decryption before retiring the old key. Do not put the plaintext
   intermediate in the dotfiles checkout or backup set.

For symmetric encryption, preserve and recover the file's passphrase separately
from the ciphertext; use a public-key recipient if you want key-based decryption
and multi-recipient recovery.

Back up the encrypted `~/.authinfo.gpg` ciphertext (for example, through the
reviewed IDrive backup set) and test restoring it. Keep key recovery material and
its passphrase separate from that ciphertext; losing the only decryption key
makes the file unrecoverable.

## SSH keys

For ordinary GitHub, server, and cloud access, generate a distinct SSH key on the
new laptop and add its public key to the relevant account. This avoids carrying
old private keys to every machine and makes revocation per-device. SSH-agent
handles key use; `authinfo.gpg` is not a format for private key files.

If a specific SSH identity must be preserved, transfer it only in a separately
encrypted backup, restore it manually, set the private-key file to mode `0600`
and its `.ssh` directory to `0700`, then verify the identity before deleting
temporary copies. Keep public keys, private keys, and `known_hosts` distinct:
public keys can be registered, private keys stay secret, and host keys should be
verified rather than blindly copied from an untrusted source.

The Resolute test VM used a temporary, read-only GitHub deploy key for the private
`emacs.d` clone. Remove that deploy key from GitHub and delete the VM's private
key when it is no longer needed. Never put it in the DOTFILES seed ISO.

## Fresh-machine checklist

1. Restore the dotfiles checkout and install the declared packages and tools.
2. Apply the Firefox LastPass extension policy, open Firefox, sign in to LastPass,
   and complete MFA. Confirm the extension is enabled.
3. Either create new SSH/GPG identities or restore protected key backups through
   the manual recovery path above. Register new public keys with their services.
4. Restore `~/.authinfo.gpg` ciphertext and verify Emacs can use a non-sensitive
   test credential without displaying its secret.
5. Sign in again to Codex and other cloud tools. Do not copy their local token or
   session directories from the old machine.
6. Restore a sample file from IDrive and separately confirm recovery access to
   the encryption key/passphrase needed for secret backups.

These secret-transfer steps have not yet been rehearsed on a fresh laptop. The
Resolute VM verified LastPass extension installation/use and Emacs/Codex
provisioning, but did not restore the user's GPG key, authinfo file, or long-lived
SSH identities.
