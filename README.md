<div align="center">

# 🌊 Remnawave Updater

**Удобный CLI для обновления Remnawave Panel, Nodes и Subscription Page.**

[![Language RU](https://img.shields.io/badge/README-Русский-blue)](README.md)
[![Language EN](https://img.shields.io/badge/README-English-lightgrey)](README_EN.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Без Web UI · Русский / English · SSH-ключи · Последовательное обновление нод

</div>

> Проект не является официальным компонентом Remnawave. Перед обновлением major-версий всегда проверяйте официальный changelog.

## ✨ Что умеет

- обновлять **Remnawave Panel**;
- получать список нод напрямую из **Remnawave API**;
- обновлять **все ноды** или только выбранные;
- обновлять ноды **строго по очереди**, а не одновременно;
- проверять контейнер и подключение ноды после обновления;
- обновлять **Subscription Page** локально или на отдельном VPS;
- создавать backup перед обновлением;
- не хранить пароли от VPS;
- работать на русском и английском языках;
- пропускать любые ноды при первоначальной настройке и добавить их позже.

## 🖥️ Как выглядит логика

```text
Remnawave Updater

1. Обновить Panel
2. Обновить Nodes
3. Обновить Subscription Page
4. Статус
5. Настройки
6. Выход
```

В меню нод:

```text
1. Обновить все настроенные ноды
2. Выбрать ноды
3. Назад
```

При первом запуске программа получает ноды из Panel API и спрашивает для каждой:

```text
Настроить SSH для ноды «Germany» (185.10.10.10)? [Y/n]
```

Нажмите `n`, чтобы **пропустить ноду**. Она не попадёт в список обновления. Позже её можно добавить через `Настройки → Синхронизировать ноды`.

## 🔐 Как работает SSH

При первом подключении к VPS программа спрашивает:

```text
SSH username [root]:
SSH port [22]:
SSH password:
```

Пароль используется **только один раз**. Updater создаёт отдельный Ed25519 SSH-ключ и добавляет его в `authorized_keys` на сервере.

После этого обновления выполняются по ключу. **Пароли VPS на диск не записываются.** SSH host key после первого подключения закрепляется в отдельном `known_hosts`.

Файлы:

```text
/etc/remnawave-updater/config.json
/etc/remnawave-updater/keys/id_ed25519
/etc/remnawave-updater/known_hosts
```

Конфигурация и приватный ключ доступны только root.

## 📦 Установка

### Требования

- Ubuntu / Debian;
- установленный Remnawave Panel;
- Docker + Docker Compose plugin;
- root / sudo;
- API token Remnawave Panel;
- SSH-доступ к VPS с нодами.

### 1. Скачайте проект

После загрузки этого репозитория на свой GitHub:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/remnawave-updater.git
cd remnawave-updater
```

Или просто распакуйте скачанный ZIP и перейдите в каталог проекта.

### 2. Запустите установку

```bash
sudo ./install.sh
```

Installer установит системные Python-зависимости и сразу откроет мастер настройки.

Если мастер пока запускать не нужно:

```bash
sudo ./install.sh --no-setup
```

Затем:

```bash
sudo remnawave-updater setup
```

## ⚙️ Первоначальная настройка

1. Выберите `Русский` или `English`.
2. Введите URL Remnawave Panel.
3. Вставьте API token.
4. Updater проверит API и автоматически получит список нод.
5. Для каждой нужной ноды подтвердите настройку SSH.
6. Ненужные ноды можно пропустить через `n`.
7. Выберите, где установлена Subscription Page:
   - на сервере Panel;
   - на другом VPS;
   - не используется.

После этого достаточно запускать:

```bash
sudo remnawave-updater
```

## 🔄 Как проходит обновление

Updater придерживается рекомендуемого Remnawave порядка: сначала **Panel**, затем **Nodes**. Для каждого компонента используется официальный подход `docker compose pull` → перезапуск compose → health check.

Для нод обновление выполняется последовательно:

```text
Node 1 → pull → restart → health check → Panel API check
                         ↓
Node 2 → pull → restart → health check → Panel API check
                         ↓
Node 3 → ...
```

Если нода не обновилась, по умолчанию дальнейшая очередь останавливается, чтобы одна проблема не затронула остальные серверы.

### ⚠️ Major-обновления

Updater **не переписывает `docker-compose.yml` автоматически**. Это специально сделано для безопасности.

Некоторые major-релизы Remnawave требуют ручных изменений compose/config. Например, при переходе между major-тегами может понадобиться изменить Docker image tag. Перед такими обновлениями проверьте официальный changelog:

- https://docs.rw/install/upgrading/
- https://f.docs.rw/

## 💾 Backups

Перед обновлением Panel сохраняются:

- `.env`;
- `docker-compose.yml`;
- PostgreSQL dump, если его удалось создать.

Локальные backups:

```text
/var/backups/remnawave-updater/
```

Для удалённых Nodes / Subscription Page backup конфигурации создаётся на соответствующем VPS:

```text
/var/backups/remnawave-updater/
```

> Backup создаётся как страховка. Автоматическое восстановление базы не выполняется: откат миграций БД без проверки конкретного релиза может быть опаснее самого сбоя.

## 🛠️ Полезные команды

| Команда | Что делает |
|---|---|
| `sudo remnawave-updater` | открыть главное меню |
| `sudo remnawave-updater setup` | заново запустить мастер настройки |
| `sudo remnawave-updater status` | проверить Panel, Nodes и Sub Page |
| `sudo remnawave-updater sync-nodes` | найти новые ноды и предложить добавить их |
| `sudo remnawave-updater doctor` | проверить Docker, API, SSH и конфигурацию |
| `remnawave-updater --version` | показать версию |

### Обновить сам Remnawave Updater

Из каталога репозитория:

```bash
git pull
sudo ./install.sh --no-setup
```

Настройки, API token и SSH-ключ при переустановке сохраняются.

### Удаление

```bash
sudo ./uninstall.sh
```

Приложение удалится, но `/etc/remnawave-updater` и backups останутся на сервере специально, чтобы случайно не удалить ключи и резервные копии.

## 📁 Стандартные пути Remnawave

Updater рассчитан на официальную структуру установки:

```text
Panel:             /opt/remnawave
Node:              /opt/remnanode
Subscription Page: /opt/remnawave/subscription
```

Если Remnawave установлен сторонним installer-скриптом в другие каталоги, текущая версия Updater может не подойти.

## 🩺 Если что-то не работает

Сначала выполните:

```bash
sudo remnawave-updater doctor
```

Также полезны официальные команды Remnawave:

```bash
# Panel logs
cd /opt/remnawave && docker compose logs -f -t

# Node logs
docker logs -f remnanode

# Xray logs
docker exec remnanode xlogs
```

Официальная документация: https://docs.rw/

## 🔒 Безопасность

Подробнее: [SECURITY.md](SECURITY.md).

Коротко:

- VPS passwords не сохраняются;
- API token хранится root-only (`600`);
- используется отдельный SSH Ed25519 key;
- SSH host keys закрепляются после первого подключения;
- updater не пытается автоматически менять major-конфигурацию Remnawave.

## 📄 License

MIT — см. [LICENSE](LICENSE).
