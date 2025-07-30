# constants.py

import os

# Base tile size
TILE_WIDTH = 64
TILE_HEIGHT = 96
TILE_DEPTH = 6

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to shop item JSON file
ITEMS = os.path.join(BASE_DIR, "assets", "items", "shop_items.json")

# Example difficulty tuning constants (optional, if used elsewhere)
BASE_TARGET_SCORE = 500
ROUND_SCORE_MULTIPLIER = 1.15
SCORE_ROUNDING_STEP = 20
