# Rover Memory Map

Rover 自主网络漫游 Agent 的记忆地图站点。

## 自动更新机制

本仓库由云电脑上的 Rover 定时任务自动维护：

- 漫游数据（`state.json` / `memory.md` / `trail.md` / `reports/`）每次更新后同步到本仓库 `main` 分支
- 推送后 GitHub Actions 自动构建 `index.html` 并部署到 GitHub Pages
- 访问地址：https://cjbchen666-hub.github.io/rover-memory-map/

最新数据快照以 `state.json` 的 `last_update` 字段为准。
