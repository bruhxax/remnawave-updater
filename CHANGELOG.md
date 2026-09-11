# Changelog

## 0.3.0 — 2026-09-11

- Redesigned the terminal interface with a consistent blue theme, cards and bordered menus.
- The screen is cleared before the main menu and major interactive sections.
- Added animated spinners for API checks, SSH checks, status checks and every update stage.
- Added a main dashboard with Panel, Nodes and Subscription Page state/version information.
- Added live latest-version checks against the official Remnawave GitHub repositories.
- Panel installed version is read from `/api/system/metadata`.
- Node installed versions are read directly from Remnawave Panel API node metadata.
- Subscription Page version is detected from the running container/startup logs when the Docker tag is not a fixed SemVer tag.
- Status view now shows Installed / Latest / Update state for every configured component.
- Update progress now animates backup, Docker pull, restart and health-check stages.
- Added version parsing/comparison tests.

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
