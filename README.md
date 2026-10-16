# ai-games

用 AI 辅助编写的小游戏合集，同一批游戏做了 **Python 桌面版** 和 **网页版** 两套实现，
便于对比两种技术路线在代码结构、渲染方式、输入处理上的差异。

仓库里还顺手放了一个独立小工具，见下方[附带工具](#附带工具live-wallpaper)。

## 目录结构

```
ai-games/
├── python/                 Python 桌面版（pygame）
│   ├── main.py             游戏选择器（统一入口）
│   ├── requirements.txt
│   ├── common/
│   │   └── settings.py     窗口尺寸、配色、帧率等公共常量
│   ├── games/
│   │   ├── __init__.py     游戏注册表
│   │   ├── snake.py        贪吃蛇
│   │   └── tetris.py       俄罗斯方块
│   └── assets/
│       ├── images/         图片素材
│       ├── sounds/         音效素材
│       └── fonts/          字体
├── web/                    网页版（HTML5 Canvas）
│   ├── index.html          游戏大厅
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── common.js       公共工具：循环、键盘、分数
│   │   ├── snake.js        贪吃蛇
│   │   └── tetris.js       俄罗斯方块
│   └── assets/
│       └── images/
├── tools/
│   └── live-wallpaper/     附带工具：每日换壁纸 + 动态壁纸（Windows，纯标准库）
└── docs/                   设计笔记
```

## 两套实现怎么选

| 对比项 | Python 版 | 网页版 |
|---|---|---|
| 运行方式 | 需要装 Python + pygame | 双击 html 即可，零依赖 |
| 分享给别人 | 得让对方装环境 | 发个链接就能玩 |
| 性能上限 | 高（本地渲染） | 中（受浏览器限制） |
| 调试体验 | 好，断点直接调 | 靠 DevTools |
| 手机能玩 | 不能 | 能 |

## 快速开始

### Python 版

```bash
cd python
pip install -r requirements.txt
python main.py
```

### 网页版

直接用浏览器打开 `web/index.html` 即可。

如果要用本地服务器（推荐，避免某些浏览器对 `file://` 的限制）：

```bash
cd web
python -m http.server 8000
# 浏览器访问 http://localhost:8000
```

## 操作方式

| 游戏 | 操作 |
|---|---|
| 贪吃蛇 | 方向键 / WASD 控制方向，空格暂停，R 重开 |
| 俄罗斯方块 | ← → 移动，↑ 旋转，↓ 加速下落，空格直接落下，P 暂停 |

## 附带工具：live-wallpaper

`tools/live-wallpaper/` 是一个独立的 Windows 小工具，和游戏没有直接关系，只是顺手放在同一个仓库里。

| 模块 | 文件 | 做什么 | 是否常驻 |
|---|---|---|---|
| 每日换壁纸 | `wallpaper_daily.py` | 每天自动换一张**静态**壁纸（必应每日一图 / Picsum / 本地文件夹） | 否（定时触发一次即退出） |
| 动态壁纸 | `live_wallpaper.py` | 桌面上跑**动画**（极光流彩 / 等离子波纹 / 星空穿梭 / 照片慢推） | 是（后台常驻进程） |

两个模块都**只用 Python 标准库 + Win32 API**，不需要 `pip install` 任何东西。

一分钟上手：

1. 双击 `change_now.bat` —— 立刻换一张，先看效果
2. 双击 `install_startup.bat` —— 以后每次开机自动检查，今天没换过就换一张
3. 想让电脑长时间不关机也能每天换，再双击 `install_task.bat`（默认每天 09:00 触发）

动态壁纸则是 `python live_wallpaper.py --start`，想看效果图可以直接看目录里的 `_preview_*.png`。

> 完整说明（三种图源、命令行参数、原理、还原方法）见 [`tools/live-wallpaper/README.md`](tools/live-wallpaper/README.md)。

## 后续计划

- [ ] 更多游戏：打砖块、2048、扫雷
- [ ] 游戏内最高分本地存储
- [ ] 网页版加排行榜
