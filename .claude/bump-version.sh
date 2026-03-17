#!/bin/bash
# デザインファイル（CSS/JS/HTMLテンプレート）編集時にバージョン番号をインクリメント
# 対象: static/sw.js の VERSION と config/settings.py の STATIC_VERSION

FILE=$(jq -r '.tool_input.file_path // ""')

# 対象パターン: static/**/*.css, static/**/*.js (sw.js除く), stockdiary/templates/**/*.html
if echo "$FILE" | grep -qE '/static/.+\.(css|js)$|/stockdiary/templates/.+\.html$' && \
   ! echo "$FILE" | grep -q '/sw\.js$'; then

  SW=/home/user/stock-dialy/static/sw.js
  PY=/home/user/stock-dialy/config/settings.py

  VER=$(grep -oP "(?<=const VERSION = ')[0-9]+\.[0-9]+\.[0-9]+" "$SW")
  if [ -n "$VER" ]; then
    PATCH=$(echo "$VER" | cut -d. -f3)
    NEW=$(echo "$VER" | sed "s/\.[0-9]*$/.$((PATCH+1))/")
    sed -i "s/const VERSION = '$VER'/const VERSION = '$NEW'/" "$SW" && \
    sed -i "s/STATIC_VERSION = '$VER'/STATIC_VERSION = '$NEW'/" "$PY"
  fi
fi
