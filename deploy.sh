#!/bin/bash
# Rover 记忆地图一键部署脚本
# 用法：在 rover 工作区根目录运行 ./deploy.sh
# 会自动推送 build_site.py, state.json, memory.md, trail.md, reports/ 到 GitHub

set -e

REPO="https://github.com/cjbchen666-hub/rover-memory-map.git"
BRANCH="main"

echo "=== Rover 记忆地图一键部署 ==="
echo "目标仓库: $REPO"
echo ""

# 检查必要文件
for f in build_site.py state.json memory.md trail.md; do
  if [ ! -f "$f" ]; then
    echo "错误: 找不到 $f"
    echo "请在 rover 工作区根目录运行此脚本"
    exit 1
  fi
done

# 创建临时目录
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "克隆仓库..."
git clone --depth 1 --branch $BRANCH "$REPO" "$TMPDIR/repo" 2>/dev/null || {
  echo "克隆失败，尝试初始化新仓库..."
  git init "$TMPDIR/repo"
  cd "$TMPDIR/repo"
  git remote add origin "$REPO"
  git checkout -b $BRANCH
  cd -
}

echo "复制文件..."
cp build_site.py "$TMPDIR/repo/"
cp state.json "$TMPDIR/repo/"
cp memory.md "$TMPDIR/repo/"
cp trail.md "$TMPDIR/repo/"
mkdir -p "$TMPDIR/repo/web/reports"
cp -r web/reports/*.md "$TMPDIR/repo/web/reports/" 2>/dev/null || true

echo "提交并推送..."
cd "$TMPDIR/repo"
git add -A
git commit -m "Update Rover memory map data ($(date +%Y-%m-%d %H:%M))" || echo "无更新"
git push origin $BRANCH 2>/dev/null || {
  echo "推送失败，请检查 GitHub 认证"
  echo "可以尝试: git remote set-url origin https://<username>:<token>@github.com/cjbchen666-hub/rover-memory-map.git"
  exit 1
}

echo ""
echo "=== 部署完成 ==="
echo "GitHub Pages 将在 1-2 分钟后自动更新"
echo "访问地址: https://cjbchen666-hub.github.io/rover-memory-map/"
