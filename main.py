import sys
import os
import random
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
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer
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
PAIR_COUNT = 7
STACK_HEIGHT = 4
NUM_ROWS = 6
ACTION_BAR_HEIGHT = 80


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
            self.setGeometry(100, 100, 1000, 800)
            self.ACTION_BAR_HEIGHT = 80
            self.debug = False
            self.base_score = 5
            self.encounter_engine = EncounterEngine(self)
            self.in_shop = False
            self.in_game_over = False
            self.game_over_button_rect = pygame.Rect(80, 400, 200, 40)  # Same size as shop_continue
            self.game_over_flash_toggle = True
            self.last_flash_time = pygame.time.get_ticks()
            self.flash_interval = 500  # milliseconds

            self.board = []
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

        layout.addLayout(btns)
        self.canvas_label = QLabel()
        # self.canvas_label.mousePressEvent = self.handle_click
        self.canvas_label.mousePressEvent = self.mousePressEvent
        layout.addWidget(self.canvas_label)

        self.setLayout(layout)

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
        y = self.action_bar_top - 10
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
                    # (optional) trigger item logic here
                    handled = True

                elif name == "shop_continue":
                    print("[CLICK] shop_continue confirmed")
                    self.start_new_round()
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

        if self.in_game_over:
            if self.game_over_button_rect.collidepoint(x, y):
                print("[CLICK] Start New Game from Game Over screen")
                self.in_game_over = False
                self.reset_game_state()
                self.start_new_round()
                return

        # Tile selection fallback
        self.handle_click(event)


    def handle_mouse_up(self, event):
        self.dragging_volume = False

    def mouseReleaseEvent(self, event):
        self.handle_mouse_up(event)

        self.dragging_volume_slider = False

    def mouseMoveEvent(self, event):
        x = event.pos().x()
        y = event.pos().y()

        # Track hover index
        self.hovered_inventory_index = None
        for i in range(5):
            rect = self.button_rects.get(f"inventory_{i}")
            if rect and rect.collidepoint(x, y):
                self.hovered_inventory_index = i
                break

        if self.dragging_volume_slider:
            self.update_volume_from_mouse(event.pos().x())

        self.update()  # Redraw with updated hover state

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

        tile_names = list(self.tile_images.keys())
        if not tile_names:
            print("No tiles loaded.")
            return

        chosen = random.sample(tile_names, min(len(tile_names), 144 // PAIR_COUNT))
        name_pool = []
        for name in chosen:
            name_pool.extend([name] * PAIR_COUNT)

        random.shuffle(name_pool)
        layout = []
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

        margin_x = 80
        margin_y = 60

        for i, (gx, gy, gz) in enumerate(layout):
            if i >= len(name_pool):
                break
            abs_x = margin_x + gx * TILE_WIDTH
            abs_y = margin_y + gy * TILE_HEIGHT - gz * 10
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

        # 🛠️ Add this block to compute bounds for encounter effects
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
        # Scroll background first
        self.bg_scroll_x = (self.bg_scroll_x + self.bg_scroll_speed_x) % self.background_tile.get_width()
        self.bg_scroll_y = (self.bg_scroll_y + self.bg_scroll_speed_y) % self.background_tile.get_height()

        # Then redraw everything
        self.update_canvas()

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
        self.draw_overlays()
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
        top_tiles = {
            (tile["grid_x"], tile["grid_y"]): tile
            for tile in self.board
            if
            tile not in self.animating_tiles and (tile["grid_x"], tile["grid_y"], tile["z"]) not in self.fading_coords
        }

        for tile in self.board:
            gx, gy = tile["grid_x"], tile["grid_y"]
            if (gx, gy) in vacated:
                continue
            top = top_tiles.get((gx, gy))
            if top and top["z"] > tile["z"]:
                shadow = pygame.Surface((TILE_WIDTH, TILE_HEIGHT), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 200))
                self.surface.blit(shadow, (tile["x"], tile["y"]))

    def clear_background(self):
        self.surface.fill((0, 80, 80))

    def draw_background_tiles(self):
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
                self.shop.enter_shop_screen()

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

    def enter_shop_screen(self):
        print("[SHOP] Entering shop screen...")

        self.in_shop = True

        # Transfer leftover points
        leftover = self.score - self.target_score
        print(f"[SHOP] Calculated leftover points: {leftover}")
        if leftover > 0:
            self.wallet += leftover
            print(f"[SHOP] Wallet updated: {self.wallet}")

        self.shop_selected_item_index = None
        self.shop_message = ""

        # Load shop item pool
        print(f"[SHOP] Attempting to load shop items from: {ITEMS}")
        try:
            with open(ITEMS, "r") as f:
                all_items = json.load(f)
                print(f"[SHOP] Loaded {len(all_items)} items from JSON.")

                # Sanity check first few items
                for idx, item in enumerate(all_items[:3]):
                    print(f"[SHOP] Item {idx}: {item}")

                k = min(4, len(all_items))
                if k > 0:
                    self.shop_items = random.sample(all_items, k=k)
                    print(f"[SHOP] Selected {k} random shop items.")
                else:
                    print("[SHOP WARNING] No items found in JSON.")
                    self.shop_items = []

        except Exception as e:
            print("[SHOP ERROR] Failed to load shop items.")
            traceback.print_exc()
            print(f"[SHOP ERROR] Exception: {e}")
            self.shop_items = []

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

            # Wallet
            wallet = self.money_font.render(f"Wallet: {self.wallet} pts", True, (255, 255, 100))
            self.surface.blit(wallet, (80, 100))

            # Draw shop items
            self.shop_button_rects = []
            base_y = 150
            for i, item in enumerate(self.shop_items):
                name = item.get("title", "???")
                cost = item.get("cost", 999)
                img_path = item.get("image", None)

                y = base_y + i * (TILE_HEIGHT + 30)
                item_rect = pygame.Rect(80, y, 400, TILE_HEIGHT + 10)

                # Load and blit image
                if img_path:
                    full_path = os.path.normpath(os.path.join(BASE_DIR, img_path))
                    if os.path.exists(full_path):
                        icon = pygame.image.load(full_path).convert_alpha()
                        icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                        self.surface.blit(icon, (90, y + 5))
                    else:
                        print(f"[SHOP WARNING] Icon not found at: {full_path}")

                # Draw name & price
                name_text = self.item_font.render(name, True, (255, 255, 255))
                cost_text = self.money_font.render(f"{cost} pts", True, (255, 255, 100))
                self.surface.blit(name_text, (100 + TILE_WIDTH, y + 5))
                self.surface.blit(cost_text, (100 + TILE_WIDTH, y + TILE_HEIGHT // 2))

                self.shop_button_rects.append((item_rect, item))

            # Fonts & Colors
            btn_font = self.button_font
            btn_bg_color = (15, 15, 15, 38)  # Transparent dark
            btn_border_color = (0, 60, 0, 128)  # Semi-transparent green
            green_hover_color = (0, 125, 0)
            shadow_color = (0, 0, 0)

            # Common Y position
            button_y = 150 + len(self.shop_items) * (TILE_HEIGHT + 30) + 80
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

            reroll_label = btn_font.render("Reroll (-50)", True, reroll_text_color)
            reroll_shadow = btn_font.render("Reroll (-50)", True, shadow_color)
            self.surface.blit(reroll_shadow, (reroll_rect.centerx - reroll_label.get_width() // 2 + btn_shadow_offset,
                                              reroll_rect.centery - reroll_label.get_height() // 2 + btn_shadow_offset))
            self.surface.blit(reroll_label, (reroll_rect.centerx - reroll_label.get_width() // 2,
                                             reroll_rect.centery - reroll_label.get_height() // 2))

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

            # Inventory view
            self.surface.blit(self.gui_font.render("Inventory:", True, (255, 255, 255)), (500, 150))
            for i in range(5):
                x = 500 + i * (TILE_WIDTH + 10)
                y = 190
                rect = pygame.Rect(x, y, TILE_WIDTH, TILE_HEIGHT)
                pygame.draw.rect(self.surface, (15, 15, 15), rect)
                pygame.draw.rect(self.surface, (0, 60, 0), rect, 2)
                if i < len(self.inventory):
                    inv_item = self.inventory[i]
                    icon_path = inv_item.get("image", None)
                    if icon_path:
                        full_path = os.path.join(BASE_DIR, icon_path)
                        if os.path.exists(full_path):
                            icon = pygame.image.load(full_path).convert_alpha()
                            icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                            self.surface.blit(icon, (x, y))
                self.button_rects[f"inventory_{i}"] = rect

            # Continue Button (bottom right)
            cont_width, cont_height = 240, 40
            cont_x = self.surface.get_width() - cont_width - 40
            cont_y = self.surface.get_height() - cont_height - 30


            # Message
            if self.shop_message:
                msg = self.gui_font.render(self.shop_message, True, (255, 100, 100))
                self.surface.blit(msg, (80, cont_y - 40))

        except Exception as e:
            import traceback
            print("[DRAW SHOP ERROR]")
            traceback.print_exc()

    def attempt_purchase(self, item):
        name = item.get("title", "???")
        cost = item.get("cost", 999)

        print(f"[PURCHASE] Wallet: {self.wallet}, Cost: {cost}")

        if self.wallet >= cost:
            if len(self.inventory) < 5:
                self.wallet -= cost
                self.inventory.append(item)
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

    def apply_west_wind_shift(self):
        self.current_wind_direction = "west"

        print("🌬️ Applying Animated West Wind Shift")

        new_positions = {}
        animated_tiles = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            # Covered or bottom tile — skip movement
            if gz == 0 or (gx, gy, gz + 1) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gx = gx - 1
            if new_gx < self.min_grid_x or (new_gx, gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = 0
            while (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                new_gz += 1

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]

            tile["target_x"] = 80 + new_gx * TILE_WIDTH
            tile["target_y"] = 60 + gy * TILE_HEIGHT - new_gz * TILE_DEPTH

            tile["target_grid_x"] = new_gx
            tile["target_grid_y"] = gy
            tile["target_z"] = new_gz

            tile["alpha"] = 255
            tile["fading"] = True

            animated_tiles.append(tile)

        # Preserve position of non-moving tiles
        for tile in self.board:
            if tile not in animated_tiles:
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                new_positions[key] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

    def apply_east_wind_shift(self):
        self.current_wind_direction = "east"

        print("🌬️ Applying Animated East Wind Shift")

        new_positions = {}
        animated_tiles = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx, gy, gz + 1) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gx = gx + 1
            if new_gx > self.max_grid_x or (new_gx, gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = 0
            while (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                new_gz += 1

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]

            tile["target_x"] = 80 + new_gx * TILE_WIDTH
            tile["target_y"] = 60 + gy * TILE_HEIGHT - new_gz * TILE_DEPTH

            tile["target_grid_x"] = new_gx
            tile["target_grid_y"] = gy
            tile["target_z"] = new_gz

            tile["alpha"] = 255
            tile["fading"] = True

            animated_tiles.append(tile)

        # Preserve all tiles that didn't move
        for tile in self.board:
            if tile not in animated_tiles:
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                new_positions[key] = tile

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

    def apply_north_wind_shift(self):
        self.current_wind_direction = "north"
        print("🌬️ Applying Animated North Wind Shift")

        new_positions = {}
        animated_tiles = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx, gy, gz + 1) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gy = gy - 1
            if new_gy < self.min_grid_y or (gx, new_gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = 0
            while (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                new_gz += 1

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]

            tile["target_x"] = 80 + gx * TILE_WIDTH
            tile["target_y"] = 60 + new_gy * TILE_HEIGHT - new_gz * TILE_DEPTH

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

            if gz == 0 or (gx, gy, gz + 1) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gy = gy + 1
            if new_gy > self.max_grid_y or (gx, new_gy, gz) in occupied:
                new_positions[(gx, gy, gz)] = tile
                continue

            new_gz = 0
            while (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                new_gz += 1

            tile["start_x"] = tile["x"]
            tile["start_y"] = tile["y"]

            tile["target_x"] = 80 + gx * TILE_WIDTH
            tile["target_y"] = 60 + new_gy * TILE_HEIGHT - new_gz * TILE_DEPTH

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

        self.encounter_engine.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

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

        min_x = min(tile["grid_x"] for tile in self.board)
        max_x = max(tile["grid_x"] for tile in self.board)
        center_x = (min_x + max_x) / 2

        columns = {}
        for tile in self.board:
            gx = tile["grid_x"]
            columns.setdefault(gx, []).append(tile)

        used_columns = set()
        animated_tiles = []

        def find_nearest_unoccupied_column(target, direction):
            offset = 1
            while True:
                candidate = target + direction * offset
                if candidate in used_columns:
                    offset += 1
                    continue
                if direction < 0 and candidate >= min_x:
                    return candidate
                elif direction > 0 and candidate <= max_x:
                    return candidate
                else:
                    return target

        for gx in sorted(columns.keys()):
            stack = columns[gx]
            if gx < center_x:
                target_gx = gx - 1
                if target_gx < min_x or target_gx in used_columns:
                    target_gx = find_nearest_unoccupied_column(int(center_x), 1)
            elif gx > center_x:
                target_gx = gx + 1
                if target_gx > max_x or target_gx in used_columns:
                    target_gx = find_nearest_unoccupied_column(int(center_x), -1)
            else:
                target_gx = gx

            used_columns.add(target_gx)

            for tile in stack:
                tile["start_x"] = tile["x"]
                tile["target_x"] = 80 + target_gx * TILE_WIDTH
                tile["grid_x"] = target_gx
                tile["fading"] = (gx == min_x or gx == max_x)  # True if from edge column
                tile["alpha"] = 255  # full opacity to start
                animated_tiles.append(tile)

        self.encounter_engine.animate_parallax_tiles(animated_tiles, steps=10, interval=30)

    def rotate_local_blocks(self, clockwise=True):
        if not self.board:
            return

        new_board = []
        new_positions = {}
        visited = set()

        # Group tiles into 3x3 blocks by their top-left origin
        blocks = {}
        for tile in self.board:
            gx, gy = tile["grid_x"], tile["grid_y"]
            block_x = (gx // 3) * 3
            block_y = (gy // 3) * 3
            blocks.setdefault((block_x, block_y), []).append(tile)

        for (bx, by), tiles in blocks.items():
            # Build local 3x3 grid: tile_map[y][x] = tile
            grid = [[None for _ in range(3)] for _ in range(3)]
            for tile in tiles:
                local_x = tile["grid_x"] - bx
                local_y = tile["grid_y"] - by
                if 0 <= local_x < 3 and 0 <= local_y < 3:
                    grid[local_y][local_x] = tile

            # Rotate grid
            rotated = [[None for _ in range(3)] for _ in range(3)]
            for y in range(3):
                for x in range(3):
                    tile = grid[y][x]
                    if tile:
                        if clockwise:
                            new_x, new_y = 2 - y, x
                        else:
                            new_x, new_y = y, 2 - x

                        # Update tile position
                        tile["grid_x"] = bx + new_x
                        tile["grid_y"] = by + new_y
                        tile["x"] = 80 + tile["grid_x"] * TILE_WIDTH
                        tile["y"] = 60 + tile["grid_y"] * TILE_HEIGHT - tile["z"] * TILE_DEPTH

                        key = (tile["grid_x"], tile["grid_y"], tile["z"])
                        new_positions[key] = tile
                        new_board.append(tile)

        self.board = new_board
        self.tile_positions = new_positions
        self.normalize_stacks()
        self.update_canvas()  # Fixed

    def normalize_stacks(self):
        from collections import defaultdict
        column_groups = defaultdict(list)

        # Group tiles by (grid_x, grid_y)
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"])
            column_groups[key].append(tile)

        # Repack each column's stack bottom-up
        new_positions = {}
        for (gx, gy), tiles in column_groups.items():
            sorted_tiles = sorted(tiles, key=lambda t: t["z"])
            for new_z, tile in enumerate(sorted_tiles):
                tile["z"] = new_z
                tile["x"] = 80 + gx * TILE_WIDTH
                tile["y"] = 60 + gy * TILE_HEIGHT - new_z * TILE_DEPTH
                new_positions[(gx, gy, new_z)] = tile

        self.tile_positions = new_positions

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



if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = MahjongGame()
    game.show()
    sys.exit(app.exec_())

