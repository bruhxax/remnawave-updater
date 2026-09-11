<div align="center">

# 🌊 Remnawave Updater

**A convenient CLI updater for Remnawave Panel, Nodes and Subscription Page.**

[![Language RU](https://img.shields.io/badge/README-Русский-lightgrey)](README.md)
[![Language EN](https://img.shields.io/badge/README-English-blue)](README_EN.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

No Web UI · Russian / English · SSH keys · Sequential node updates

</div>

> This project is not an official Remnawave component. Always review the official changelog before major-version upgrades.

## ✨ Features

- updates **Remnawave Panel**;
- discovers nodes directly from the **Remnawave API**;
- updates **all configured nodes** or selected nodes only;
- updates nodes **sequentially**, never all at once;
- checks the node container and Panel connection after each update;
- supports a local or remote **Subscription Page**;
- creates backups before updates;
- never stores VPS passwords;
- Russian and English UI;
- lets you skip any node during setup and add it later.

## 🖥️ Main menu

```text
Remnawave Updater

1. Update Panel
2. Update Nodes
3. Update Subscription Page
4. Status
5. Settings
6. Exit
```

Node menu:

```text
1. Update all configured nodes
2. Select nodes
3. Back
```

During the first setup, the updater gets nodes from the Panel API and asks:

```text
Configure SSH for node “Germany” (185.10.10.10)? [Y/n]
```

Press `n` to **skip the node**. It will not be added to the update list. You can add it later with `Settings → Sync nodes from Panel`.

## 🔐 SSH model

On the first connection the updater asks for:

```text
SSH username [root]:
SSH port [22]:
SSH password:
```

The password is used **once** to install a dedicated Ed25519 public key. VPS passwords are **never written to disk**.

Files:

```text
/etc/remnawave-updater/config.json
/etc/remnawave-updater/keys/id_ed25519
/etc/remnawave-updater/known_hosts
```

The configuration and private key are root-only. SSH server keys are pinned after first use.

## 📦 Installation

### Requirements

- Ubuntu / Debian;
- Remnawave Panel already installed;
- Docker + Docker Compose plugin;
- root / sudo;
- Remnawave Panel API token;
- SSH access to node VPS servers.

### 1. Clone the repository

After uploading this project to your GitHub account:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/remnawave-updater.git
cd remnawave-updater
```

You can also download the ZIP, extract it and enter the project directory.

### 2. Install

```bash
sudo ./install.sh
```

The installer installs the required system Python packages and launches the setup wizard.

Install without launching setup:

```bash
sudo ./install.sh --no-setup
```

Then run:

```bash
sudo remnawave-updater setup
```

## ⚙️ Initial setup

1. Choose `Русский` or `English`.
2. Enter the Remnawave Panel URL.
3. Paste the API token.
4. The updater validates the API and automatically discovers nodes.
5. Configure SSH for each node you want to manage.
6. Skip unwanted nodes with `n`.
7. Select where Subscription Page is installed:
   - on the Panel server;
   - on another VPS;
   - not used.

After setup, simply run:

```bash
sudo remnawave-updater
```

## 🔄 Update process

The updater follows Remnawave's recommended order: **Panel first, then Nodes**. Components use the official `docker compose pull` → compose restart → health-check flow.

Nodes are updated one at a time:

```text
Node 1 → pull → restart → health check → Panel API check
                         ↓
Node 2 → pull → restart → health check → Panel API check
                         ↓
Node 3 → ...
```

If a node fails, the queue stops by default so one broken update does not affect the rest of the fleet.

### ⚠️ Major upgrades

The updater intentionally **does not rewrite `docker-compose.yml` automatically**.

Some major Remnawave releases require manual compose/config changes. Always check:

- https://docs.rw/install/upgrading/
- https://f.docs.rw/

## 💾 Backups

Before a Panel update the updater saves:

- `.env`;
- `docker-compose.yml`;
- a PostgreSQL dump when available.

Local backups:

```text
/var/backups/remnawave-updater/
```

Remote Node / Subscription Page configuration backups are stored on the corresponding VPS under the same path.

> Backups are created as a safety net. Database rollback is intentionally not automated because blindly reversing migrations can make a failed upgrade worse.

## 🛠️ Useful commands

| Command | Purpose |
|---|---|
| `sudo remnawave-updater` | open the main menu |
| `sudo remnawave-updater setup` | run setup again |
| `sudo remnawave-updater status` | check Panel, Nodes and Sub Page |
| `sudo remnawave-updater sync-nodes` | discover and configure new nodes |
| `sudo remnawave-updater doctor` | check Docker, API, SSH and config |
| `remnawave-updater --version` | show version |

### Update Remnawave Updater itself

From the repository directory:

```bash
git pull
sudo ./install.sh --no-setup
```

Runtime configuration, API token and SSH keys are preserved.

### Uninstall

```bash
sudo ./uninstall.sh
```

The application is removed, while `/etc/remnawave-updater` and backups are intentionally preserved.

## 📁 Supported Remnawave layout

The current version targets the official installation paths:

```text
Panel:             /opt/remnawave
Node:              /opt/remnanode
Subscription Page: /opt/remnawave/subscription
```

Custom third-party installation layouts may require changes.

## 🩺 Troubleshooting

Start with:

```bash
sudo remnawave-updater doctor
```

Useful official commands:

```bash
# Panel logs
cd /opt/remnawave && docker compose logs -f -t

# Node logs
docker logs -f remnanode

# Xray logs
docker exec remnanode xlogs
```

Official documentation: https://docs.rw/

## 🔒 Security

See [SECURITY.md](SECURITY.md).

In short: passwords are not stored, the API token is root-only, a dedicated Ed25519 key is used, SSH host keys are pinned, and major-version configuration is never modified automatically.

## 📄 License

MIT — see [LICENSE](LICENSE).
