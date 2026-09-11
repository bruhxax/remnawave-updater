<div align="center">

# 🌊 Remnawave Updater

**A fast CLI update manager for Remnawave Panel, Nodes and Subscription Page.**

[![Русский](https://img.shields.io/badge/README-Русский-555555?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/README-English-3776AB?style=for-the-badge)](README_EN.md)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Runtime deps](https://img.shields.io/badge/Runtime%20deps-0-success)](#-installation)

**No Web UI · No `apt update` · No `pip install` · RU / EN · SSH keys · Sequential updates**

</div>

> [!WARNING]
> This project is not an official Remnawave component. Always review the official Remnawave changelog and documentation before major upgrades.

---

## ✨ Features

- update **Remnawave Panel**;
- automatically discover nodes through the **Remnawave API**;
- update **all** or selected nodes;
- update nodes strictly one by one;
- run health checks after updates;
- update **Subscription Page** locally or on a separate VPS;
- create backups before updates;
- use a dedicated Ed25519 SSH key;
- VPS passwords are **never stored or passed to Python code**;
- Russian and English interface;
- skip any node during setup and add it later;
- `status`, `doctor` and node synchronization commands.

---

## ⚡ Quick installation

```bash
git clone https://github.com/bruhxax/remnawave-updater.git
cd remnawave-updater
sudo ./install.sh
```

The installer **does not run `apt update` and does not install anything through pip**.

It only checks the required system tools, copies Remnawave Updater and launches setup.

---

## 📦 Requirements

The Panel VPS needs:

- Linux (Ubuntu / Debian recommended);
- Python **3.10+**;
- Docker + Docker Compose plugin;
- OpenSSH client: `ssh`, `ssh-keygen`;
- `root` / `sudo`;
- Remnawave Panel API token;
- SSH access to node VPS servers.

If anything is missing, the installer does **not** modify the OS automatically. It simply reports what is missing.

```text
[1/3] Checking requirements...
  ✓ python3
  ✓ docker
  ✓ ssh
  ✓ ssh-keygen
  ✓ docker compose

[2/3] Installing Remnawave Updater...
[3/3] Done.
  ✓ No apt update
  ✓ No pip install
  ✓ No third-party Python packages
```

---

## ⚙️ Initial setup

After `sudo ./install.sh`, setup starts automatically.

1. Choose 🇷🇺 Russian or 🇬🇧 English.
2. Enter the Remnawave Panel URL.
3. Paste the API token.
4. Updater validates the API and discovers nodes.
5. Choose which nodes should be managed.
6. Configure or skip Subscription Page.

For every node:

```text
Configure SSH for node “Germany” (185.10.10.10)? [Y/n]
```

Press `Enter` / `Y` to add it, or `n` to skip it.

Skipped nodes can be added later:

```bash
sudo remnawave-updater sync-nodes
```

---

## 🔐 SSH model

For a managed node, Updater asks for:

```text
SSH username [root]:
SSH port [22]:
```

Then Updater launches the system `ssh` client. If key authentication is not configured yet, OpenSSH asks for the VPS password directly.

Updater never receives or stores that password.

The dedicated private key is stored at:

```text
/etc/remnawave-updater/keys/id_ed25519
```

SSH host keys are pinned in:

```text
/etc/remnawave-updater/known_hosts
```

---

## 🖥️ Main menu

```text
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

---

## 🔄 Update flow

The updater follows Remnawave's recommended order: **Panel first, then Nodes**.

```text
docker compose pull
        ↓
docker compose down
        ↓
docker compose up -d
        ↓
health check
```

Nodes are updated sequentially. If one node fails, the bulk queue stops by default.

---

## 💾 Backups

Backups are stored under:

```text
/var/backups/remnawave-updater/
```

Panel backups include configuration and an attempted PostgreSQL dump. Remote node and Subscription Page configuration backups are created on their own VPS servers.

---

## 🛠️ Useful commands

| Command | Purpose |
|---|---|
| `sudo remnawave-updater` | open the main menu |
| `sudo remnawave-updater setup` | run setup again |
| `sudo remnawave-updater status` | show component status |
| `sudo remnawave-updater doctor` | check environment, API and SSH |
| `sudo remnawave-updater sync-nodes` | discover and add new nodes |
| `remnawave-updater --version` | show version |

Install without launching setup:

```bash
sudo ./install.sh --no-setup
```

Update Remnawave Updater itself:

```bash
cd remnawave-updater
git pull
sudo ./install.sh --no-setup
```

Uninstall:

```bash
sudo ./uninstall.sh
```

Runtime configuration and backups are intentionally preserved.

---

## 📁 Standard Remnawave paths

```text
Panel:             /opt/remnawave
Node:              /opt/remnanode
Subscription Page: /opt/remnawave/subscription
```

---

## ⚠️ Major upgrades

Remnawave Updater intentionally **does not rewrite `docker-compose.yml`**.

Major releases may require compose, `.env`, image tag or migration changes. Check:

- https://docs.rw/install/upgrading/
- https://docs.rw/

---

## 🔒 Security

See [SECURITY.md](SECURITY.md).

In short: VPS passwords are entered directly into system OpenSSH, the API token and private key are root-only, SSH host keys are pinned, and major configuration is never rewritten automatically.

---

## 🤝 Contribution

Pull Requests and suggestions are welcome. Found a bug or have an idea? Open an [Issue](https://github.com/bruhxax/remnawave-updater/issues).

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

### 🌊 Remnawave Updater

**Simple · Fast · CLI**

[🇷🇺 Русский](README.md) · [🇬🇧 English](README_EN.md)

</div>
