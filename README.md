# ai-games

用 AI 辅助编写的小游戏合集，同一批游戏做了 **Python 桌面版** 和 **网页版** 两套实现，
便于对比两种技术路线在代码结构、渲染方式、输入处理上的差异。

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

## 后续计划

- [ ] 更多游戏：打砖块、2048、扫雷
- [ ] 游戏内最高分本地存储
- [ ] 网页版加排行榜
