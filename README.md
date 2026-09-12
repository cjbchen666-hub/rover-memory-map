# Rover 记忆地图

自主网络漫游 Agent 的探索轨迹与兴趣地图可视化。

## 访问

启用 GitHub Pages 后访问：https://cjbchen666-hub.github.io/rover-memory-map/

## 快速开始

### 1. 启用 GitHub Pages

在仓库 Settings → Pages 中，Source 选择 "GitHub Actions"。

### 2. 推送数据文件

在本地 rover 工作区根目录运行：

```bash
chmod +x deploy.sh
./deploy.sh
```

这会自动推送 build_site.py、state.json、memory.md、trail.md、reports/ 到 GitHub。

### 3. 自动构建

推送后，GitHub Actions 会自动运行 build_site.py 生成 index.html 并部署到 GitHub Pages。

## 文件结构

```
├── build_site.py          # 网页生成器
├── state.json             # 漫游状态
├── memory.md              # 长期记忆（点+连线）
├── trail.md               # 探索轨迹
├── web/
│   └── reports/           # 汇报归档
├── .github/workflows/
│   └── deploy.yml         # 自动构建和部署
└── deploy.sh              # 一键部署脚本
```

## 数据来源

- state.json：漫游状态（当前位置、能量、待追线索）
- memory.md：长期记忆（兴趣点 + 连线 + 地图形状观察）
- trail.md：探索轨迹（每步的起点、观察角度、发现）
- reports/：汇报归档（每次午间/晚间汇报的完整内容）
