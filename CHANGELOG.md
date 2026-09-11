# Changelog

## 0.3.2 — 2026-09-11

- Nodes that already run the latest Remnawave Node version are now skipped before backup, Docker pull and restart.
- Node version pre-check first uses Remnawave Panel API and falls back to the remote container when needed.
- If latest-version lookup is unavailable, Updater keeps the safe old behavior and performs the update instead of incorrectly skipping it.
- Confirmation input is more tolerant of RU/EN keyboard layouts and no longer repeats the same question after an invalid key.

## 0.3.1 — 2026-09-11

- Added the short global `updater` command; it can be launched from any directory.
- Installer now detects an existing `/etc/remnawave-updater/config.json` and keeps the saved Panel URL/API token instead of running the setup wizard again.
- Reinstall/update keeps Panel URL, API token, node SSH settings and generated SSH keys.
- Uninstall still keeps `/etc/remnawave-updater` intentionally, including Panel credentials and SSH configuration.

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
