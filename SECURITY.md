# Security

- Remnawave Updater has **no third-party Python runtime dependencies**.
- VPS passwords are entered directly into the system OpenSSH (`ssh`) process during initial provisioning. The Python application never receives or stores them.
- The updater creates a dedicated Ed25519 key under `/etc/remnawave-updater/keys/`.
- Runtime SSH connections use the dedicated key with `IdentitiesOnly=yes` and non-interactive `BatchMode=yes`.
- SSH host keys use trust-on-first-use and are pinned in `/etc/remnawave-updater/known_hosts`.
- The Remnawave API token is stored in `/etc/remnawave-updater/config.json` with mode `600`.
- Runtime configuration and the private SSH key are intended to be readable only by root.
- The updater does not automatically rewrite Remnawave `docker-compose.yml` for major migrations.

If a server is decommissioned, remove the updater public key from that server's `authorized_keys` file.
