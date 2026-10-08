"""游戏选择器 —— 统一入口。

    python main.py            打开菜单
    python main.py snake      直接启动贪吃蛇
"""

import sys
from pathlib import Path

# 让 python main.py 能直接 import common / games
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pygame  # noqa: E402

from common.settings import (  # noqa: E402
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PANEL,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    GAME_ORDER,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from games import load_games  # noqa: E402


def draw_menu(screen: pygame.Surface, fonts: dict, games: dict, selected: int) -> None:
    screen.fill(COLOR_BG)

    title = fonts["title"].render("AI 游戏合集", True, COLOR_TEXT)
    screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 90)))

    hint = fonts["small"].render("↑ ↓ 选择    Enter 开始    Esc 退出", True, COLOR_TEXT_DIM)
    screen.blit(hint, hint.get_rect(center=(WINDOW_WIDTH // 2, 145)))

    y = 230
    for i, key in enumerate(GAME_ORDER):
        info = games.get(key)
        if info is None:
            continue

        active = i == selected
        box = pygame.Rect(120, y - 14, WINDOW_WIDTH - 240, 96)
        pygame.draw.rect(screen, COLOR_PANEL, box, border_radius=10)
        pygame.draw.rect(
            screen,
            COLOR_ACCENT if active else COLOR_PANEL,
            box,
            width=2,
            border_radius=10,
        )

        name_color = COLOR_ACCENT if active else COLOR_TEXT
        prefix = "▸ " if active else "  "
        name = fonts["normal"].render(prefix + info["title"], True, name_color)
        screen.blit(name, (box.x + 24, box.y + 18))

        desc = fonts["small"].render(info["description"], True, COLOR_TEXT_DIM)
        screen.blit(desc, (box.x + 24, box.y + 56))

        y += 120


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("AI 游戏合集")
    clock = pygame.time.Clock()

    fonts = {
        "title": pygame.font.Font(None, FONT_SIZE_TITLE),
        "normal": pygame.font.Font(None, FONT_SIZE_NORMAL),
        "small": pygame.font.Font(None, FONT_SIZE_SMALL),
    }

    games = load_games()

    # 命令行直接进某个游戏
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key not in games:
            print(f"未知游戏: {key}，可选: {', '.join(games)}")
            return 1
        games[key]["run"]()
        pygame.quit()
        return 0

    selected = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(GAME_ORDER)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(GAME_ORDER)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    games[GAME_ORDER[selected]]["run"]()
                    # 从游戏返回后重建窗口，防止尺寸被改
                    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

        draw_menu(screen, fonts, games, selected)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
