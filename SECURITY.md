# Security

- VPS passwords are used only during initial SSH provisioning and are not written to disk.
- The updater creates its own Ed25519 key under `/etc/remnawave-updater/keys/`.
- SSH host keys use trust-on-first-use and are pinned in `/etc/remnawave-updater/known_hosts`.
- The Remnawave API token is stored in `/etc/remnawave-updater/config.json` with mode `600`.
- Runtime configuration is intended to be readable only by root.

If a server is decommissioned, remove the updater public key from the server's `authorized_keys` file.
