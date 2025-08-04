import datetime
import sys
import os
import random
from typing import List, Tuple
import pandas as pd;
import matplotlib.pyplot as plt
import pygame
import time
import math
import json
import traceback
import logging
from logging.handlers import RotatingFileHandler
from shop import Shop
from encounterengine import EncounterEngine
from action_bar import ActionBar
from item_description import ItemDescriptionCard
name = "Curiosima"
def get_base_dir():
    if getattr(sys, 'frozen', False):
        # If bundled by PyInstaller or similar
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
log_file = "game.log"

# Rotating file handler
file_handler = RotatingFileHandler(log_file, maxBytes=512 * 1024, backupCount=5)
file_handler.setFormatter(log_formatter)

# Optional: also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Log uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

logger.info("Logging initialized")


from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QMenu, QAction
)
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer, QEvent, Qt
from PyQt5.QtGui import QPixmap, QImage
from PyQt5 import QtGui, QtCore
from matplotlib import cm
from matplotlib.colors import Normalize

from assets.fx.particle import SmokeParticle, SparkleParticle, FireParticle, WindParticle, \
    SelectedParticle, ComboBand, SelectedParticle_B
from music import MusicManager


TILES_ROOT = "./assets/tiles/classic"
BG_ROOT = "./assets/bg"
ITEMS = "./assets/items/shop_items.json"
TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
MAX_ROWS = 6
MAX_COLS = 18
PAIR_COUNT = 32
STACK_HEIGHT = 6
NUM_ROWS = 6
ACTION_BAR_HEIGHT = 80
WIDTH = 1000
HEIGHT = 1000


tile_particle_map = {
    "death": SmokeParticle,
    "fool": SparkleParticle,
    "sun": FireParticle,
    "moon": SparkleParticle,
    "devil": FireParticle,
}

class MahjongGame(QWidget):
    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle("Mahjong Pygame + Qt5")
            self.setMouseTracking(True)
            self.setGeometry(100, 100, HEIGHT, WIDTH)
            self.ACTION_BAR_HEIGHT = 80
            self.debug = False
            self.base_score = 5

            self.show_booster_selector = False
            self.booster_history = []
            self.booster_choices = []  # List of 7 tiles
            self.booster_selected_indices = set()  # Set of clicked indices (max 3)
            self.show_booster_selector = False
            self.selected_booster_tiles = []
            self.booster_pack_cost = 75

            self.encounter_engine = EncounterEngine(self)
            self.in_shop = False
            self.in_game_over = False
            self.game_over_button_rect = pygame.Rect(80, 400, 200, 40)  # Same size as shop_continue
            self.game_over_flash_toggle = True
            self.last_flash_time = pygame.time.get_ticks()
            self.flash_interval = 500  # milliseconds

            self.base_rarity_weights = {
                "Common": 60,
                "Uncommon": 30,
                "Rare": 8,
                "Epic": 2
            }

            self.board = []
            self.current_column_order = None
            self.booster_pool = []
            # self.shop = Shop(self)
            self.tile_positions = {}
            self.selected_tiles = []
            self.animating_tiles = []
            self.fading_matched_tiles = []

            self.animating_tiles = []
            self.fading_matched_tiles = []
            self.animating_coords = set()
            self.fading_coords = set()
            self.top_tiles = {}

            self.matched_pairs = {}
            self.wallet = 0
            self.score = 0
            self.inventory = []
            self.round_number = 1
            self.match_count = 0
            self.tile_match_count = {}  # e.g., {"Tower": 2, "Moon": 1}
            self.combo_multiplier = 1


            self.selected_inventory_index = {}
            self.hovered_inventory_index = None

            # For UI tracking
            self.button_rects = {}
            self.dragging_volume = False
            self.music_volume = 0.25


            self.particles = []
            self.fuse_particles = []
            cmap = cm.get_cmap("inferno").reversed()
            self.fuse_gradient = [tuple(int(c * 255) for c in cmap(i / 20)[:3]) for i in range(20)]

            # Combo timer
            self.combo_fuse_x = 50
            self.combo_fuse_y = 50
            self.combo_fuse_total_width = 200
            self.combo_fuse_height = 16

            self.reroll_price = 50
            self.reroll_base_price = 50  # Use this to reset later


            self.combo_timer = QTimer()
            self.combo_timer.setInterval(10000)
            self.combo_timer.timeout.connect(self.reset_combo_timer)
            self.combo_display_start = 0
            self.combo_display_duration = 10000  # 10 seconds, in ms

            self.combo_level = 1  # Multiplier: x1 to x5
            self.combo_points = 0  # 0 to 5
            self.combo_bands = []  # Holds fuse particle data for each level
            self.combo_max_level = 5
            self.combo_required_per_level = 5

            print("[INIT] Combo timer connected.")

            self.combo_label = QLabel("", self)
            self.combo_label.setStyleSheet("color: gold; font-size: 24px; font-weight: bold;")
            self.combo_label.move(100, 50)  # Adjust as needed
            self.combo_label.hide()

            self.combo_display_text = ""
            self.combo_display_time = 0


            self.combo_anim = QPropertyAnimation(self.combo_label, b"pos")
            self.combo_anim.setDuration(500)
            self.combo_anim.setEasingCurve(QEasingCurve.OutBounce)

            self.last_match_time = None
            self.encounter_mode = None
            self.encounter_trigger_in = 5
            self.action_bar_top = self.height() - ACTION_BAR_HEIGHT  # Adjust as needed
            self.available_encounters = [
                "west_wind", "east_wind", "south_wind", "north_wind",
                "crush", "parallax", "slot_machine", "rotate_cw", "rotate_ccw",
                "fog of war"
            ]

            self.available_encounters_bu = []

            pygame.init()
            try:
                pygame.mixer.init()
                self.music_manager = MusicManager("assets/music/")
                self.music_manager.play_current()
                self.music_manager.set_volume(self.music_volume)
            except pygame.error as e:
                print(f"[ERROR] Could not initialize mixer: {e}")
                # Optional: set fallback or disable music

            self.dragging_volume_slider = False
            self.setMouseTracking(True)

            pygame.display.set_mode((1, 1), pygame.HIDDEN)
            self.icon_images = {
                "prev": pygame.image.load("assets/icons/prev_track.png").convert_alpha(),
                "next": pygame.image.load("assets/icons/next_track.png").convert_alpha(),
                "volume": pygame.image.load("assets/icons/volume_icon.png").convert_alpha()
            }
            bg_path = os.path.join(BG_ROOT, "bg.png")
            pygame.font.init()

            for event in pygame.event.get():
                self.music_manager.handle_event(event)

            self.match_sound = pygame.mixer.Sound(os.path.join("assets", "sfx", "ignite.wav"))
            self.match_sound = pygame.mixer.Sound(os.path.join("assets", "sfx", "church-bell-toll.mp3"))
            self.match_sound.set_volume(1)  # Optional

            OldeEnglishRegular = os.path.join("assets", "fonts", "OldeEnglishRegular-Zd2J.ttf")
            Aveschon = os.path.join("assets", "fonts", "Aveschon.otf")
            FacultyGlyphicRegular = os.path.join("assets", "fonts", "FacultyGlyphic-Regular.ttf")
            MerchantVF = os.path.join("assets", "fonts", "MerchantVF.ttf")
            vergilia = os.path.join("assets", "fonts", "vergilia.ttf")
            self.font_title = pygame.font.Font(vergilia, 36)
            self.font_body = pygame.font.Font(FacultyGlyphicRegular, 20)
            self.combo_font = pygame.font.Font(vergilia, 36)  # 36pt size
            self.gui_font = pygame.font.Font(FacultyGlyphicRegular, 20)  # 36pt size
            self.button_font_2 = pygame.font.Font(OldeEnglishRegular, 32)  # Smaller than combo_font
            self.button_font = pygame.font.Font(vergilia, 32)  # Smaller than combo_font

            self.money_font = pygame.font.Font(FacultyGlyphicRegular, 25)  # Smaller than combo_font
            self.item_font = pygame.font.Font(vergilia, 25)  # Smaller than combo_font

            self.background_tile = pygame.image.load(bg_path).convert()
            self.bg_scroll_x = 0
            self.bg_scroll_y = 0
            self.bg_scroll_speed_x = 1  # Adjust as needed
            self.bg_scroll_speed_y = 1


            self.surface = pygame.Surface((1500, 900))

            self.tile_images = {}
            self.load_tileset_images()
            self.target_score = self.calculate_target_score()

            self.action_bar = ActionBar(self)

            self.init_shop()
            self.item_card = ItemDescriptionCard(self.font_title, self.font_body)
            self.init_ui()

            self.timer = QTimer()
            self.timer.timeout.connect(self.update_canvas)
            self.timer.timeout.connect(self.tick)  # This will call tick() every 30 ms
            self.timer.start(30)


            self.new_game()
        except Exception as e:
            print("[FATAL ERROR IN __init__]:", e)
            traceback.print_exc()

    def init_shop(self):
        self.shop_selected_item_index = None
        self.shop_message = ""
        self.shop_items = []

    def init_ui(self):
        self.button_contexts = {
            "prev_track": "global",
            "next_track": "global",
            "volume_slider": "global",
            "shop_continue": "shop",
            "inventory_0": "inventory",
            "inventory_1": "inventory",
            "inventory_2": "inventory",
            "inventory_3": "inventory",
            "inventory_4": "inventory",
        }

        layout = QVBoxLayout()

        self.score_label = QLabel(f"Score: {self.score}")
        layout.addWidget(self.score_label)

        self.wallet_label = QLabel(f"Wallet: {self.wallet}")
        layout.addWidget(self.wallet_label)

        self.encounter_label = QLabel("Encounter: None")
        layout.addWidget(self.encounter_label)

        self.match_counter_label = QLabel("")
        layout.addWidget(self.match_counter_label)

        btns = QHBoxLayout()
        new_game_btn = QPushButton("New Game")
        new_game_btn.clicked.connect(self.start_new_game)
        btns.addWidget(new_game_btn)

        debug_score = QPushButton("Add 100 Score")
        debug_score.clicked.connect(lambda: self.modify_score("Debug", 100))
        btns.addWidget(debug_score)

        end_round = QPushButton("End Round")
        # end_round.clicked.connect(self.start_new_round)
        end_round.clicked.connect(self.update_game_state)
        btns.addWidget(end_round)

        go_to_shop = QPushButton("Go to Shop")
        go_to_shop.clicked.connect(self.enter_shop_screen)
        btns.addWidget(go_to_shop)

        trigger_encounter = QPushButton("Trigger Encounter")
        trigger_encounter.clicked.connect(self.trigger_encounter_effect)
        btns.addWidget(trigger_encounter)

        # Create a QMenu for the right-click context
        encounter_menu = QMenu(trigger_encounter)

        # Dictionary of possible encounter modes
        encounter_options = {
            "West Wind": "west_wind",
            "East Wind": "east_wind",
            "North Wind": "north_wind",
            "South Wind": "south_wind",
            "Slot Machine": "slot_machine",
            "Rotate CW": "rotate_cw",
            "Rotate CCW": "rotate_ccw",
            "Parallax": "parallax",
            "Crush": "crush",
            "None": None
        }

        # Populate the menu
        for label, value in encounter_options.items():
            action = encounter_menu.addAction(label)
            action.triggered.connect(lambda checked, v=value: self.set_encounter_mode(v))

        # Override contextMenuEvent
        trigger_encounter.setContextMenuPolicy(Qt.CustomContextMenu)
        trigger_encounter.customContextMenuRequested.connect(
            lambda pos: encounter_menu.exec_(trigger_encounter.mapToGlobal(pos))
        )

        layout.addLayout(btns)
        self.canvas_label = QLabel()
        self.canvas_label.setMouseTracking(True)
        self.canvas_label.mousePressEvent = self.mousePressEvent
        self.canvas_label.mouseMoveEvent = self.mouseMoveEvent
        layout.addWidget(self.canvas_label)

        self.setLayout(layout)

    def set_encounter_mode(self, mode):
        print(f"[DEBUG] Encounter mode set to: {mode}")
        self.encounter_mode = mode

    def load_tileset_images(self):
        self.tile_images.clear()
        for fname in os.listdir(TILES_ROOT):
            if fname.endswith(".png"):
                name = os.path.splitext(fname)[0]
                path = os.path.join(TILES_ROOT, fname)
                try:
                    image = pygame.image.load(path).convert_alpha()
                    self.tile_images[name] = image
                except Exception as e:
                    print(f"Failed to load tile '{fname}': {e}")

    def get_remaining_tile_count(self):
        return sum(
            1 for tile in self.board
            if tile.get("state") != "cleared" and not tile.get("fading", False)
        )

    def get_total_tile_count(self):
        return len(self.tile_images)

    def calculate_target_score(self, base_combo=2):
        tiles_remaining = self.get_total_tile_count()
        N_pairs = tiles_remaining * PAIR_COUNT
        difficulty_scale = 1.1 + (self.round_number - 1) * 0.15  # increases per round
        combo_expectation = base_combo + self.round_number * 0.05  # expects better combos later

        expected_score_per_pair = self.base_score * combo_expectation
        expected_total_score = N_pairs * expected_score_per_pair

        # Penalize slightly for increasing difficulty
        target = expected_total_score * difficulty_scale

        # Round to the nearest 20
        target = round(target / 50) * 50

        return int(target)


    def modify_score(self, tile_name, base_points=5):
        self.combo_display_start = pygame.time.get_ticks()
        self.combo_display_text = f" X {self.combo_level}"
        self.combo_display_start = pygame.time.get_ticks()
        self.combo_end_time = self.combo_display_start + self.combo_display_duration  # 10 seconds
        self.combo_fade_duration = 20000  # ms fade out after timer ends

        # Track tile match count
        count = self.tile_match_count.get(tile_name, 0) + 1
        self.tile_match_count[tile_name] = count

        # Set combo display
        if self.combo_multiplier > 1:
            self.combo_display_text = f"X {self.combo_level}"
            self.combo_display_time = pygame.time.get_ticks()



        # Score calculation
        tile_multiplier = count
        total_multiplier = tile_multiplier * self.combo_level
        total_points = base_points * total_multiplier
        if self.score >= self.target_score:
            self.score += int(total_points / self.count_remaining_tiles())
        else:
            self.score += total_points
            self.score += total_points

        self.score += total_points


        self.score_label.setText(f"Score: {self.score}")

    def get_combo_color(self, multiplier):
        # Clamp the range
        multiplier = max(1, min(multiplier, 10))

        # Normalize to 0.0–1.0 for the colormap
        norm = Normalize(vmin=1, vmax=10)
        cmap = cm.get_cmap("inferno").reversed()

        rgba = cmap(norm(multiplier))  # Returns (r, g, b, a) floats
        r = int(rgba[0] * 255)
        g = int(rgba[1] * 255)
        b = int(rgba[2] * 255)
        return (r, g, b)

    def update_fuse_gradient(self):
        # Reversed inferno colormap
        cmap = cm.get_cmap("inferno").reversed()

        # Clamp combo_level between 1 and 10
        clamped_level = max(1, min(self.combo_level, 10))

        # Normalize range from 1 to 10
        norm = Normalize(vmin=1, vmax=10)

        # Sample the gradient from 1 up to the current combo level
        levels = 20  # Number of discrete colors
        max_ratio = norm(clamped_level)  # Get float in 0.0–1.0

        self.fuse_gradient = [
            tuple(int(c * 255) for c in cmap(i / (levels - 1) * max_ratio)[:3])
            for i in range(levels)
        ]

    def draw_combo_text(self):

        if not self.combo_display_text:
            return

        now = pygame.time.get_ticks()

        # Case 1: Combo still active — draw fully opaque
        if now < self.combo_end_time:
            alpha = 255

        # Case 2: Combo has ended — fade out gradually
        elif now < self.combo_end_time + self.combo_fade_duration:
            fade_elapsed = now - self.combo_end_time
            progress = fade_elapsed / self.combo_fade_duration
            alpha = int(255 * (1 - progress ** 2))  # quadratic ease-out
            self.reset_combo()
        else:
            return  # Combo fully expired, don't draw

        color = self.get_combo_color(self.combo_level)
        text_surface = self.combo_font.render(self.combo_display_text, True, color)
        text_surface.set_alpha(alpha)

        text_rect = text_surface.get_rect(center=(self.surface.get_width() // 2,
                                                  self.surface.get_height() - 40))
        self.surface.blit(text_surface, text_rect)

    def add_combo_point(self):
        logging.debug(f"Combo points before: {self.combo_points}, level: {self.combo_level}")

        self.combo_points += 1

        if not self.combo_bands:
            self.start_new_combo_band(self.combo_points)
            logging.debug("Started new combo band")
        else:
            self.combo_bands[-1].refresh(
                current_points=self.combo_points,
                max_points=self.combo_required_per_level
            )
            logging.debug("Refreshed existing combo band")

        if self.combo_level < self.combo_max_level:
            if self.combo_points >= self.combo_required_per_level:
                self.combo_points = 0
                self.combo_level += 1
                self.combo_multiplier += 1
                self.update_fuse_gradient()
                self.start_new_combo_band()
                logging.debug(f"Leveled up combo: level={self.combo_level}, multiplier={self.combo_multiplier}")

        self.combo_timer.start()
        self.combo_display_start = pygame.time.get_ticks()  # For time-based rendering

        self.update()

    def create_or_update_combo_band(self):
        # Remove and recreate the most recent band with updated progress and fresh burn timer
        if self.combo_bands:
            self.combo_bands[-1] = self._build_combo_band(self.combo_level, self.combo_points)
        else:
            self.combo_bands.append(self._build_combo_band(self.combo_level, self.combo_points))

    def _build_combo_band(self, level, points):
        self.combo_color = self.get_combo_color(level)
        y = self.action_bar_top - 10
        x = 20
        width = self.surface.get_width() - 40
        return ComboBand(x, y, width, 4, self.combo_color, self.combo_display_duration,
                         current_points=points, max_points=self.combo_required_per_level)

    def reset_combo_timer(self):
        self.combo_timer.stop()
        self.combo_display_start = 0
        self.combo_multiplier = 1
        self.combo_matches = 0
        self.combo_level = 1
        self.combo_color = self.get_combo_color(self.combo_level)

        self.combo_bands.clear()  # Extinguish fuse band visually
        logging.debug("[COMBO] Combo timer expired. Fuse extinguished.")

        self.update()

    def reset_combo(self):
        self.combo_points = 0
        self.combo_level = 0
        self.combo_matches = 0
        self.combo_bands.clear()  # ✅ Clear fuse bands
        self.combo_timer.stop()  # ✅ Stop the fuse countdown

        # ✅ Clear combo display
        self.combo_display_text = ""
        self.combo_display_time = 0
        self.combo_label.hide()  # Hide the Qt label if you're using it

        # ✅ Optionally reset combo multiplier and score display
        self.combo_multiplier = 1

        # ✅ Force UI update if needed
        self.update()

    def start_new_combo_band(self, points=None):
        if points is None or points == 0:
            points = 1  # Start at 20% minimum when creating a new band

        color = self.get_combo_color(self.combo_level)
        y = ACTION_BAR_HEIGHT
        x = 20
        width = self.surface.get_width() - 40

        # Clamp to prevent overfilling
        points = max(1, min(points, self.combo_required_per_level))

        band = ComboBand(
            x, y, width, 4, color,
            self.combo_display_duration,
            current_points=points,
            max_points=self.combo_required_per_level
        )
        self.combo_bands.append(band)
        logging.debug(
            f"Created new combo band with {points} points (fill {points / self.combo_required_per_level:.2f})")

    def draw_combo_fuse(self):
        for band in self.combo_bands:
            band.draw(self.surface, self.fuse_particles, self.fuse_gradient)

        # Update/draw fuse particles
        alive_fuse_particles = []
        for p in self.fuse_particles:
            p.update()
            p.draw(self.surface)
            if p.alpha > 0:
                alive_fuse_particles.append(p)
        self.fuse_particles = alive_fuse_particles


    def draw_score_text(self):
        score_color = (255, 255, 255)  # White or any desired color
        score_text = f"Score: {self.score}"
        score_surface = self.gui_font.render(score_text, True, score_color)

        # Align below the combo text
        combo_y_offset = self.surface.get_height() - 40  # y-position of combo text
        padding = 30  # space between combo and score

        score_rect = score_surface.get_rect(center=(self.surface.get_width() // 2,
                                                    combo_y_offset + padding))

        self.surface.blit(score_surface, score_rect)

    def reset_round_score_state(self):
        self.tile_match_count.clear()
        self.combo_multiplier = 1
        self.combo_timer.stop()
        self.last_match_time = None

    def reset_game_state(self):
        self.wallet = 0
        self.score = 0
        self.round_number = 0
        self.target_score = 500
        self.selected_tiles = []
        self.combo_multiplier = 1
        self.match_count = 0
        self.inventory = [None] * 5
        self.available_encounters = []
        self.available_encounters_bu = []
        self.encounter_mode = None
        self.board = []
        self.tile_positions = {}
        self.fading_matched_tiles = []
        self.animating_tiles = []
        self._vacated_during_animation = set()

    def mousePressEvent(self, event):
        x = event.pos().x()
        y = event.pos().y()
        self.last_mouse_pos = (x, y)

        # print("[DEBUG] Mouse click at:", (x, y))
        pygame.draw.circle(self.surface, (255, 0, 0), (x, y), 5)

        handled = False  # Track whether anything handled the click

        for name, rect in self.button_rects.items():
            context = self.button_contexts.get(name, "global")

            # Context-aware filtering
            if context == "shop" and not self.in_shop:
                continue
            if context == "inventory" and self.in_shop:
                continue

            if rect.collidepoint(x, y):
                print(f"[CLICK] {name} button clicked")

                if name == "prev_track":
                    self.music_manager.previous_track()
                    handled = True

                elif name == "next_track":
                    self.music_manager.next_track()
                    handled = True

                elif name == "volume_slider":
                    self.dragging_volume_slider = True
                    self.update_volume_from_mouse(x)
                    handled = True


                elif name.startswith("inventory_"):
                    index = int(name.split("_")[1])
                    print(f"[CLICK] Inventory slot {index} clicked")
                    self.selected_inventory_index = index
                    self.trigger_inventory_item_effect(index)
                    handled = True

                elif name == "shop_continue":
                    print("[CLICK] shop_continue confirmed")
                    self.start_new_round()
                    handled = True

                elif name == "shop_reroll":
                    print("[CLICK] shop_reroll triggered")
                    self.reroll_shop()
                    handled = True


                elif name == "booster_confirm":
                    if len(self.booster_selected_indices) == 3:
                        selected_names = [self.booster_choices[i] for i in self.booster_selected_indices]
                        self.booster_history.extend(selected_names)
                        self.exit_booster_selector()
                        handled = True


                elif name == "booster_skip":
                    self.selected_booster_tiles = []  # Ensure nothing is added
                    self.exit_booster_selector()
                    handled = True

                elif name == "shop_booster":
                    print("[CLICK] shop_booster triggered")
                    if self.wallet >= self.booster_pack_cost:
                        self.wallet -= self.booster_pack_cost
                        self.selected_booster_tiles = []
                        self.booster_choices = random.sample(list(self.tile_images.keys()), 5)
                        self.show_booster_selector = True
                    else:
                        self.shop_message = "Not enough points!"
                    handled = True

                break  # Found a matching button, stop checking

        if handled:
            return

        # Shop item buttons (outside button_rects)
        if self.in_shop:
            for rect, item in getattr(self, "shop_button_rects", []):
                if rect.collidepoint(x, y):
                    name = item.get("title", "???")
                    cost = item.get("cost", 999)
                    print(f"[CLICK] Attempting to buy {name} for {cost}")
                    self.attempt_purchase(item)
                    return

        elif self.show_booster_selector:
            for i, (rect, item) in enumerate(self.booster_button_rects):
                if rect.collidepoint(event.pos):
                    if i in self.booster_selected_indices:
                        self.booster_selected_indices.remove(i)
                    elif len(self.booster_selected_indices) < 3:
                        self.booster_selected_indices.add(i)
                    self.update()
                    return

            if self.button_rects.get("booster_confirm", pygame.Rect(0, 0, 0, 0)).collidepoint(self.last_mouse_pos):
                if len(self.booster_selected_indices) == 3:
                    for idx in self.booster_selected_indices:
                        self.tile_pool.append(self.booster_choices[idx])
                    self.exit_booster_selector()

            elif self.button_rects.get("booster_skip", pygame.Rect(0, 0, 0, 0)).collidepoint(self.last_mouse_pos):
                self.exit_booster_selector()

        # Check if booster UI is active
        if self.booster_choices:
            for i, (rect, tile_name) in enumerate(self.booster_button_rects):
                if rect.collidepoint(self.last_mouse_pos):
                    if i in self.booster_selected_indices:
                        self.booster_selected_indices.remove(i)  # Unselect
                    elif len(self.booster_selected_indices) < 3:
                        self.booster_selected_indices.add(i) # Select
                    return  # Stop here if clicked a tile

            # Confirm button
            confirm_rect = self.button_rects.get("booster_confirm")
            if confirm_rect and confirm_rect.collidepoint(self.last_mouse_pos):
                if len(self.booster_selected_indices) == 3:
                    selected_names = [self.booster_choices[i] for i in self.booster_selected_indices]
                    self.booster_pool.extend(selected_names * 2)  # Add pairs to pool
                    self.booster_choices = []  # Close UI
                    self.booster_selected_indices.clear()
                return

            # Skip button
            skip_rect = self.button_rects.get("booster_skip")
            if skip_rect and skip_rect.collidepoint(self.last_mouse_pos):
                self.booster_choices = []  # Close UI
                self.booster_selected_indices.clear()
                return


        if self.in_game_over:
            if self.game_over_button_rect.collidepoint(x, y):
                print("[CLICK] Start New Game from Game Over screen")
                self.in_game_over = False
                self.reset_game_state()
                self.start_new_round()
                return

        # Tile selection fallback
        self.handle_click(event)

    def get_random_booster_tiles(self, count):
        try:
            with open(ITEMS, "r") as f:
                all_tiles = json.load(f)
            return random.sample(all_tiles, min(count, len(all_tiles)))
        except Exception as e:
            print("[BOOSTER ERROR] Failed to load booster tiles")
            traceback.print_exc()
            return []

    def reroll_shop(self):
        print("[REROLL] Attempting shop reroll...")

        if self.wallet < self.reroll_price:
            self.shop_message = f"Not enough points to reroll! ({self.reroll_price} pts)"
            print(f"[REROLL] Blocked. Wallet: {self.wallet}, Cost: {self.reroll_price}")
            return

        self.wallet -= self.reroll_price
        self.reroll_price += 25  # Increase cost with each reroll
        print(f"[REROLL] Deducted {self.reroll_price - 25}, new wallet: {self.wallet}, next cost: {self.reroll_price}")

        # Remove placeholder items
        self.shop_items = [item for item in self.shop_items if not item.get("placeholder")]

        # Track inventory titles to avoid duplicates
        owned_titles = {item.get("title") for item in self.inventory}

        while len(self.shop_items) < 4:
            new_item = self.get_random_shop_item(owned_titles)
            if new_item:
                self.shop_items.append(new_item)
                owned_titles.add(new_item.get("title"))
            else:
                break  # Stop if no more valid items

        self.shop_message = "Shop rerolled!"
        self.update()

    def trigger_inventory_item_effect(self, index):
        if index >= len(self.inventory):
            print(f"[ERROR] Invalid inventory index: {index}")
            return

        item = self.inventory[index]
        item_id = item.get("id", f"item_{index}")

        # Initialize cooldown and usage tracking dicts if needed
        if not hasattr(self, "inventory_cooldowns"):
            self.inventory_cooldowns = {}  # match-based cooldowns
        if not hasattr(self, "inventory_timers"):
            self.inventory_timers = {}  # time-based cooldowns

        now = time.time()

        # --- Check cooldown match ---
        match_cd = item.get("cooldown_match")
        if match_cd is not None:
            last_match_use = self.inventory_cooldowns.get(item_id, -9999)
            if self.match_count - last_match_use < match_cd:
                print(f"[COOLDOWN] {item['title']} still on match cooldown.")
                return
            self.inventory_cooldowns[item_id] = self.match_count

        # --- Check cooldown time ---
        time_cd = item.get("cooldown_time")
        if time_cd is not None:
            last_time_use = self.inventory_timers.get(item_id, -9999)
            if now - last_time_use < time_cd:
                print(f"[COOLDOWN] {item['title']} still on time cooldown.")
                return
            self.inventory_timers[item_id] = now

        # --- Check charges ---
        charges = item.get("charges")
        if charges is not None:
            if charges <= 0:
                print(f"[USED UP] {item['title']} has no charges left.")
                return
            item["charges"] -= 1
            print(f"[USE] {item['title']} used. Charges left: {item['charges']}")
            if item["charges"] == 0:
                print(f"[REMOVE] {item['title']} removed from inventory.")
                self.inventory.pop(index)
                return

        # --- Trigger effect (your logic here) ---
        print(f"[TRIGGER] {item['title']} activated.")

        # Optional: show animation, apply effect, etc.
        self.handle_inventory_effect(item, index)

    def handle_inventory_effect(self, item, index):
        effect_type = item.get("effect")
        if effect_type == "shuffle":
            self.shuffle_board()
        elif effect_type == "reveal":
            self.hint_possible_matches()
        elif effect_type == "boost_score":
            self.score += item.get("value", 100)
        elif effect_type == "swap_tarot_tiles_moon_sun":
            self.swap_tarot_tiles_moon_sun()
        else:
            print(f"[EFFECT] No defined logic for effect: {effect_type}")

    def handle_mouse_up(self, event):
        self.dragging_volume = False

    def mouseReleaseEvent(self, event):
        self.handle_mouse_up(event)

        self.dragging_volume_slider = False



    def handle_mouse_motion(self, event):
        if self.dragging_volume:
            x = event.pos().x()
            slider_rect = self.button_rects["volume_slider"]
            relative_x = min(max(x - slider_rect.x, 0), slider_rect.width)
            self.music_volume = relative_x / slider_rect.width
            self.music_manager.set_volume(self.music_volume)

    def update_volume_from_mouse(self, mouse_x):
        rect = self.button_rects.get("volume_slider")
        if not rect:
            return
        relative_x = max(0, min(mouse_x - rect.x, rect.width))
        self.music_volume = relative_x / rect.width
        self.music_manager.set_volume(self.music_volume)
        print(f"[VOLUME] Adjusted to {self.music_volume:.2f}")
        self.update()


    def get_possible_match_count(self):
        name_counts = {}
        for tile in self.get_selectable_tiles():
            name = tile["name"]
            name_counts[name] = name_counts.get(name, 0) + 1

        total = 0
        for count in name_counts.values():
            total += count // 2  # Each pair is a match
        return total

    def start_new_round(self):
        print("[ROUND] Starting next round...")

        # Exit shop
        self.in_shop = False
        self.selected_inventory_index = None
        self.setMouseTracking(True)

        self.shop_message = ""
        self.shop_items = []

        # Transfer leftover points
        leftover = self.score - self.target_score
        if leftover > 0:
            self.wallet += leftover

        # Reset score and round info
        self.score = 0
        self.round_number += 1
        self.target_score = self.calculate_target_score()
        self.match_count = 0
        self.combo_multiplier = 1
        self.fading_matched_tiles = []

        # Handle encounter mode
        if self.round_number % 3 == 0:
            if len(self.available_encounters) == 0:
                self.available_encounters = self.available_encounters_bu
                self.available_encounters_bu = []

            self.encounter_mode = random.choice(self.available_encounters)
            self.available_encounters.remove(self.encounter_mode)
            self.available_encounters_bu.append(self.encounter_mode)

            self.encounter_label.setText(f"Encounter: {self.encounter_mode}")
            self.match_counter_label.setText("Encounter triggers every 5 matches")
        else:
            self.encounter_mode = None
            self.encounter_label.setText("Encounter: None")
            self.match_counter_label.setText("")

        # Update UI
        self.wallet_label.setText(f"Wallet: {self.wallet}")
        self.score_label.setText(f"Score: {self.score}")

        # Start new game
        self.new_game()
        self.update()

    def build_centered_pyramid_layout(self, total_tiles: int, max_cols=MAX_COLS, max_rows=MAX_ROWS) -> list[tuple[int, int, int]]:
        layout = []
        layer_maps = {}  # Tracks occupied positions per z level

        # Determine max size for pyramid base
        max_w, max_h = max_cols, max_rows
        cx, cy = max_w // 2, max_h // 2

        z = 0
        step = 2
        base_w, base_h = 2, 2

        # Build in growth cycles: each z layer starts with minimal center, then grows
        while len(layout) < total_tiles:
            for dz in range(z + 1):
                grow = z - dz
                desired_w = min(base_w + (step * grow), max_w)
                desired_h = min(base_h + (step * grow), max_h)

                # Check if either dimension can still be expanded without exceeding max
                if desired_w > max_w and desired_h > max_h:
                    continue

                occupied = layer_maps.setdefault(dz, set())

                for y in range(desired_h):
                    for x in range(desired_w):
                        gx = cx - desired_w // 2 + x
                        gy = cy - desired_h // 2 + y
                        if (gx, gy) not in occupied:
                            layout.append((gx, gy, dz))
                            occupied.add((gx, gy))
                        if len(layout) >= total_tiles:
                            break
                    if len(layout) >= total_tiles:
                        break
                if len(layout) >= total_tiles:
                    break
            z += 1

        # Debug output
        from collections import defaultdict
        level_summary = defaultdict(list)
        for gx, gy, gz in layout:
            level_summary[gz].append((gx, gy))

        for level in sorted(level_summary.keys()):
            coords = level_summary[level]
            min_x = min(gx for gx, _ in coords)
            max_x = max(gx for gx, _ in coords)
            min_y = min(gy for _, gy in coords)
            max_y = max(gy for _, gy in coords)
            w = max_x - min_x + 1
            h = max_y - min_y + 1
            print(f"[DEBUG] Z={level}: {w}x{h} => {len(coords)} tiles")

        return layout

    def start_new_game(self):
        print("[ROUND] Starting next round...")

        self.reset_combo()

        # Exit shop
        self.in_shop = False
        self.selected_inventory_index = None
        self.shop_message = ""
        self.shop_items = []


        # Reset score and round info
        self.score = 0
        self.round_number = 1
        self.target_score = self.calculate_target_score()
        self.match_count = 0
        self.combo_multiplier = 1
        self.fading_matched_tiles = []


        # Handle encounter mode
        if self.round_number % 3 == 0:
            if len(self.available_encounters) == 0:
                self.available_encounters = self.available_encounters_bu
                self.available_encounters_bu = []

            self.encounter_mode = random.choice(self.available_encounters)
            self.available_encounters.remove(self.encounter_mode)
            self.available_encounters_bu.append(self.encounter_mode)

            self.encounter_label.setText(f"Encounter: {self.encounter_mode}")
            self.match_counter_label.setText("Encounter triggers every 5 matches")
        else:
            self.encounter_mode = None
            self.encounter_label.setText("Encounter: None")
            self.match_counter_label.setText("")

        # Update UI labels
        self.wallet_label.setText(f"Wallet: {self.wallet}")
        self.score_label.setText(f"Score: {self.score}")

        # Generate new board and redraw
        self.new_game()
        self.update()

    def new_game(self):
        self.board.clear()
        self.tile_positions.clear()
        self.selected_tiles.clear()
        self.matched_pairs.clear()
        self.match_count = 0

        # 🤩 Always include every base tile with PAIR_COUNT
        tile_names = list(self.tile_images.keys())
        if not tile_names:
            print("No tiles loaded.")
            return

        name_pool = []
        for tile_name in tile_names:
            name_pool.extend([tile_name] * PAIR_COUNT)

        print(f"[DEBUG] Base pool: {len(name_pool)} tiles ({len(name_pool) // 2} pairs)")

        # 🎯 Add booster history (2 copies per tile)
        for tile_name in self.booster_history:
            name_pool.extend([tile_name] * PAIR_COUNT)

        total_tiles = len(name_pool)
        print(f"[DEBUG] Total tiles in pool after boosters: {total_tiles} ({total_tiles // 2} pairs)")
        print(f"[DEBUG] Booster history: {self.booster_history}")

        # 🔀 Shuffle the pool
        random.shuffle(name_pool)

        # 🧱 Build a centered pyramid layout starting from top layer
        layout = self.build_centered_pyramid_layout(total_tiles)

        center_x = 6
        center_y = NUM_ROWS // 2

        for z in range(STACK_HEIGHT):
            width = 12 - z * 2
            height = NUM_ROWS - z
            x_start = center_x - width // 2
            y_start = center_y - height // 2
            for y in range(height):
                for x in range(width):
                    layout.append((x_start + x, y_start + y, z))

        canvas_width, canvas_height = self.surface.get_size()
        tile_w, tile_h = TILE_WIDTH, TILE_HEIGHT
        tile_d = TILE_DEPTH
        layout_xs = [x for x, y, z in layout]
        layout_ys = [y for x, y, z in layout]
        min_x, max_x = min(layout_xs), max(layout_xs)
        min_y, max_y = min(layout_ys), max(layout_ys)
        board_px_width = (max_x - min_x + 1) * tile_w
        board_px_height = (max_y - min_y + 1) * tile_h
        offset_x = (canvas_width - board_px_width) // 2 - min_x * tile_w
        offset_y = (canvas_height - board_px_height) // 2 - min_y * tile_h - 40

        for i, (gx, gy, gz) in enumerate(layout):
            if i >= len(name_pool):
                break
            abs_x, abs_y = self.get_tile_pixel_position(gx, gy, gz, tile_w, tile_h, tile_d, offset_x, offset_y)
            name = name_pool[i]
            tile = {
                "name": name,
                "x": abs_x,
                "y": abs_y,
                "z": gz,
                "grid_x": gx,
                "grid_y": gy
            }
            self.board.append(tile)
            self.tile_positions[(gx, gy, gz)] = tile

        # Save for global reference
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.calculate_grid_bounds()

    def calculate_grid_bounds(self):
        if not self.board:
            self.min_grid_x = self.max_grid_x = 0
            self.min_grid_y = self.max_grid_y = 0
            return

        xs = [tile["grid_x"] for tile in self.board]
        ys = [tile["grid_y"] for tile in self.board]

        self.min_grid_x = min(xs)
        self.max_grid_x = max(xs)
        self.min_grid_y = min(ys)
        self.max_grid_y = max(ys)

    def get_tile_pixel_position(self, gx, gy, gz, tile_w, tile_h, tile_d, offset_x, offset_y):
        return (
            offset_x + gx * tile_w,
            offset_y + gy * tile_h - gz * tile_d
        )

    def new_game_2(self):
        # 🧹 Clear current game state
        self.board.clear()
        self.tile_positions.clear()
        self.selected_tiles.clear()
        self.matched_pairs.clear()
        self.match_count = 0

        # 🤩 Always include every base tile with PAIR_COUNT
        tile_names = list(self.tile_images.keys())
        if not tile_names:
            print("No tiles loaded.")
            return

        name_pool = []
        for tile_name in tile_names:
            name_pool.extend([tile_name] * PAIR_COUNT)

        print(f"[DEBUG] Base pool: {len(name_pool)} tiles ({len(name_pool) // 2} pairs)")

        # 🎯 Add booster history (2 copies per tile)
        for tile_name in self.booster_history:
            name_pool.extend([tile_name] * PAIR_COUNT)

        total_tiles = len(name_pool)
        print(f"[DEBUG] Total tiles in pool after boosters: {total_tiles} ({total_tiles // 2} pairs)")
        print(f"[DEBUG] Booster history: {self.booster_history}")

        # 🔀 Shuffle the pool
        random.shuffle(name_pool)

        # 🧱 Build a centered pyramid layout starting from top layer
        layout = self.build_centered_pyramid_layout(total_tiles)

        # 🖼 Centering logic with offset
        canvas_width, canvas_height = self.surface.get_size()
        tile_w, tile_h = TILE_WIDTH, TILE_HEIGHT
        layout_xs = [x for x, y, z in layout]
        layout_ys = [y for x, y, z in layout]
        min_x, max_x = min(layout_xs), max(layout_xs)
        min_y, max_y = min(layout_ys), max(layout_ys)
        board_px_width = (max_x - min_x + 1) * tile_w
        board_px_height = (max_y - min_y + 1) * tile_h
        offset_x = (canvas_width - board_px_width) // 2 - min_x * tile_w
        offset_y = (canvas_height - board_px_height) // 2 - min_y * tile_h - 40  # shift up

        self.board.clear()
        self.tile_positions.clear()

        # 🧱 Build tiles
        for i, (gx, gy, gz) in enumerate(layout):
            abs_x = offset_x + gx * tile_w
            abs_y = offset_y + gy * tile_h - gz * 10  # stack offset

            name = name_pool[i]
            tile = {
                "name": name,
                "x": abs_x,
                "y": abs_y,
                "z": gz,
                "grid_x": gx,
                "grid_y": gy
            }
            self.board.append(tile)
            self.tile_positions[(gx, gy, gz)] = tile

        # 📐 Grid bounds for fog/center reference
        grid_xs = [tile["grid_x"] for tile in self.board]
        grid_ys = [tile["grid_y"] for tile in self.board]
        self.min_grid_x = min(grid_xs)
        self.max_grid_x = max(grid_xs)
        self.min_grid_y = min(grid_ys)
        self.max_grid_y = max(grid_ys)
        self.center_x = (self.min_grid_x + self.max_grid_x) // 2
        self.center_y = (self.min_grid_y + self.max_grid_y) // 2

    def is_tile_selectable(self, tile):
        gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

        # Must have no tile above
        if (gx, gy, gz + 1) in self.tile_positions:
            return False

        # Must have at least one free horizontal side
        left_blocked = (gx - 1, gy, gz) in self.tile_positions
        right_blocked = (gx + 1, gy, gz) in self.tile_positions

        return not (left_blocked and right_blocked)

    def get_topmost_tiles(self):
        topmost = {}
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"])
            if key not in topmost or tile["z"] > topmost[key]["z"]:
                topmost[key] = tile
        return topmost

    def count_remaining_tiles(self):
        return len(self.board)

    def tick(self):
        self.bg_scroll_x = (self.bg_scroll_x + self.bg_scroll_speed_x) % self.background_tile.get_width()
        self.bg_scroll_y = (self.bg_scroll_y + self.bg_scroll_speed_y) % self.background_tile.get_height()
        self.update_hover_state()  # Must be here!

        self.update_canvas()

    def update_hover_state(self):
        if not hasattr(self, 'last_mouse_pos'):
            return

        pos = self.last_mouse_pos
        self.item_card.hide()
        self.hovered_inventory_index = None

        # Use a fixed display location for all item cards
        anchor_rect = self.button_rects.get("inventory_0")
        card_x = anchor_rect.x if anchor_rect else 0
        card_y = anchor_rect.y - TILE_HEIGHT * 4 - 10 if anchor_rect else 0
        card_y = max(0, card_y)

        # === Check inventory items ===
        for i in range(5):
            rect = self.button_rects.get(f"inventory_{i}")
            if rect and rect.collidepoint(pos):
                item = self.inventory[i] if i < len(self.inventory) else None
                self.hovered_inventory_index = i
                if item:
                    self.item_card.show(item, (card_x, card_y))
                return

        # === Check shop items ===
        if self.in_shop and hasattr(self, "shop_button_rects"):
            for rect, item in self.shop_button_rects:
                if rect.collidepoint(pos):
                    self.item_card.show(item, (card_x, card_y))
                    return

        self.hovered_inventory_index = None

    def mouseMoveEvent(self, event):
        # print(f"[MOUSE MOVE] {datetime.datetime.now()}")
        self.last_mouse_pos = (event.pos().x(), event.pos().y())
        # self.update_hover_state()  # ✅ Trigger hover check immediately
        # self.update()  # ✅ Repaint if hover card changes

    def update_canvas(self):
        ACTION_BAR_HEIGHT = 100
        self.clear_background()
        self.draw_background_tiles()
        self.draw_tile_shadows()
        self.draw_top_static_tiles()
        self.draw_exposed_tiles()
        self.draw_animating_tiles()
        self.draw_fading_tiles()
        self.draw_fog_of_war()
        self.draw_combo_fuse()
        self.action_bar.draw()  # External call to encapsulated class
        self.draw_particles()
        self.update_hover_state()
        self.draw_overlays()
        self.item_card.draw(self.surface)
        self.blit_to_qt()

    def draw_top_static_tiles(self):
        # Get safely initialized lists/sets
        animating_tiles = getattr(self, "animating_tiles", [])
        fading_tiles = getattr(self, "fading_matched_tiles", [])

        animating_coords = set((t["grid_x"], t["grid_y"], t["z"]) for t in animating_tiles)
        fading_coords = set((t["grid_x"], t["grid_y"], t["z"]) for t in fading_tiles)

        top_tiles = {}
        for tile in self.board:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            if (gx, gy, gz) in animating_coords or (gx, gy, gz) in fading_coords:
                continue
            key = (gx, gy)
            if key not in top_tiles or gz > top_tiles[key]["z"]:
                top_tiles[key] = tile

        for tile in sorted(top_tiles.values(), key=lambda t: t["z"]):
            img = self.tile_images.get(tile["name"])
            if img:
                self.surface.blit(img, (tile["x"], tile["y"]))
                if tile in self.selected_tiles:
                    for _ in range(20):
                        self.particles.append(SelectedParticle(tile["x"], tile["y"], TILE_WIDTH, TILE_HEIGHT))

    def draw_exposed_tiles(self):
        exposed_tiles = [
            tile for tile in self.board
            if tile.get("will_become_exposed") and
               (tile["grid_x"], tile["grid_y"]) not in self.top_tiles
        ]
        exposed_tiles.sort(key=lambda t: t["z"])
        for tile in exposed_tiles:
            img = self.tile_images.get(tile["name"])
            if img:
                temp_img = img.copy()
                temp_img.set_alpha(tile.get("alpha", 255))
                self.surface.blit(temp_img, (tile["x"], tile["y"]))

    def draw_animating_tiles(self):
        for tile in self.animating_tiles:
            if (tile["grid_x"], tile["grid_y"], tile["z"]) not in self.fading_coords:
                img = self.tile_images.get(tile["name"])
                if img:
                    temp_img = img.copy()
                    temp_img.set_alpha(tile.get("alpha", 255))
                    self.surface.blit(temp_img, (tile["x"], tile["y"]))

    def draw_fading_tiles(self):
        now = pygame.time.get_ticks()
        done = []
        for tile in self.fading_matched_tiles:
            elapsed = now - tile["fade_start"]
            progress = min(1.0, elapsed / tile["fade_duration"])
            alpha = int(255 * (1 - progress))
            img = self.tile_images.get(tile["name"])
            if img:
                temp_img = img.copy()
                temp_img.set_alpha(alpha)
                self.surface.blit(temp_img, (tile["x"], tile["y"]))
            if progress >= 1.0:
                done.append(tile)
        for tile in done:
            self.board.remove(tile)
            self.tile_positions.pop((tile["grid_x"], tile["grid_y"], tile["z"]), None)
            self.fading_matched_tiles.remove(tile)
        for tile in self.board:
            if tile.get("will_become_exposed"):
                tile.pop("will_become_exposed")

    def draw_tile_shadows(self):
        vacated = getattr(self, "_vacated_during_animation", set())
        fading_coords = set((t["grid_x"], t["grid_y"], t["z"]) for t in self.fading_matched_tiles)
        animating_coords = set((t["grid_x"], t["grid_y"], t["z"]) for t in self.animating_tiles)

        # All current tiles that are not fading or animating
        present_tiles = [
            tile for tile in self.board
            if (tile["grid_x"], tile["grid_y"], tile["z"]) not in fading_coords
        ]

        # Map (gx, gy) -> highest z of tile still present at that position
        top_z_at = {}
        for tile in present_tiles:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            top_z_at[(gx, gy)] = max(top_z_at.get((gx, gy), -1), gz)

        # Include animating tiles that are leaving a stack
        for tile in self.animating_tiles:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            top_z_at[(gx, gy)] = max(top_z_at.get((gx, gy), -1), gz - 1)

        # Draw shadows under all tiles that are not the topmost at their (gx, gy)
        for tile in self.board:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            if gz < top_z_at.get((gx, gy), -1):
                shadow = pygame.Surface((TILE_WIDTH, TILE_HEIGHT), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 200))
                self.surface.blit(shadow, (tile["x"], tile["y"]))

    def clear_background(self):
        self.surface.fill((0, 80, 80))

    def draw_background_tiles(self):
        pygame.mixer.music.get_pos()

        tile_w, tile_h = self.background_tile.get_size()
        surface_w, surface_h = self.surface.get_size()
        start_x = -int(self.bg_scroll_x)
        start_y = -int(self.bg_scroll_y)

        for x in range(start_x, surface_w, tile_w):
            for y in range(start_y, surface_h, tile_h):
                self.surface.blit(self.background_tile, (x, y))

    def draw_particles(self):
        alive_particles = []
        for p in self.particles:
            if p.update():
                p.draw(self.surface)
                alive_particles.append(p)
        self.particles = alive_particles

    def draw_overlays(self):
        if self.in_shop:
            self.draw_shop_overlay()
        if self.in_game_over:
            self.draw_game_over_overlay()
        if self.item_card:
            # print("[DRAW] Calling item_card.draw()")
            self.item_card.draw(self.surface)
        if self.show_booster_selector:
            self.draw_booster_selector()
            return  # Prevent drawing the rest of the shop UI behind it

    def blit_to_qt(self):
        raw_data = pygame.image.tostring(self.surface, "RGB")
        image = QPixmap.fromImage(
            QImage(raw_data, self.surface.get_width(), self.surface.get_height(), QImage.Format_RGB888)
        )
        self.canvas_label.setPixmap(image)

    def draw_fog_of_war(self):
        try:
            fog_surface = pygame.Surface((TILE_WIDTH, TILE_HEIGHT), pygame.SRCALPHA)
            fog_surface.fill((0, 0, 0, 220))
            visible_set = {(t["grid_x"], t["grid_y"], t["z"]) for t in self.get_selectable_tiles()}
            visible_set.update(
                (t["grid_x"], t["grid_y"], t["z"])
                for t in self.board if t.get("will_become_exposed")
            )
            visibility_cutoff_y = {}
            for tile in self.board:
                gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
                if (gx, gy, gz) in visible_set:
                    visibility_cutoff_y[(gx, gy)] = min(
                        visibility_cutoff_y.get((gx, gy), float("inf")),
                        tile["y"]
                    )
            for (gx, gy), tile in self.top_tiles.items():
                if (gx, gy, tile["z"]) in visible_set:
                    continue
                fog_top = tile["y"]
                fog_bottom = tile["y"] + TILE_HEIGHT
                cutoff_y = visibility_cutoff_y.get((gx, gy))
                if cutoff_y is not None and cutoff_y < fog_bottom:
                    fog_height = cutoff_y - fog_top
                    if fog_height > 0:
                        partial_fog = pygame.Surface((TILE_WIDTH, fog_height), pygame.SRCALPHA)
                        partial_fog.fill((0, 0, 0, 220))
                        self.surface.blit(partial_fog, (tile["x"], fog_top))
                else:
                    self.surface.blit(fog_surface, (tile["x"], tile["y"]))
        except Exception as e:
            print(f"[FOG ERROR] {e}")

    def get_selectable_tiles(self):
        selectable = []
        for tile in self.board:
            if self.is_tile_selectable(tile):
                selectable.append(tile)
        # print(f"[DEBUG] Selectable tiles: {[(t['grid_x'], t['grid_y'], t['z']) for t in selectable]}")
        return selectable

    def handle_click(self, event):
        x = event.pos().x()
        y = event.pos().y()


        # Convert Qt click to Pygame click
        for tile in reversed(sorted(self.get_topmost_tiles().values(), key=lambda t: t["z"])):
            tx, ty = tile["x"], tile["y"]
            if tx <= x <= tx + TILE_WIDTH and ty <= y <= ty + TILE_HEIGHT:
                if self.is_tile_selectable(tile):
                    if tile in self.selected_tiles:
                        self.selected_tiles.remove(tile)
                    else:
                        self.selected_tiles.append(tile)
                    if len(self.selected_tiles) == 2:
                        if self.selected_tiles[0]["name"] == self.selected_tiles[1]["name"]:
                            matched = list(self.selected_tiles)  # Copy for animation
                            for t in matched:
                                t["fade_start"] = pygame.time.get_ticks()
                                t["fade_duration"] = 600  # ms
                                t["fading_out"] = True

                                # Lookup particle class based on tile name (fallback to SmokeParticle)
                                particle_cls = tile_particle_map.get(t["name"], SparkleParticle)

                                for _ in range(6):
                                    px = t["x"] + random.randint(-5, 5)
                                    py = t["y"] + random.randint(-5, 5)
                                    self.particles.append(particle_cls(px, py))

                            # New logic to mark tiles beneath as exposed
                            for tile in matched:
                                gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
                                for other in self.board:
                                    if (
                                            other["grid_x"] == gx and
                                            other["grid_y"] == gy and
                                            other["z"] < gz and
                                            not other.get("will_become_exposed")
                                    ):
                                        # Only mark if it's the topmost under this column (and not being removed)
                                        if not any(t2 for t2 in matched if t2 is not tile and
                                                                           t2["grid_x"] == gx and t2[
                                                                               "grid_y"] == gy and t2["z"] > other[
                                                                               "z"]):
                                            other["will_become_exposed"] = True

                            self.fading_matched_tiles = matched
                            self.match_sound.play()

                            # Conditional Match
                            self.combo_level += self.handle_lycan_match(self.selected_tiles[0]["name"],
                                                                    lycanthrope_active = self.has_lycanthrope_item())


                            self.match_count += 1
                            self.modify_score(self.base_score)

                            # NEW: Add combo point when a match is made
                            self.add_combo_point()

                            self.combo_display_text = f"X  {self.combo_multiplier}"
                            self.combo_display_time = QtCore.QTime.currentTime().msecsSinceStartOfDay()
                            self.update()  # Triggers a repaint of the widget

                            if self.encounter_mode and self.match_count % 5 == 0:
                                print(f"[Encounter Triggered] Mode: {self.encounter_mode}")
                                self.trigger_encounter_effect()
                                self.encounter_trigger_in = 5
                            elif self.encounter_mode:
                                self.encounter_trigger_in -= 1

                        self.selected_tiles.clear()
                        self.update_game_state()
                    break


    def update_game_state(self):
        moves = self.get_possible_match_count()
        if self.debug:
            moves = 0

        print(f"Updating Game State, Moves left: {moves} Target Score: {self.target_score}")
        if moves <= 0:
            if self.score < self.target_score:
                print("[STATE] No moves left and target score NOT reached → Game Over")
                self.trigger_game_over()
            else:
                print("[STATE] No moves left but target score met → Entering Shop")
                self.enter_shop_screen()

    def trigger_game_over(self):
        print("[GAME OVER] Triggered")
        self.in_game_over = True
        self.in_shop = False  # Ensure shop is closed
        self.shop_items = []
        self.selected_inventory_index = None
        self.update()

    def draw_game_over_overlay(self):
        now = pygame.time.get_ticks()
        if now - self.last_flash_time > self.flash_interval:
            self.game_over_flash_toggle = not self.game_over_flash_toggle
            self.last_flash_time = now

        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Semi-transparent dark overlay
        self.surface.blit(overlay, (0, 0))

        # Text settings
        game_over_color = (220, 0, 0) if self.game_over_flash_toggle else (120, 0, 0)
        shadow_offset = 4

        # Render drop shadow
        shadow_text = self.combo_font.render("GAME OVER", True, (0, 0, 0))
        game_over_text = self.combo_font.render("GAME OVER", True, game_over_color)

        text_x = self.surface.get_width() // 2 - game_over_text.get_width() // 2
        text_y = 180

        self.surface.blit(shadow_text, (text_x + shadow_offset, text_y + shadow_offset))
        self.surface.blit(game_over_text, (text_x, text_y))

        # Draw button box
        pygame.draw.rect(self.surface, (60, 0, 0), self.game_over_button_rect)  # dark red
        pygame.draw.rect(self.surface, (220, 0, 0), self.game_over_button_rect, 3)  # red border

        # --- Draw button ---
        btn_label = "Start new game"
        mouse_pos = pygame.mouse.get_pos()
        hovering = self.game_over_button_rect.collidepoint(mouse_pos)

        # Button styling
        bg_color = (15, 15, 15, 0.15)
        border_color = (60, 0, 0, 0.5)  # Red border
        text_color = (255, 255, 255) if hovering else (255, 255, 255)

        # Reposition button in center
        btn_width, btn_height = 240, 60
        btn_x = self.surface.get_width() // 2 - btn_width // 2
        btn_y = 320
        self.game_over_button_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)

        # Draw background and border
        pygame.draw.rect(self.surface, bg_color, self.game_over_button_rect)
        pygame.draw.rect(self.surface, border_color, self.game_over_button_rect, 3)

        # Render text and shadow
        btn_text = self.button_font.render(btn_label, True, text_color)
        shadow_text = self.button_font.render(btn_label, True, (0, 0, 0))

        text_x = self.game_over_button_rect.centerx - btn_text.get_width() // 2
        text_y = self.game_over_button_rect.centery - btn_text.get_height() // 2

        self.surface.blit(shadow_text, (text_x + 2, text_y + 2))
        self.surface.blit(btn_text, (text_x, text_y))

    def get_random_shop_item(self, exclude_titles=None):
        if exclude_titles is None:
            exclude_titles = set()

        try:
            with open(ITEMS, "r") as f:
                all_items = json.load(f)

            # Exclude duplicates
            inventory_titles = {item["title"] for item in self.inventory}
            current_shop_titles = {item["title"] for item in self.shop_items}
            exclude_titles.update(inventory_titles)
            exclude_titles.update(current_shop_titles)

            valid_items = [item for item in all_items if
                           item.get("title") not in exclude_titles and not item.get("placeholder")]

            if not valid_items:
                print("[SHOP WARNING] No valid items to choose from.")
                return None

            # Apply rarity weights
            rarity_mods = self.get_rarity_modifiers()
            weighted_pool = []
            for item in valid_items:
                rarity = item.get("rarity", "Common")
                weight = rarity_mods.get(rarity, 1.0)
                weighted_pool.extend([item] * int(weight * 10))  # Multiplier scale

            if not weighted_pool:
                print("[SHOP WARNING] No weighted items to choose from.")
                return None

            return random.choice(weighted_pool)

        except Exception as e:
            print("[SHOP ERROR] Failed to get random shop item.")
            traceback.print_exc()
            return None

    def get_rarity_modifiers(self):
        modifiers = {"Common": 1.0, "Uncommon": 1.0, "Rare": 1.0, "Epic": 1.0}
        for item in self.inventory:
            effect = item.get("effect")
            if effect == "uncommon_chance":
                modifiers["Uncommon"] += 0.5
            elif effect == "rare_chance":
                modifiers["Rare"] += 0.5
            elif effect == "epic_chance":
                modifiers["Epic"] += 0.5
        return modifiers

    def enter_shop_screen(self):
        print("[SHOP] Entering shop screen...")

        self.in_shop = True
        self.reroll_price = self.reroll_base_price  # ✅ Reset reroll cost

        # Transfer leftover points
        leftover = self.score - self.target_score
        print(f"[SHOP] Calculated leftover points: {leftover}")
        if leftover > 0:
            self.wallet += leftover
            print(f"[SHOP] Wallet updated: {self.wallet}")

        self.shop_selected_item_index = None
        self.shop_message = ""

        # Load shop item pool only once
        print(f"[SHOP] Attempting to load shop items from: {ITEMS}")
        try:
            with open(ITEMS, "r") as f:
                self.all_shop_items = json.load(f)
                print(f"[SHOP] Loaded {len(self.all_shop_items)} items from JSON.")

                # Sanity check first few items
                for idx, item in enumerate(self.all_shop_items[:3]):
                    print(f"[SHOP] Item {idx}: {item}")

        except Exception as e:
            print("[SHOP ERROR] Failed to load shop items.")
            traceback.print_exc()
            self.all_shop_items = []

        # Populate shop
        self.shop_items = []
        exclude_titles = {item["title"] for item in self.inventory}
        while len(self.shop_items) < 4:
            item = self.get_random_shop_item(exclude_titles)
            if item:
                self.shop_items.append(item)
                exclude_titles.add(item["title"])  # Update to prevent repeats
            else:
                break

        print("[SHOP] Shop screen setup complete. Calling update().")
        self.update()

    def draw_shop_overlay(self):
        try:
            overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 215))
            self.surface.blit(overlay, (0, 0))

            # Title
            title = self.gui_font.render("Welcome to the Shop", True, (255, 255, 255))
            self.surface.blit(title, (80, 60))

            # Draw shop items
            self.shop_button_rects = []
            base_y = 110
            for i, item in enumerate(self.shop_items):
                is_placeholder = item.get("placeholder", False)
                name = item.get("title", "???")
                cost = item.get("cost", 999)
                img_path = item.get("image", None)

                y = base_y + i * (TILE_HEIGHT + 30)
                item_rect = pygame.Rect(80, y, 400, TILE_HEIGHT + 10)

                # Load and blit image (even for placeholders if image exists)
                if img_path:
                    full_path = os.path.normpath(os.path.join(BASE_DIR, img_path))
                    if os.path.exists(full_path):
                        icon = pygame.image.load(full_path).convert_alpha()
                        icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                        self.surface.blit(icon, (90, y + 5))
                    else:
                        print(f"[SHOP WARNING] Icon not found at: {full_path}")

                # Set colors based on placeholder status
                name_color = (180, 180, 180) if is_placeholder else (255, 255, 255)
                name_text = self.item_font.render(name, True, name_color)
                self.surface.blit(name_text, (100 + TILE_WIDTH, y + 5))

                if not is_placeholder:
                    cost_text = self.money_font.render(f"{cost} pts", True, (255, 255, 100))
                    self.surface.blit(cost_text, (100 + TILE_WIDTH, y + TILE_HEIGHT // 2))

                self.shop_button_rects.append((item_rect, item))

            # Fonts & Colors
            btn_font = self.button_font
            btn_bg_color = (15, 15, 15, 38)  # Transparent dark
            btn_border_color = (0, 60, 0, 128)  # Semi-transparent green
            green_hover_color = (0, 125, 0)
            shadow_color = (0, 0, 0)

            # Common Y position
            button_y = 80 + len(self.shop_items) * (TILE_HEIGHT + 30) + 80
            btn_height = 60
            btn_shadow_offset = 2

            # --- Reroll Button (Left) ---
            reroll_width = 180
            reroll_x = 80
            reroll_rect = pygame.Rect(reroll_x, button_y, reroll_width, btn_height)
            self.button_rects["shop_reroll"] = reroll_rect

            # Hover check
            hovering_reroll = reroll_rect.collidepoint(pygame.mouse.get_pos())
            reroll_text_color = green_hover_color if hovering_reroll else green_hover_color

            pygame.draw.rect(self.surface, btn_bg_color, reroll_rect)
            pygame.draw.rect(self.surface, btn_border_color, reroll_rect, 3)

            reroll_label = btn_font.render(f"Reroll (-{self.reroll_price})", True, reroll_text_color)
            reroll_shadow = btn_font.render(f"Reroll (-{self.reroll_price})", True, shadow_color)
            self.surface.blit(reroll_shadow, (reroll_rect.centerx - reroll_label.get_width() // 2 + btn_shadow_offset,
                                              reroll_rect.centery - reroll_label.get_height() // 2 + btn_shadow_offset))
            self.surface.blit(reroll_label, (reroll_rect.centerx - reroll_label.get_width() // 2,
                                             reroll_rect.centery - reroll_label.get_height() // 2))

            # --- Booster Pack Button (Bottom Center) ---
            booster_width = 340
            booster_x = (self.surface.get_width() - booster_width) // 2
            booster_y = button_y + btn_height + 40
            booster_rect = pygame.Rect(booster_x, booster_y, booster_width, btn_height)
            self.button_rects["shop_booster"] = booster_rect

            hovering_booster = booster_rect.collidepoint(pygame.mouse.get_pos())
            booster_color = (180, 140, 0) if hovering_booster else (160, 120, 0)

            pygame.draw.rect(self.surface, btn_bg_color, booster_rect)
            pygame.draw.rect(self.surface, booster_color, booster_rect, 3)

            booster_label = btn_font.render(f"Buy Booster Pack (-{self.booster_pack_cost})", True, booster_color)
            booster_shadow = btn_font.render(f"Buy Booster Pack (-{self.booster_pack_cost})", True, shadow_color)
            self.surface.blit(booster_shadow,
                              (booster_rect.centerx - booster_label.get_width() // 2 + btn_shadow_offset,
                               booster_rect.centery - booster_label.get_height() // 2 + btn_shadow_offset))
            self.surface.blit(booster_label,
                              (booster_rect.centerx - booster_label.get_width() // 2,
                               booster_rect.centery - booster_label.get_height() // 2))

            # --- Continue Button (Right) ---
            continue_width = 260
            continue_x = self.surface.get_width() - continue_width - 750
            continue_rect = pygame.Rect(continue_x, button_y, continue_width, btn_height)
            self.button_rects["shop_continue"] = continue_rect

            hovering_continue = continue_rect.collidepoint(pygame.mouse.get_pos())
            continue_text_color = (0, 125, 0) if hovering_continue else (0, 125, 0)

            pygame.draw.rect(self.surface, btn_bg_color, continue_rect)
            pygame.draw.rect(self.surface, btn_border_color, continue_rect, 3)

            continue_label = btn_font.render("Continue", True, continue_text_color)
            continue_shadow = btn_font.render("Continue", True, shadow_color)
            self.surface.blit(continue_shadow,
                              (continue_rect.centerx - continue_label.get_width() // 2 + btn_shadow_offset,
                               continue_rect.centery - continue_label.get_height() // 2 + btn_shadow_offset))
            self.surface.blit(continue_label, (continue_rect.centerx - continue_label.get_width() // 2,
                                               continue_rect.centery - continue_label.get_height() // 2))

            self.action_bar.draw()


            # Message
            if self.shop_message:
                msg = self.gui_font.render(self.shop_message, True, (255, 100, 100))
                # self.surface.blit(msg, (80, cont_y - 40))

        except Exception as e:
            import traceback
            print("[DRAW SHOP ERROR]")
            traceback.print_exc()

    def attempt_purchase(self, item):
        PLACEHOLDER_ITEM = {
            "title": "Sold Out",
            "cost": 0,
            "image": "assets/sold_out.png",  # You can make a gray X or similar icon
            "placeholder": True
        }

        if item.get("placeholder"):
            self.shop_message = "This slot is empty!"
            print(f"[PURCHASE BLOCKED] Tried to buy placeholder: {item.get('title')}")
            return

        name = item.get("title", "???")
        cost = item.get("cost", 999)

        if self.wallet >= cost:
            if len(self.inventory) < 5:
                self.wallet -= cost
                self.inventory.append(item)

                # ✅ Replace item with placeholder, preserving slot
                for i, shop_item in enumerate(self.shop_items):
                    if shop_item == item:
                        self.shop_items[i] = PLACEHOLDER_ITEM.copy()
                        break

                self.shop_message = f"Purchased {name}!"
            else:
                self.shop_message = "Inventory Full!"
        else:
            self.shop_message = "Not enough points!"

    def trigger_encounter_effect(self):
        try:
            if self.encounter_mode == "west_wind":
                self.apply_west_wind_shift()
            elif self.encounter_mode == "east_wind":
                self.apply_east_wind_shift()
            elif self.encounter_mode == "north_wind":
                self.apply_north_wind_shift()
            elif self.encounter_mode == "south_wind":
                self.apply_south_wind_shift()
            elif self.encounter_mode == "slot_machine":
                self.apply_slot_machine_shift()
            elif self.encounter_mode == "rotate_cw":
                self.apply_rotate_cw()
            elif self.encounter_mode == "rotate_ccw":
                self.apply_rotate_ccw()
            elif self.encounter_mode == "parallax":
                self.apply_parallax_shift()
            elif self.encounter_mode == "crush":
                self.apply_crush_shift()
            elif self.encounter_mode == "fog of war":
                self.apply_fog_of_war()
            else:
                print(f"[WARN] Unknown encounter mode: {self.encounter_mode}")

            self.update_game_state()
        except Exception as e:
            print(f"[ERROR] Encounter effect '{self.encounter_mode}' failed: {e}")

    def debug_trigger_encounter(self):
        if self.encounter_mode:
            self.trigger_encounter_effect()

    def apply_fog_of_war(self):
        for tile in self.board:
            tile["fogged"] = not self.is_tile_selectable(tile)

        self.update_canvas()

    def clear_fog_of_war(self):
        for tile in self.board:
            tile.pop("fogged", None)
        self.update_canvas()

    def draw_booster_selector(self):
        # Transparent overlay (no fill color, just alpha surface)
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        self.surface.blit(overlay, (0, 0))

        # Position offset for the whole booster UI
        offset_x = 445
        offset_y = 200

        self.booster_button_rects = []

        # Title
        title = self.gui_font.render("Choose 3 Tiles", True, (255, 255, 255))
        self.surface.blit(title, (offset_x, offset_y))

        # Tile positioning
        spacing = TILE_WIDTH + 20
        start_x = 80 + offset_x
        tile_y = offset_y + 60  # 60px below the title

        for i, tile_name in enumerate(self.booster_choices):
            x = start_x + i * spacing
            rect = pygame.Rect(x, tile_y, TILE_WIDTH, TILE_HEIGHT)

            # ✅ Load from self.tile_images
            if tile_name in self.tile_images:
                img = self.tile_images[tile_name]
                scaled_img = pygame.transform.scale(img, (TILE_WIDTH, TILE_HEIGHT))
                self.surface.blit(scaled_img, (x, tile_y))

            # ✅ Draw green border if selected
            if i in self.booster_selected_indices:
                pygame.draw.rect(self.surface, (0, 255, 0), rect, 4)

            # ✅ Save clickable rect and tile name
            self.booster_button_rects.append((rect, tile_name))

        # --- Confirm Button ---
        confirm_enabled = len(self.booster_selected_indices) == 3
        confirm_color = (0, 150, 0) if confirm_enabled else (60, 60, 60)
        btn_y = tile_y + TILE_HEIGHT + 40

        confirm_rect = pygame.Rect(80 + offset_x, btn_y, 180, 50)
        self.button_rects["booster_confirm"] = confirm_rect

        pygame.draw.rect(self.surface, confirm_color, confirm_rect)
        label = self.button_font.render("Confirm", True, (255, 255, 255))
        self.surface.blit(label, (confirm_rect.centerx - label.get_width() // 2,
                                  confirm_rect.centery - label.get_height() // 2))

        # --- Skip Button ---
        skip_rect = pygame.Rect(300 + offset_x, btn_y, 180, 50)
        self.button_rects["booster_skip"] = skip_rect

        pygame.draw.rect(self.surface, (150, 0, 0), skip_rect)
        skip_label = self.button_font.render("Skip", True, (255, 255, 255))
        self.surface.blit(skip_label, (skip_rect.centerx - skip_label.get_width() // 2,
                                       skip_rect.centery - skip_label.get_height() // 2))

    def exit_booster_selector(self):
        self.show_booster_selector = False
        self.booster_choices = []
        self.booster_selected_indices.clear()

    def apply_wind_shift(self, dx: int, dy: int):
        directions = {
            (-1, 0): "west",
            (1, 0): "east",
            (0, -1): "north",
            (0, 1): "south"
        }
        self.current_wind_direction = directions.get((dx, dy), "unknown")
        print(f"🌬️ Applying Animated {self.current_wind_direction.capitalize()} Wind Shift")

        new_positions = {}
        animated_tiles = []
        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            # Skip covered or bottom tiles
            if gz == 0 or (gx, gy, gz + 1) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gx = gx + dx
            new_gy = gy + dy

            if not (self.min_grid_x <= new_gx <= self.max_grid_x) or \
                    not (self.min_grid_y <= new_gy <= self.max_grid_y):
                new_positions[(gx, gy, gz)] = tile
                continue

            if (new_gx, new_gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            # Descend to the highest unoccupied Z coordinate (lowest stack)
            new_gz = gz
            while new_gz > 0 and ((new_gx, new_gy, new_gz) in new_positions or (new_gx, new_gy, new_gz) in occupied):
                new_gz -= 1

            if (new_gx, new_gy, new_gz) in new_positions or (new_gx, new_gy, new_gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]

            tile["target_x"] = 80 + new_gx * TILE_WIDTH
            tile["target_y"] = 60 + new_gy * TILE_HEIGHT - new_gz * TILE_DEPTH

            tile["target_grid_x"] = new_gx
            tile["target_grid_y"] = new_gy
            tile["target_z"] = new_gz

            tile["alpha"] = 255
            tile["fading"] = True

            animated_tiles.append(tile)

        for tile in self.board:
            if tile not in animated_tiles:
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                new_positions[key] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

    def apply_west_wind_shift(self):
        self.current_wind_direction = "west"
        print("\U0001f32c️ Applying Animated West Wind Shift")

        new_positions = {}
        animated_tiles = []
        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx - 1, gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gx = gx - 1
            if new_gx < self.min_grid_x:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = gz
            while new_gz > 0 and ((new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied):
                new_gz -= 1

            if (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            abs_x, abs_y = self.get_tile_pixel_position(new_gx, gy, new_gz, TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH, self.offset_x, self.offset_y)
            tile.update({"start_x": tile["x"], "start_y": tile["y"], "target_x": abs_x, "target_y": abs_y,
                         "target_grid_x": new_gx, "target_grid_y": gy, "target_z": new_gz,
                         "alpha": 255, "fading": True})
            animated_tiles.append(tile)

        for tile in self.board:
            if tile not in animated_tiles:
                new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)


    def apply_east_wind_shift(self):
        self.current_wind_direction = "east"
        print("\U0001f32c️ Applying Animated East Wind Shift")

        new_positions = {}
        animated_tiles = []
        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx + 1, gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gx = gx + 1
            if new_gx > self.max_grid_x:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = gz
            while new_gz > 0 and ((new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied):
                new_gz -= 1

            if (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            abs_x, abs_y = self.get_tile_pixel_position(new_gx, gy, new_gz, TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH, self.offset_x, self.offset_y)
            tile.update({"start_x": tile["x"], "start_y": tile["y"], "target_x": abs_x, "target_y": abs_y,
                         "target_grid_x": new_gx, "target_grid_y": gy, "target_z": new_gz,
                         "alpha": 255, "fading": True})
            animated_tiles.append(tile)

        for tile in self.board:
            if tile not in animated_tiles:
                new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

    def apply_north_wind_shift(self):
        self.current_wind_direction = "north"
        print("\U0001f32c️ Applying Animated North Wind Shift")

        new_positions = {}
        animated_tiles = []
        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx, gy - 1, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gy = gy - 1
            if new_gy < self.min_grid_y:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = gz
            while new_gz > 0 and ((gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied):
                new_gz -= 1

            if (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            abs_x, abs_y = self.get_tile_pixel_position(gx, new_gy, new_gz, TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH,
                                                        self.offset_x, self.offset_y)
            tile.update({"start_x": tile["x"], "start_y": tile["y"], "target_x": abs_x, "target_y": abs_y,
                         "target_grid_x": gx, "target_grid_y": new_gy, "target_z": new_gz,
                         "alpha": 255, "fading": True})
            animated_tiles.append(tile)

        for tile in self.board:
            if tile not in animated_tiles:
                new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

    def apply_south_wind_shift(self):
        self.current_wind_direction = "south"
        print("🌬️ Applying Animated South Wind Shift")

        new_positions = {}
        animated_tiles = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            # Skip tiles that are on the ground level or already blocked in the direction of movement
            if gz == 0 or (gx, gy + 1, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gy = gy + 1

            if new_gy > self.max_grid_y:
                new_positions[(gx, gy, gz)] = tile
                continue

            # Descend to the highest unoccupied Z coordinate at new location
            new_gz = gz
            while new_gz > 0 and ((gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied):
                new_gz -= 1

            if (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            abs_x, abs_y = self.get_tile_pixel_position(
                gx, new_gy, new_gz,
                TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH,
                self.offset_x, self.offset_y
            )

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]
            tile["target_x"] = abs_x
            tile["target_y"] = abs_y
            tile["target_grid_x"] = gx
            tile["target_grid_y"] = new_gy
            tile["target_z"] = new_gz
            tile["alpha"] = 255
            tile["fading"] = True

            animated_tiles.append(tile)

        for tile in self.board:
            if tile not in animated_tiles:
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                new_positions[key] = tile

        self.encounter_engine.animate_wind_shift(
            animated_tiles, new_positions, steps=12, interval=30
        )

    def apply_slot_machine_shift(self):
        print("🎰 Applying Slot Machine Shift")

        from collections import defaultdict

        stack_map = defaultdict(list)
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"])
            stack_map[key].append(tile)

        for stack in stack_map.values():
            stack.sort(key=lambda t: t["z"])

        # Group by column
        column_map = defaultdict(list)
        for (gx, gy), stack in stack_map.items():
            column_map[gx].append((gy, stack))

        animated_tiles = []

        for gx, gy_stacks in column_map.items():
            gy_stacks.sort(key=lambda s: s[0])
            shift_amount = random.randint(1, 6)

            print(f"Column {gx}: shift {'↓' if gx % 2 == 0 else '↑'} by {shift_amount}")

            if gx % 2 == 0:  # Even columns go down
                for _ in range(shift_amount):
                    gy_stacks = gy_stacks[-1:] + gy_stacks[:-1]
            else:  # Odd columns go up
                for _ in range(shift_amount):
                    gy_stacks = gy_stacks[1:] + gy_stacks[:1]

            for new_gy, (_, stack) in zip(range(len(gy_stacks)), gy_stacks):
                for new_z, tile in enumerate(stack):
                    tile["start_y"] = tile["y"]
                    tile["target_y"] = 60 + new_gy * TILE_HEIGHT - new_z * TILE_DEPTH
                    tile["target_grid_y"] = new_gy
                    tile["target_z"] = new_z
                    tile["flicker"] = True  # Give slot tiles a flicker glow
                    tile["alpha"] = 255
                    animated_tiles.append(tile)

        self.encounter_engine.animate_slot_tiles(animated_tiles, steps=14, interval=20)

    def apply_rotate_cw(self):
        self.encounter_engine.animate_rotation(clockwise=True)

    def apply_rotate_ccw(self):
        self.encounter_engine.animate_rotation(clockwise=False)

    def apply_parallax_shift(self):
        if not self.board:
            return

        tile_w, tile_h, tile_d = TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH
        offset_x, offset_y = self.offset_x, self.offset_y

        # Group tiles by column
        columns = {}
        for tile in self.board:
            gx = tile["grid_x"]
            columns.setdefault(gx, []).append(tile)

        all_columns = sorted(columns.keys())
        if not all_columns or len(all_columns) % 2 != 0:
            print("[ERROR] Parallax requires an even number of columns.")
            return

        if self.current_column_order is None:
            self.current_column_order = all_columns.copy()

        col_order = self.current_column_order
        col_count = len(col_order)
        half = col_count // 2
        left_cols = col_order[:half]
        right_cols = col_order[half:]

        new_order = [None] * col_count

        # Handle left side
        for i, col in enumerate(left_cols):
            if i + 1 < half:
                new_order[i + 1] = col  # Shift right
            else:
                new_order[0] = col  # Wrap to leftmost

        # Handle right side
        for i, col in enumerate(reversed(right_cols)):
            index = col_count - 1 - i
            if index - 1 >= half:
                new_order[index - 1] = col  # Shift left
            else:
                new_order[-1] = col  # Wrap to rightmost

        # Build shift map
        shift_map = {old: new for old, new in zip(col_order, new_order)}
        self.current_column_order = new_order

        animated_tiles = []
        used_targets = set()

        for gx, stack in columns.items():
            target_gx = shift_map.get(gx, gx)

            # Prevent duplicate column assignments in animation
            while target_gx in used_targets:
                target_gx += 1 if target_gx > gx else -1
            used_targets.add(target_gx)

            for tile in stack:
                abs_x, abs_y = self.get_tile_pixel_position(
                    target_gx, tile["grid_y"], tile["z"],
                    tile_w, tile_h, tile_d, offset_x, offset_y
                )

                tile["start_x"] = tile["x"]
                tile["target_x"] = abs_x
                tile["target_grid_x"] = target_gx
                tile["fading"] = (gx in [col_order[0], col_order[-1]])  # edge fades
                tile["alpha"] = 255
                animated_tiles.append(tile)

        self.encounter_engine.animate_parallax_tiles(animated_tiles, steps=10, interval=30)

    def apply_crush_shift(self):
        print("⚙️ Applying Crush Shift (animated 4-stack crush)")

        from collections import defaultdict
        rows = defaultdict(list)
        for tile in self.board:
            rows[tile["grid_y"]].append(tile)

        max_stack_height = 4
        animated_tiles = []

        for gy, row_tiles in rows.items():
            left = [t for t in row_tiles if t["grid_x"] < self.center_x]
            right = [t for t in row_tiles if t["grid_x"] > self.center_x]
            stationary = [t for t in row_tiles if t["grid_x"] == self.center_x]

            left_sorted = sorted(left, key=lambda t: -t["grid_x"])
            right_sorted = sorted(right, key=lambda t: t["grid_x"])

            placed = {}

            def find_stack_spot(gx, name):
                stack = [pos for pos in placed if pos[0] == gx and pos[1] == gy]
                stack.sort(key=lambda pos: pos[2])
                if any(placed[pos]["name"] == name for pos in stack):
                    return None
                return len(stack) if len(stack) < max_stack_height else None

            for tile in stationary:
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                placed[key] = tile
                tile["alpha"] = 255  # fully opaque

            for tile in left_sorted:
                new_x = tile["grid_x"] + 1
                z_spot = find_stack_spot(new_x, tile["name"])
                if z_spot is not None:
                    gx, gz = new_x, z_spot
                    tx = 80 + gx * TILE_WIDTH
                    ty = 60 + gy * TILE_HEIGHT - gz * TILE_DEPTH
                    tile["start_x"] = tile["x"]
                    tile["start_y"] = tile["y"]
                    tile["target_x"] = tx
                    tile["target_y"] = ty
                    tile["target_grid_x"] = gx
                    tile["target_grid_y"] = gy
                    tile["target_z"] = gz
                    tile["fading"] = True
                    tile["alpha"] = 255
                    animated_tiles.append(tile)
                else:
                    placed[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

            for tile in right_sorted:
                new_x = tile["grid_x"] - 1
                z_spot = find_stack_spot(new_x, tile["name"])
                if z_spot is not None:
                    gx, gz = new_x, z_spot
                    tx = 80 + gx * TILE_WIDTH
                    ty = 60 + gy * TILE_HEIGHT - gz * TILE_DEPTH
                    tile["start_x"] = tile["x"]
                    tile["start_y"] = tile["y"]
                    tile["target_x"] = tx
                    tile["target_y"] = ty
                    tile["target_grid_x"] = gx
                    tile["target_grid_y"] = gy
                    tile["target_z"] = gz
                    tile["fading"] = True
                    tile["alpha"] = 255
                    animated_tiles.append(tile)
                else:
                    placed[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

        self.encounter_engine.animate_crush_tiles(animated_tiles, steps=12, interval=25)

    def rebuild_tile_positions(self):
        self.tile_positions.clear()
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"], tile["z"])
            self.tile_positions[key] = tile

    def get_modified_rarity_weights(self):
        weights = self.base_rarity_weights.copy()

        for item in self.player_inventory:  # Assume this is a list of item dicts
            effect = item.get("effect")

            if effect == "uncommon_chance":
                weights["Uncommon"] += 15
                weights["Common"] -= 10
            elif effect == "rare_chance":
                weights["Rare"] += 10
                weights["Uncommon"] -= 5
            elif effect == "epic_chance":
                weights["Epic"] += 5
                weights["Rare"] -= 3

        # Clamp negative values and normalize (optional)
        for rarity in weights:
            weights[rarity] = max(0, weights[rarity])

        return weights

    def shuffle_board(self):
        if not self.board:
            print("[SHUFFLE] No tiles to shuffle.")
            return

        print("[SHUFFLE] Shuffling board...")

        # Extract all movable tile names
        tile_names = [tile["name"] for tile in self.board]

        # Shuffle the tile names
        random.shuffle(tile_names)

        # Reassign names to tiles
        for tile, new_name in zip(self.board, tile_names):
            tile["name"] = new_name

        # Optional: reset selected tiles
        self.selected_tiles.clear()

        # Optional: feedback
        # self.play_sound("shuffle")  # Stub, define if you want audio
        # self.show_temp_popup("Tiles shuffled!", duration=1000)

        # Optional: mark all as unexposed and recalculate visibility
        for tile in self.board:
            tile.pop("will_become_exposed", None)
        # self.recalculate_exposures()

    def hint_possible_matches(self):
        if not self.board or not self.selected_tiles:
            print("[HINT] No tile selected or board is empty.")
            return

        selected_tile = self.selected_tiles[0]
        selected_name = selected_tile["name"]

        # Find all tiles that match the selected name and are selectable
        matching_tiles = [
            tile for tile in self.board
            if tile["name"] == selected_name and tile != selected_tile and self.is_tile_selectable(tile)
        ]

        if not matching_tiles:
            print(f"[HINT] No matching tiles found for: {selected_name}")
            return

        print(f"[HINT] Showing possible matches for: {selected_name}")

        for tile in matching_tiles:
            for _ in range(30):
                self.particles.append(SelectedParticle_B(tile["x"], tile["y"], TILE_WIDTH, TILE_HEIGHT))

        self.update()

    def swap_tarot_tiles_moon_sun(self):
        board = self.board.copy()
        sun_tiles = [tile for tile in board if tile.tarot == 'thesun']
        moon_tiles = [tile for tile in board if tile.tarot == 'themoon']

        count = min(len(sun_tiles), len(moon_tiles))
        for i in range(count):
            sun = sun_tiles[i]
            moon = moon_tiles[i]

            # Swap positions
            sun.grid_x, moon.grid_x = moon.grid_x, sun.grid_x
            sun.grid_y, moon.grid_y = moon.grid_y, sun.grid_y
            sun.z, moon.z = moon.z, sun.z

            # Optional: swap screen positions (if calculated already)
            sun.x, moon.x = moon.x, sun.x
            sun.y, moon.y = moon.y, sun.y

        return board

    def handle_lycan_match(self, tile, lycanthrope_active: bool) -> int:
        increase = 0
        if lycanthrope_active and tile == "themoon" and self.combo_level < self.combo_max_level:
            increase = 1
        return increase

    def has_lycanthrope_item(self) -> bool:
        for item in self.inventory:
            if item.get("unique_id") == "lycanthrope":
                return True
        return False



if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = MahjongGame()
    game.show()
    sys.exit(app.exec_())

