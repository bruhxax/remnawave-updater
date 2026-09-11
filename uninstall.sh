#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./uninstall.sh"
  exit 1
fi

rm -f /usr/local/bin/remnawave-updater
rm -rf /opt/remnawave-updater

echo "Application removed."
echo "Config/SSH key were intentionally kept in /etc/remnawave-updater"
echo "Backups were intentionally kept in /var/backups/remnawave-updater"
echo "Remove those directories manually only if you no longer need them."
