# Changelog

## 0.2.0 — 2026-09-11

- Removed `rich` and `paramiko` runtime dependencies.
- Removed automatic `apt-get update` / `apt-get install` from the installer.
- Installer now performs a fast prerequisite check only.
- Replaced Paramiko with the system OpenSSH client.
- Initial key provisioning now uses the system `ssh` client directly; passwords are entered into OpenSSH and never reach Python code.
- Added a lightweight built-in ANSI CLI UI using only the Python standard library.
- Added Python/OpenSSH version and availability checks to `doctor`.
- Updated RU/EN README and installation instructions.
- CI no longer installs project/runtime Python packages to run tests.

## 0.1.0 — 2026-09-11

- Initial bilingual RU/EN CLI.
- Panel API setup and automatic node discovery.
- Per-node skip during initial setup.
- Password used only for first SSH-key installation; passwords are never stored.
- Sequential updates for all or selected nodes.
- Local or remote Subscription Page support.
- Config/database backups before Panel updates and config backups for Nodes/Sub Page.
- Status, node sync and doctor commands.
