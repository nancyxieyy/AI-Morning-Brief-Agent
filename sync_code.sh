#!/bin/bash
# 把 NancysDaily 本地最新代码同步到此 repo 并推送
SRC="$(dirname "$0")/../.."
REPO="$(dirname "$0")"

cp -r $SRC/agents/morning_brief/web/templates/ $REPO/agents/morning_brief/web/templates/
cp -r $SRC/agents/morning_brief/web/static/ $REPO/agents/morning_brief/web/static/
cp $SRC/agents/morning_brief/web/main.py $REPO/agents/morning_brief/web/main.py
cp $SRC/agents/morning_brief/html_renderer.py $REPO/agents/morning_brief/html_renderer.py
cp $SRC/agents/morning_brief/run.py $REPO/agents/morning_brief/run.py
cp $SRC/configs/admin_settings.json $REPO/configs/admin_settings.json

cd $REPO
git add -A
git diff --cached --stat
read -p "确认推送？(y/n) " confirm
if [ "$confirm" = "y" ]; then
  git commit -m "sync: code update $(date +%Y-%m-%d)"
  git push origin main
fi
