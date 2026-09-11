<div align="center">

# 🌊 Remnawave Updater

**Быстрый CLI-менеджер для обновления Remnawave Panel, Nodes и Subscription Page.**

[![Русский](https://img.shields.io/badge/README-Русский-3776AB?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/README-English-555555?style=for-the-badge)](README_EN.md)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Runtime deps](https://img.shields.io/badge/Runtime%20deps-0-success)](#-установка)

**Без Web UI · Без `apt update` · Без `pip install` · RU / EN · SSH-ключи · Sequential updates**

</div>

> [!WARNING]
> Проект не является официальным компонентом Remnawave. Перед major-обновлениями проверяйте официальный changelog и документацию Remnawave.

---

## ✨ Возможности

- обновление **Remnawave Panel**;
- автоматическое получение нод через **Remnawave API**;
- обновление **всех** или выбранных нод;
- последовательное обновление нод — строго по одной;
- health check после обновления;
- обновление **Subscription Page** локально или на отдельном VPS;
- backup перед обновлением;
- отдельный Ed25519 SSH-ключ;
- пароли VPS **не сохраняются и не передаются Python-коду**;
- русский и английский интерфейс;
- любую ноду можно пропустить во время настройки и добавить позже;
- `status`, `doctor` и синхронизация новых нод.

---

## ⚡ Быстрая установка

```bash
git clone https://github.com/bruhxax/remnawave-updater.git
cd remnawave-updater
sudo ./install.sh
```

Готово. Installer **не запускает `apt update` и ничего не устанавливает через pip**.

Он только проверяет, что на сервере уже есть необходимые системные инструменты, копирует Updater и запускает мастер настройки.

---

## 📦 Требования

На VPS с Panel должны быть:

- Linux (рекомендуется Ubuntu / Debian);
- Python **3.10+**;
- Docker + Docker Compose plugin;
- OpenSSH client: `ssh`, `ssh-keygen`;
- `root` / `sudo`;
- Remnawave Panel API token;
- SSH-доступ к VPS с нодами.

Обычно Python, Docker и OpenSSH уже присутствуют на сервере с Remnawave.

Если чего-то не хватает, installer **не трогает систему сам**, а просто покажет, какой компонент отсутствует.

Пример:

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

## ⚙️ Первоначальная настройка

После `sudo ./install.sh` мастер запускается автоматически.

1. Выберите язык:
   - 🇷🇺 Русский
   - 🇬🇧 English
2. Введите URL Remnawave Panel.
3. Вставьте API token.
4. Updater проверит API и получит список нод.
5. Для каждой ноды выберите, нужно ли добавлять её в Updater.
6. Настройте Subscription Page или пропустите её.

Для каждой найденной ноды будет запрос:

```text
Настроить SSH для ноды «Germany» (185.10.10.10)? [Y/n]
```

`Enter` / `Y` — добавить.

`n` — **пропустить**. Пропущенная нода не попадёт в список обновлений.

Позже её можно добавить:

```bash
sudo remnawave-updater sync-nodes
```

---

## 🔐 Как работает SSH

Для добавляемой ноды Updater спрашивает:

```text
SSH username [root]:
SSH port [22]:
```

После этого Updater запускает системный `ssh`. Если вход по ключу ещё не настроен, OpenSSH сам попросит пароль:

```text
root@server's password:
```

Пароль вводится **напрямую в OpenSSH**. Python-код Remnawave Updater не получает его и не сохраняет.

Updater создаёт отдельный ключ:

```text
/etc/remnawave-updater/keys/id_ed25519
```

и добавляет публичную часть на нужную VPS. Все следующие подключения выполняются по ключу.

SSH host keys закрепляются в:

```text
/etc/remnawave-updater/known_hosts
```

---

## 🖥️ Главное меню

```text
╭────────────────────────────────────────────╮
│  🌊 Remnawave Updater                      │
│  Panel, Nodes и Subscription Page          │
╰────────────────────────────────────────────╯

Главное меню

  1. Обновить Panel
  2. Обновить Nodes
  3. Обновить Subscription Page
  4. Статус
  5. Настройки
  6. Выход
```

Меню Nodes:

```text
1. Обновить все настроенные ноды
2. Выбрать ноды
3. Назад
```

---

## 🔄 Как проходит обновление

Updater придерживается официального порядка Remnawave: сначала **Panel**, затем **Nodes**.

Для обновления используется стандартная схема Remnawave:

```text
docker compose pull
        ↓
docker compose down
        ↓
docker compose up -d
        ↓
health check
```

Ноды обновляются **по очереди**:

```text
Germany      → backup → update → health check → OK
Netherlands  → backup → update → health check → OK
Estonia      → backup → update → health check → OK
```

Если одна нода не проходит проверку, массовая очередь по умолчанию останавливается.

---

## 🌐 Subscription Page

При настройке можно выбрать:

```text
1. Subscription Page на сервере Panel
2. Subscription Page на другом VPS
3. Subscription Page не используется
```

Для удалённого Sub Page SSH настраивается так же, как для нод.

---

## 💾 Backups

Перед обновлением Panel Updater сохраняет конфигурацию и пытается создать PostgreSQL dump.

```text
/var/backups/remnawave-updater/
```

Для Nodes и удалённого Subscription Page backup создаётся на соответствующем сервере.

> [!NOTE]
> Автоматический rollback базы не выполняется. Откат миграций БД без проверки конкретного релиза может быть опасным.

---

## 🛠️ Полезные команды

| Команда | Что делает |
|---|---|
| `sudo remnawave-updater` | открыть главное меню |
| `sudo remnawave-updater setup` | запустить настройку заново |
| `sudo remnawave-updater status` | проверить компоненты |
| `sudo remnawave-updater doctor` | проверить окружение, API и SSH |
| `sudo remnawave-updater sync-nodes` | найти и добавить новые ноды |
| `remnawave-updater --version` | показать версию |

### Установка без запуска мастера

```bash
sudo ./install.sh --no-setup
```

Позже:

```bash
sudo remnawave-updater setup
```

### Обновить сам Remnawave Updater

```bash
cd remnawave-updater
git pull
sudo ./install.sh --no-setup
```

Конфиг, API token и SSH-ключи сохраняются.

### Удаление

```bash
sudo ./uninstall.sh
```

`/etc/remnawave-updater` и backups специально остаются на сервере, чтобы случайно не удалить ключи и резервные копии.

---

## 🩺 Диагностика

Перед первым реальным обновлением рекомендуется выполнить:

```bash
sudo remnawave-updater doctor
```

Проверяются:

- Python;
- Docker / Docker Compose;
- OpenSSH;
- конфигурация;
- Remnawave API;
- SSH-доступ к добавленным нодам.

---

## 📁 Стандартные пути Remnawave

```text
Panel:             /opt/remnawave
Node:              /opt/remnanode
Subscription Page: /opt/remnawave/subscription
```

Updater рассчитан на официальную структуру установки.

---

## ⚠️ Major-обновления

Updater **не переписывает `docker-compose.yml` автоматически**.

Major-релизы могут требовать изменения compose, `.env`, Docker image tag или дополнительных шагов миграции.

Перед такими обновлениями проверьте:

- https://docs.rw/install/upgrading/
- https://docs.rw/

---

## 📜 Логи Remnawave

Panel:

```bash
cd /opt/remnawave
docker compose logs -f -t
```

Node:

```bash
docker logs -f remnanode
```

Xray:

```bash
docker exec remnanode xlogs
```

---

## 🔒 Безопасность

Подробнее: [SECURITY.md](SECURITY.md)

Коротко:

- VPS-пароли не сохраняются;
- пароль вводится непосредственно в системный `ssh`;
- API token хранится root-only (`600`);
- используется отдельный SSH Ed25519 key;
- SSH host keys закрепляются после первого подключения;
- major-конфигурация Remnawave автоматически не меняется.

---

## 🤝 Contribution

Pull Requests и предложения приветствуются.

Нашли баг или хотите предложить функцию — создайте [Issue](https://github.com/bruhxax/remnawave-updater/issues).

---

## 📄 License

MIT — см. [LICENSE](LICENSE).

---

<div align="center">

### 🌊 Remnawave Updater

**Simple · Fast · CLI**

[🇷🇺 Русский](README.md) · [🇬🇧 English](README_EN.md)

</div>
