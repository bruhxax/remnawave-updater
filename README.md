<div align="center">

# 🌊 Remnawave Updater

**Удобный CLI-менеджер для обновления Remnawave Panel, Nodes и Subscription Page.**

[![Русский](https://img.shields.io/badge/README-Русский-3776AB?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/README-English-555555?style=for-the-badge)](README_EN.md)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Без Web UI · Русский / English · SSH-ключи · Последовательное обновление нод**

</div>

> [!WARNING]
> Проект не является официальным компонентом Remnawave.  
> Перед major-обновлениями всегда проверяйте официальный changelog Remnawave.

---

## ✨ Возможности

- обновление **Remnawave Panel**;
- автоматическое получение списка нод через **Remnawave API**;
- обновление **всех** или только выбранных нод;
- последовательное обновление нод — по одной;
- health check после обновления каждой ноды;
- обновление **Subscription Page**;
- поддержка Sub Page на сервере Panel или отдельном VPS;
- backup конфигурации перед обновлением;
- SSH-доступ по отдельному Ed25519-ключу;
- пароли VPS **не сохраняются**;
- русский и английский интерфейс;
- возможность пропустить ненужные ноды;
- синхронизация новых нод после первоначальной настройки;
- диагностика Panel, API, Docker и SSH.

---

## 🖥️ Главное меню

```text
╭──────────────────────────────╮
│      Remnawave Updater       │
╰──────────────────────────────╯

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

## 🚀 Установка

### Требования

- Ubuntu / Debian;
- Remnawave Panel;
- Docker + Docker Compose Plugin;
- `root` или `sudo`;
- API Token Remnawave;
- SSH-доступ к VPS с нодами.

### Скачать проект

```bash
git clone https://github.com/bruhxax/remnawave-updater.git
cd remnawave-updater
```

### Установить

```bash
sudo ./install.sh
```

После установки автоматически запустится первоначальная настройка.

Если мастер настройки пока запускать не нужно:

```bash
sudo ./install.sh --no-setup
```

Позже его можно запустить вручную:

```bash
sudo remnawave-updater setup
```

---

## ⚙️ Первоначальная настройка

При первом запуске:

1. Выберите язык:
   - 🇷🇺 Русский
   - 🇬🇧 English

2. Введите URL Remnawave Panel.

3. Вставьте API Token.

4. Updater проверит подключение к API.

5. Список нод будет получен автоматически.

6. Для каждой ноды появится запрос:

```text
Настроить SSH для ноды «Germany» (185.10.10.10)? [Y/n]
```

Нажмите:

```text
Enter / Y
```

чтобы добавить ноду.

Или:

```text
n
```

чтобы **пропустить её**.

Пропущенная нода не будет участвовать в обновлениях.

Позже её можно добавить командой:

```bash
sudo remnawave-updater sync-nodes
```

---

## 🔐 SSH

Для каждой добавляемой ноды Updater попросит:

```text
SSH username [root]:
SSH port [22]:
SSH password:
```

Если используется стандартный пользователь `root`, просто нажмите:

```text
Enter
```

То же самое для стандартного SSH-порта `22`.

### Пароль не сохраняется

SSH-пароль используется только при первоначальной настройке.

Updater создаёт отдельный:

```text
Ed25519 SSH key
```

и добавляет его public key в:

```text
~/.ssh/authorized_keys
```

После этого подключения выполняются по ключу.

Пароли VPS на диск **не записываются**.

---

## 🔄 Обновление нод

Ноды обновляются **строго по очереди**, а не одновременно:

```text
Germany
   ↓
Backup
   ↓
docker compose pull
   ↓
Restart
   ↓
Health check
   ↓
✓ OK

Netherlands
   ↓
...
```

Если health check не проходит, дальнейшее массовое обновление останавливается.

Это снижает вероятность одновременного падения всех VPN-нод.

---

## 🌐 Subscription Page

Во время первоначальной настройки можно выбрать:

```text
1. Subscription Page находится на сервере Panel
2. Subscription Page находится на другом VPS
3. Subscription Page не используется
```

Если Sub Page расположен на другом сервере, SSH настраивается так же, как для Nodes.

---

## 💾 Backup

Перед обновлениями сохраняются важные файлы конфигурации.

### Panel

Backup хранится в:

```text
/var/backups/remnawave-updater/
```

Могут сохраняться:

```text
.env
docker-compose.yml
PostgreSQL dump
```

### Nodes / Subscription Page

Backup конфигурации создаётся непосредственно на соответствующем VPS:

```text
/var/backups/remnawave-updater/
```

> [!NOTE]
> Автоматический rollback базы данных специально не выполняется.  
> Миграции между версиями могут отличаться, поэтому восстановление БД безопаснее выполнять вручную после проверки конкретного релиза.

---

## 🛠️ Полезные команды

| Команда | Назначение |
|---|---|
| `sudo remnawave-updater` | открыть главное меню |
| `sudo remnawave-updater setup` | запустить настройку заново |
| `sudo remnawave-updater status` | проверить компоненты |
| `sudo remnawave-updater doctor` | диагностика Docker, API, SSH и конфигурации |
| `sudo remnawave-updater sync-nodes` | найти и добавить новые ноды |
| `remnawave-updater --version` | показать версию |

---

## 🩺 Диагностика

Перед первым обновлением рекомендуется выполнить:

```bash
sudo remnawave-updater doctor
```

Updater проверит:

- конфигурацию;
- Remnawave API;
- Docker;
- Panel;
- SSH-доступ;
- настроенные Nodes;
- Subscription Page.

---

## 🔃 Обновление Remnawave Updater

Перейдите в каталог проекта:

```bash
cd remnawave-updater
```

Получите последнюю версию:

```bash
git pull
```

И переустановите CLI:

```bash
sudo ./install.sh --no-setup
```

Ваш конфиг, API Token и SSH-ключи сохранятся.

---

## 🗑️ Удаление

```bash
sudo ./uninstall.sh
```

После удаления данные:

```text
/etc/remnawave-updater/
/var/backups/remnawave-updater/
```

автоматически не удаляются.

Это сделано специально, чтобы случайно не потерять конфигурацию, SSH-ключи и backups.

---

## 📁 Стандартные пути

Updater рассчитан на стандартную структуру Remnawave:

```text
Panel:
 /opt/remnawave

Node:
 /opt/remnanode

Subscription Page:
 /opt/remnawave/subscription
```

Если компоненты установлены в нестандартные каталоги, текущая версия Updater может работать некорректно.

---

## ⚠️ Major-обновления

Remnawave Updater **не изменяет `docker-compose.yml` автоматически при major-миграциях**.

Некоторые крупные обновления могут требовать:

- изменения Docker image tag;
- изменения `.env`;
- изменения `docker-compose.yml`;
- дополнительных migration-шагов.

Перед major-обновлением обязательно проверьте:

**Remnawave Upgrade Guide:**  
https://docs.rw/install/upgrading/

**Remnawave Documentation:**  
https://docs.rw/

---

## 📜 Логи Remnawave

### Panel

```bash
cd /opt/remnawave
docker compose logs -f -t
```

### Node

```bash
docker logs -f remnanode
```

### Xray

```bash
docker exec remnanode xlogs
```

---

## 🔒 Безопасность

Подробнее:

[SECURITY.md](SECURITY.md)

Основные принципы:

- VPS-пароли не сохраняются;
- API Token хранится с root-only правами;
- используется отдельный SSH Ed25519 key;
- SSH host keys сохраняются в отдельный `known_hosts`;
- приватный SSH-ключ доступен только root;
- major-конфигурация Remnawave не изменяется автоматически.

Файлы Updater:

```text
/etc/remnawave-updater/config.json
/etc/remnawave-updater/keys/id_ed25519
/etc/remnawave-updater/known_hosts
```

---

## 🤝 Contribution

Pull Requests и предложения приветствуются.

Если нашли баг или хотите предложить функцию:

**GitHub Issues:**  
https://github.com/bruhxax/remnawave-updater/issues

---

## 📄 License

Проект распространяется под лицензией **MIT**.

Подробнее:

[LICENSE](LICENSE)

---

<div align="center">

### 🌊 Remnawave Updater

Simple. Safe. CLI.

[🇷🇺 Русский](README.md) · [🇬🇧 English](README_EN.md)

</div>
