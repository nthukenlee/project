from pathlib import Path

INTERNAL_WIDTH = 1280
INTERNAL_HEIGHT = 720
WINDOW_SCALE = 1
WINDOW_SIZE = (INTERNAL_WIDTH * WINDOW_SCALE, INTERNAL_HEIGHT * WINDOW_SCALE)
FPS = 60

TILE = 32
MAP_COLS = 160
MAP_ROWS = 112
WORLD_WIDTH = MAP_COLS * TILE
WORLD_HEIGHT = MAP_ROWS * TILE

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
I18N_DIR = DATA_DIR / "i18n"

COLORS = {
    "ink": (34, 37, 49),
    "cream": (246, 231, 181),
    "paper": (255, 248, 218),
    "grass": (74, 139, 73),
    "grass_light": (91, 160, 83),
    "grass_dark": (53, 111, 63),
    "road": (177, 169, 145),
    "road_edge": (126, 121, 108),
    "water": (55, 133, 171),
    "water_light": (82, 171, 194),
    "brick": (174, 90, 66),
    "roof": (119, 58, 57),
    "window": (137, 201, 204),
    "white": (255, 255, 255),
    "gold": (245, 194, 66),
    "teal": (47, 133, 126),
    "purple": (101, 76, 145),
    "red": (191, 64, 61),
    "shadow": (28, 51, 45),
}

FONT_CANDIDATES = ["Microsoft JhengHei", "Noto Sans CJK TC", "Arial Unicode MS", "Arial"]

SAVE_VERSION = 2
APP_FOLDER = "NTHUPixelAdventure"
