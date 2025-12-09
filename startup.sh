#!/bin/bash

# Запускаем службу PostgreSQL
service postgresql start

# Запускаем службу cron
cron -f /etc/crontab

# Держим контейнер запущенным
tail -f /dev/null