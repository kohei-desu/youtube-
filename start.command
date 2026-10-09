#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "先にREADMEのセットアップ手順を実行してください。"
  read -r -p "Enterで閉じます…"
  exit 1
fi
exec .venv/bin/python app.py
