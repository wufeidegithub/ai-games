"""公共常量：窗口、配色、帧率。

配色遵循「深色底 + 高对比前景」，所有游戏共用一套，保证视觉统一。
"""

# ---------- 窗口 ----------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 640
FPS = 60

# ---------- 网格 ----------
CELL_SIZE = 24
GRID_COLS = 20
GRID_ROWS = 20
GRID_WIDTH = CELL_SIZE * GRID_COLS
GRID_HEIGHT = CELL_SIZE * GRID_ROWS

# ---------- 配色（RGB）----------
COLOR_BG = (24, 26, 32)            # 主背景
COLOR_PANEL = (34, 37, 45)         # 面板底色
COLOR_GRID = (44, 48, 58)          # 网格线
COLOR_TEXT = (232, 234, 240)       # 主文字
COLOR_TEXT_DIM = (140, 146, 160)   # 次要文字
COLOR_ACCENT = (86, 182, 255)      # 强调色（高亮 / 选中）
COLOR_DANGER = (255, 92, 92)       # 警示 / 游戏结束

# 方块配色，贪吃蛇和俄罗斯方块共用
BLOCK_COLORS = [
    (86, 182, 255),    # 蓝
    (126, 217, 87),    # 绿
    (255, 199, 89),    # 黄
    (255, 138, 101),   # 橙
    (186, 140, 255),   # 紫
    (255, 121, 158),   # 粉
    (94, 224, 202),    # 青
]

# ---------- 字体 ----------
FONT_NAME = None      # None 表示用 pygame 默认字体
FONT_SIZE_SMALL = 18
FONT_SIZE_NORMAL = 24
FONT_SIZE_LARGE = 40
FONT_SIZE_TITLE = 56

# ---------- 游戏注册信息 ----------
# 主菜单里显示的顺序
GAME_ORDER = ["snake", "tetris"]


def grid_to_pixel(col: int, row: int) -> tuple[int, int]:
    """网格坐标 -> 像素坐标（左上角原点）。"""
    return col * CELL_SIZE, row * CELL_SIZE
