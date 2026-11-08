# Laptop configuration and recovery

## Step 1: make configuration changes reviewable

The default `./install` now applies user dotfile links only. It does not add
repositories, install packages, upgrade the system, or run non-package installers.
Shell errors are visible. The original combined configuration is preserved in
`legacy-system-install.conf.yaml` for inventory/reference only. Do not run it:
its shell commands continue after failures and include broad package upgrades.

Inspect declared repositories without root or network access:

```sh
./add_repositories.sh --check
```

This compares source definitions and checks for missing/empty key files. It does
not establish remote availability, key freshness, or successful APT refreshes.
At the initial assessment, four live sources differed: Albert, R, RVM, LLVM
(Bionic vs Focal). They are now disabled; see [the repaired APT baseline](apt-baseline.md).

Do not run `sudo ./add_repositories.sh --apply` against the repaired baseline:
its declarations still include the four sources deliberately disabled during
repair. Update repository policy before enabling application again. It reconciles existing managed
source files and keys. All keys are downloaded/imported/exported into an isolated
GPG home and validated before any live files are changed. Failed downloads or
invalid keys stop the script. Changed files are replaced individually by rename;
this is not a transaction across all files if a filesystem write fails.

Application is limited to Focal until repository compatibility is reviewed for
the next release. This is a transitional repair, not the final Ansible setup.
Repository endpoints, MongoDB version policy, expired/revoked keys, duplicate
sources outside the managed filenames, and the existing toolchain PPA still need
review before application. The helper no longer implicitly enables the toolchain
test PPA or triggers its automatic APT refresh. Existing PPA settings are untouched.
The previous Kubernetes and GitHub declarations remain inactive.

Validation:

```sh
bash -n add_repositories.sh
shellcheck add_repositories.sh
python3 tests/test_repositories.py
```

## Verified checkpoints

- IDrive account login and backup location were restored. A manual backup reported
  431,637 files considered, 183,086 uploaded, and zero failures.
- A downloaded copy of `docs/recovery-plan.md` had the same SHA-256 hash as the
  original. This verifies that file, not every backed-up file or full recovery.
- APT refresh completes without warnings after disabling the unavailable partner
  source and four sources for the wrong Ubuntu release.
- The Bionic Python 3.8 packages were replaced with matching Focal ESM packages.
  System Python imports `apt` successfully.
- Pending updates, including GDB and Samba libraries, were installed. The user
  verified `sudo apt-get check` succeeds and `dpkg --audit` produces no output.

Backup coverage, unattended backup execution, independent credential recovery,
and a second copy of irreplaceable data still need verification. Repository and
application inventory remains necessary before building the Ansible configuration.

## Remaining work, in order

1. Verify IDrive selection, recent runs, exclusions, recovery credentials, and
   restore representative recent and versioned files to a separate location.
   Make a second copy of irreplaceable data before package repair or reinstall.
2. Inventory intended applications and services; review third-party endpoints
   against vendor instructions. Resolve current APT refresh failures explicitly.
3. Repair the installed Bionic Python 3.8 packages using a simulated and reviewed
   coordinated transaction, then complete pending updates. Do not remove Python
   blindly or change `/usr/bin/python3` manually.
4. Introduce Ansible roles for repositories, selected packages, services,
   security/update policy, user configuration, backups, and hardware differences.
   Keep Dotbot for links initially. Separate desktop essentials from optional
   databases, containers, language tools, and large applications such as TeX.
5. Resolve disk-space pressure, firmware refresh failures, Postfix configuration,
   Brother scanner rules, and remaining Bluetooth issues. Verify firewall and
   Livepatch state from an unrestricted local terminal.
6. Choose a supported Ubuntu LTS after VM and live-USB validation. Test the setup
   on a clean installation and repeat it to check for unexpected changes.
7. Document data/secret restoration and manual steps. Demonstrate recovery before
   reinstalling this laptop. Adopt Autoinstall only after the setup is reliable.

Configuration in Git, encrypted data backups, and independently recoverable
credentials are separate requirements. None substitutes for the others.
