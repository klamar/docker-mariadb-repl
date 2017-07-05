#!/usr/bin/env bash

(python /data/repl/repl.py >/dev/stdout 2>&1 &)

exec /bin/bash /usr/local/bin/docker-entrypoint.sh mysqld
