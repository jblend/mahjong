import sys
import os
import random
import pygame
import time
import math
import traceback
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5 import QtGui, QtCore
from matplotlib import cm
from matplotlib.colors import Normalize

from assets.fx.particle import SmokeParticle, SparkleParticle, FireParticle, WindParticle
from music import MusicManager


TILES_ROOT = "./assets/tiles/classic"
BG_ROOT = "./assets/bg"
TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
PAIR_COUNT = 7
STACK_HEIGHT = 4
NUM_ROWS = 6

tile_particle_map = {
    "Tower": SmokeParticle,
    "Star": SparkleParticle,
    "Sun": FireParticle,
    "Moon": SparkleParticle,
    "Devil": SmokeParticle,
}

class MahjongGame(QWidget):
    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle("Mahjong Pygame + Qt5")
            self.setGeometry(100, 100, 1000, 800)

            self.board = []
            self.tile_positions = {}
            self.selected_tiles = []
            self.matched_pairs = {}
            self.wallet = 0
            self.score = 0
            self.round_number = 1
            self.match_count = 0
            self.tile_match_count = {}  # e.g., {"Tower": 2, "Moon": 1}
            self.combo_multiplier = 1
            self.target_score = self.calculate_target_score()

            # For UI tracking
            self.button_rects = {}
            self.dragging_volume = False
            self.music_volume = 0.015

            self.particles = []

            # Combo timer
            self.combo_timer = QTimer()
            self.combo_timer.setInterval(10000)
            self.combo_timer.timeout.connect(self.reset_combo)
            self.combo_display_start = 0
            self.combo_display_duration = 10000  # 10 seconds, in ms

            print("[INIT] Combo timer connected.")

            self.combo_label = QLabel("", self)
            self.combo_label.setStyleSheet("color: gold; font-size: 24px; font-weight: bold;")
            self.combo_label.move(100, 50)  # Adjust as needed
            self.combo_label.hide()

            self.combo_display_text = ""
            self.combo_display_time = 0
            self.combo_display_duration = 1000  # ms

            self.combo_anim = QPropertyAnimation(self.combo_label, b"pos")
            self.combo_anim.setDuration(500)
            self.combo_anim.setEasingCurve(QEasingCurve.OutBounce)

            self.last_match_time = None
            self.encounter_mode = None
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
            except pygame.error as e:
                print(f"[ERROR] Could not initialize mixer: {e}")
                # Optional: set fallback or disable music

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
            self.match_sound.set_volume(0.5)  # Optional

            font_path = os.path.join("assets", "fonts", "OldeEnglishRegular-Zd2J.ttf")
            self.combo_font = pygame.font.Font(font_path, 36)  # 36pt size

            self.background_tile = pygame.image.load(bg_path).convert()
            self.bg_scroll_x = 0
            self.bg_scroll_y = 0
            self.bg_scroll_speed_x = 0.5  # Adjust as needed
            self.bg_scroll_speed_y = 0.25


            self.surface = pygame.Surface((900, 900))

            self.tile_images = {}
            self.load_tileset_images()

            self.init_ui()

            self.timer = QTimer()
            self.timer.timeout.connect(self.update_canvas)
            self.timer.timeout.connect(self.tick)  # This will call tick() every 30 ms
            self.timer.start(30)

            self.new_game()
        except Exception as e:
            print("[FATAL ERROR IN __init__]:", e)
            traceback.print_exc()

    def init_ui(self):
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
        new_game_btn.clicked.connect(self.start_new_round)
        btns.addWidget(new_game_btn)

        debug_score = QPushButton("Add 100 Score")
        debug_score.clicked.connect(lambda: self.modify_score("Debug", 100))
        btns.addWidget(debug_score)

        end_round = QPushButton("End Round")
        end_round.clicked.connect(self.start_new_round)
        btns.addWidget(end_round)

        trigger_encounter = QPushButton("Trigger Encounter")
        trigger_encounter.clicked.connect(self.trigger_encounter_effect)
        btns.addWidget(trigger_encounter)

        layout.addLayout(btns)
        self.canvas_label = QLabel()
        self.canvas_label.mousePressEvent = self.handle_click
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

    def calculate_target_score(self):
        return 200 + 100 * (self.round_number - 1)

    def modify_score(self, tile_name, base_points=5):
        self.combo_display_start = pygame.time.get_ticks()
        self.combo_display_text = f"Combo x{self.combo_multiplier}!"
        self.combo_display_start = pygame.time.get_ticks()
        self.combo_end_time = self.combo_display_start + self.combo_display_duration  # 10 seconds
        self.combo_fade_duration = 2000  # ms fade out after timer ends

        # Track tile match count
        count = self.tile_match_count.get(tile_name, 0) + 1
        self.tile_match_count[tile_name] = count

        # Time-based combo logic
        now = time.time()
        if self.last_match_time and (now - self.last_match_time) <= 10:
            self.combo_multiplier += 1
            self.combo_timer.start()
        else:
            self.combo_multiplier = 1
            self.combo_timer.start()

        self.last_match_time = now

        # Score calculation
        tile_multiplier = count
        total_multiplier = tile_multiplier * self.combo_multiplier
        total_points = base_points * total_multiplier
        self.score += total_points

        self.score_label.setText(f"Score: {self.score}")

        # Set combo display
        if self.combo_multiplier > 1:
            self.combo_display_text = f"Combo x{self.combo_multiplier}!"
            self.combo_display_time = pygame.time.get_ticks()

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
        else:
            return  # Combo fully expired, don't draw

        color = self.get_combo_color(self.combo_multiplier)
        text_surface = self.combo_font.render(self.combo_display_text, True, color)
        text_surface.set_alpha(alpha)

        text_rect = text_surface.get_rect(center=(self.surface.get_width() // 2,
                                                  self.surface.get_height() - 40))
        self.surface.blit(text_surface, text_rect)
    def reset_combo(self):
        self.combo_multiplier = 1
        self.combo_timer.stop()
        self.last_match_time = None

        self.combo_display_text = ""
        self.combo_display_start = 0

    def draw_score_text(self):
        score_color = (255, 255, 255)  # White or any desired color
        score_text = f"Score: {self.score}"
        score_surface = self.combo_font.render(score_text, True, score_color)

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

    def draw_action_bar(self):
        surface_w = self.surface.get_width()
        surface_h = self.surface.get_height()
        bar_y = surface_h - 100
        padding = 20

        # Fonts
        font = self.combo_font

        # 🧮 Score
        score_surface = font.render(f"Score: {self.score}", True, (255, 255, 255))
        self.surface.blit(score_surface, (padding, bar_y + 10))

        # 💰 Wallet
        wallet_surface = font.render(f"Wallet: {self.wallet}", True, (200, 200, 100))
        self.surface.blit(wallet_surface, (padding, bar_y + 45))

        # 🔥 Combo (if active)
        now = pygame.time.get_ticks()
        if self.combo_display_text and now < self.combo_end_time + self.combo_fade_duration:
            alpha = 255
            if now > self.combo_end_time:
                fade_elapsed = now - self.combo_end_time
                progress = fade_elapsed / self.combo_fade_duration
                alpha = int(255 * (1 - progress ** 2))

            combo_color = self.get_combo_color(self.combo_multiplier)
            combo_surface = font.render(self.combo_display_text, True, combo_color)
            combo_surface.set_alpha(alpha)
            combo_rect = combo_surface.get_rect(center=(surface_w // 2, bar_y - 10))

            self.surface.blit(combo_surface, combo_rect)

        # 🧩 Match Count
        matches_surface = font.render(f"Possible Matches: {self.get_possible_match_count()}", True, (180, 180, 255))
        self.surface.blit(matches_surface, (surface_w - 250, bar_y + 10))

        # 🎵 Music Controls
        music_label = font.render("Music", True, (255, 255, 255))
        self.surface.blit(music_label, (padding + 250, bar_y + 10))

        button_size = 40  # or whatever size your buttons are

        # ⏮️ Previous Track
        prev_rect = pygame.Rect(padding + 250, bar_y + 45, button_size, button_size)
        pygame.draw.rect(self.surface, (70, 70, 120), prev_rect)
        pygame.draw.rect(self.surface, (200, 200, 255), prev_rect, 2)
        scaled_prev = pygame.transform.smoothscale(self.icon_images["prev"], (button_size - 10, button_size - 10))
        prev_icon_rect = scaled_prev.get_rect(center=prev_rect.center)
        self.surface.blit(scaled_prev, prev_icon_rect)
        self.button_rects["prev_track"] = prev_rect

        # ⏭️ Next Track
        next_rect = pygame.Rect(padding + 250 + 50, bar_y + 45, button_size, button_size)
        pygame.draw.rect(self.surface, (70, 70, 120), next_rect)
        pygame.draw.rect(self.surface, (200, 200, 255), next_rect, 2)
        scaled_next = pygame.transform.smoothscale(self.icon_images["next"], (button_size - 10, button_size - 10))
        next_icon_rect = scaled_next.get_rect(center=next_rect.center)
        self.surface.blit(scaled_next, next_icon_rect)
        self.button_rects["next_track"] = next_rect

        # 🔊 Volume Slider (horizontal bar with knob)
        vol_x = padding + 360
        vol_y = bar_y + 60
        vol_width = 100
        vol_height = 6
        vol_knob_radius = 6
        pygame.draw.rect(self.surface, (150, 150, 150), (vol_x, vol_y, vol_width, vol_height))
        knob_x = vol_x + int(self.music_volume * vol_width)
        pygame.draw.circle(self.surface, (255, 255, 255), (knob_x, vol_y + vol_height // 2), vol_knob_radius)

        # Volume icon (optional)
        volume_icon = self.icon_images["volume"]
        self.surface.blit(volume_icon, (vol_x - 20, vol_y - 4))

        self.button_rects["volume_slider"] = pygame.Rect(vol_x, vol_y - vol_knob_radius, vol_width, vol_knob_radius * 2)

        # Knob position
        knob_x = vol_x + int(self.music_volume * vol_width)
        pygame.draw.circle(self.surface, (255, 255, 255), (knob_x, vol_y + vol_height // 2), vol_knob_radius)

        # Interaction rect
        self.button_rects["volume_slider"] = pygame.Rect(
            vol_x, vol_y - vol_knob_radius, vol_width, vol_knob_radius * 2
        )

        # 🎒 Inventory (5 slots)
        slot_w = 48
        slot_margin = 10
        start_x = surface_w - (slot_w + slot_margin) * 5 - padding
        slot_y = bar_y + 50
        for i in range(5):
            rect = pygame.Rect(start_x + i * (slot_w + slot_margin), slot_y, slot_w, slot_w)
            pygame.draw.rect(self.surface, (80, 80, 80), rect)
            pygame.draw.rect(self.surface, (200, 200, 200), rect, 2)
            # Draw item icon or placeholder here later

    def mousePressEvent(self, event):
        # Adjust if your surface is not top-left aligned
        surf_rect = self.surface.get_rect()
        surf_top_left = ((self.width() - surf_rect.width) // 2, (self.height() - surf_rect.height) // 2)
        relative_x = event.x() - surf_top_left[0]
        relative_y = event.y() - surf_top_left[1]
        pos = (relative_x, relative_y)

        for name, rect in self.button_rects.items():
            if rect.collidepoint(pos):
                print(f"[CLICK] {name} button clicked")
                if name == "prev_track":
                    self.music_manager.previous_track()
                elif name == "next_track":
                    self.music_manager.next_track()
                elif name == "volume_slider":
                    self.dragging_volume = True

    def handle_mouse_up(self, event):
        self.dragging_volume = False

    def mouseReleaseEvent(self, event):
        self.handle_mouse_up(event)

    def mouseMoveEvent(self, event):
        self.handle_mouse_motion(event)

    def handle_mouse_motion(self, event):
        if self.dragging_volume:
            surf_rect = self.surface.get_rect()
            surf_top_left = ((self.width() - surf_rect.width) // 2, (self.height() - surf_rect.height) // 2)
            relative_x = event.x() - surf_top_left[0]
            relative_y = event.y() - surf_top_left[1]

            slider_rect = self.button_rects["volume_slider"]
            relative_slider_x = min(max(relative_x - slider_rect.x, 0), slider_rect.width)
            self.music_volume = relative_slider_x / slider_rect.width
            self.music_manager.set_volume(self.music_volume)

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
        leftover = self.score - self.target_score
        if leftover > 0:
            self.wallet += leftover
        self.score = 0
        self.round_number += 1
        self.target_score = self.calculate_target_score()

        if self.round_number % 3 == 0:
            if len(self.available_encounters) == 0:
                self.available_encounters = self.available_encounters_bu

            self.encounter_mode = random.choice(self.available_encounters)

            self.available_encounters.remove(self.encounter_mode)
            self.available_encounters_bu.append(self.encounter_mode)

            self.encounter_label.setText(f"Encounter: {self.encounter_mode}")
            self.match_counter_label.setText("Encounter triggers every 5 matches")
        else:
            self.encounter_mode = None
            self.encounter_label.setText("Encounter: None")
            self.match_counter_label.setText("")

        self.wallet_label.setText(f"Wallet: {self.wallet}")
        self.score_label.setText(f"Score: {self.score}")
        self.new_game()

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

    def tick(self):
        # Scroll background first
        self.bg_scroll_x = (self.bg_scroll_x + self.bg_scroll_speed_x) % self.background_tile.get_width()
        self.bg_scroll_y = (self.bg_scroll_y + self.bg_scroll_speed_y) % self.background_tile.get_height()

        # Then redraw everything
        self.update_canvas()

    def update_canvas(self):
        ACTION_BAR_HEIGHT = 100
        self.surface.fill((0, 80, 80))  # Background

        # Draw action bar background at the bottom
        pygame.draw.rect(self.surface, (30, 30, 30), (0, self.surface.get_height() - ACTION_BAR_HEIGHT,
                                                      self.surface.get_width(), ACTION_BAR_HEIGHT))


        self.surface.fill((0, 80, 80))
        tile_w, tile_h = self.background_tile.get_size()
        surface_w, surface_h = self.surface.get_size()

        start_x = -int(self.bg_scroll_x)
        start_y = -int(self.bg_scroll_y)

        for x in range(start_x, surface_w, tile_w):
            for y in range(start_y, surface_h, tile_h):
                self.surface.blit(self.background_tile, (x, y))


        # Safely get animating tiles and vacated coords
        animating_tiles = getattr(self, "animating_tiles", [])
        animating_coords = set(
            (tile["grid_x"], tile["grid_y"], tile["z"]) for tile in animating_tiles
        )
        vacated = getattr(self, "_vacated_during_animation", set())

        # Recompute top tiles, excluding animating ones
        top_tiles = {}
        for tile in self.board:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            if (gx, gy, gz) in animating_coords:
                continue
            key = (gx, gy)
            if key not in top_tiles or gz > top_tiles[key]["z"]:
                top_tiles[key] = tile

        # Phase 1: Draw shadows (skip vacated)
        for tile in self.board:
            gx, gy = tile["grid_x"], tile["grid_y"]
            if (gx, gy) in vacated:
                continue

            top = top_tiles.get((gx, gy))
            if top and top["z"] > tile["z"]:
                shadow = pygame.Surface((TILE_WIDTH, TILE_HEIGHT), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 200))
                self.surface.blit(shadow, (tile["x"], tile["y"]))

        # Phase 2: Draw static top tiles (not animating or fading)

        # Recompute top tiles, excluding animating ones
        top_tiles = {}
        fading_coords = set()
        if hasattr(self, "fading_matched_tiles"):
            fading_coords = {(t["grid_x"], t["grid_y"], t["z"]) for t in self.fading_matched_tiles}

        for tile in self.board:
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            key = (gx, gy)
            if key not in top_tiles or gz > top_tiles[key]["z"]:
                # Don't allow fading tiles to be considered topmost
                if (gx, gy, gz) not in fading_coords:
                    top_tiles[key] = tile

        fading_coords = {
            (t["grid_x"], t["grid_y"], t["z"])
            for t in getattr(self, "fading_matched_tiles", [])
        }

        for tile in sorted(top_tiles.values(), key=lambda t: t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
            if (gx, gy, gz) in animating_coords or (gx, gy, gz) in fading_coords:
                continue
            img = self.tile_images.get(tile["name"])
            if img:
                self.surface.blit(img, (tile["x"], tile["y"]))
                if tile in self.selected_tiles:
                    pygame.draw.rect(self.surface, (255, 255, 0),
                                     (tile["x"], tile["y"], TILE_WIDTH, TILE_HEIGHT), 3)

        # Phase 3: Draw newly exposed tiles that are becoming topmost
        exposed_tiles = [
            tile for tile in self.board
            if tile.get("will_become_exposed") and
               (tile["grid_x"], tile["grid_y"]) not in top_tiles
        ]
        exposed_tiles.sort(key=lambda t: t["z"])

        for tile in exposed_tiles:
            gx, gy = tile["grid_x"], tile["grid_y"]
            x, y = tile["x"], tile["y"]
            img = self.tile_images.get(tile["name"])
            if img:
                temp_img = img.copy()
                temp_img.set_alpha(tile.get("alpha", 255))
                self.surface.blit(temp_img, (x, y))
            else:
                pygame.draw.rect(self.surface, (255, 0, 0), (x, y, TILE_WIDTH, TILE_HEIGHT))
                pygame.draw.rect(self.surface, (255, 255, 255), (x, y, TILE_WIDTH, TILE_HEIGHT), 2)
                print(f"[DRAW FAIL] No image for {tile['name']} at ({gx}, {gy}, {tile['z']})")

        # Phase 4: Draw animating tiles last
        for tile in animating_tiles:
            if (tile["grid_x"], tile["grid_y"], tile["z"]) in fading_coords:
                continue
            img = self.tile_images.get(tile["name"])
            if img:
                temp_img = img.copy()
                temp_img.set_alpha(tile.get("alpha", 255))
                self.surface.blit(temp_img, (tile["x"], tile["y"]))

        # Phase 5:Handle fading matched tiles
        now = pygame.time.get_ticks()
        if hasattr(self, "fading_matched_tiles"):
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

            # Remove fully faded tiles
            for tile in done:
                if tile in self.board:
                    self.board.remove(tile)
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                if key in self.tile_positions:
                    del self.tile_positions[key]
                self.fading_matched_tiles.remove(tile)

                # ✅ Optional cleanup: remove exposure flag once animation ends
            for tile in self.board:
                if tile.get("will_become_exposed"):
                    tile.pop("will_become_exposed")

        # Phase 6: Fog of war
        if self.encounter_mode == "fog of war":
            try:
                fog_surface = pygame.Surface((TILE_WIDTH, TILE_HEIGHT), pygame.SRCALPHA)
                fog_surface.fill((0, 0, 0, 220))

                # Step 1: Build set of all visible tiles (selectable or becoming exposed)
                visible_set = set()
                if hasattr(self, "get_selectable_tiles"):
                    for tile in self.get_selectable_tiles():
                        visible_set.add((tile["grid_x"], tile["grid_y"], tile["z"]))
                for tile in self.board:
                    if tile.get("will_become_exposed"):
                        visible_set.add((tile["grid_x"], tile["grid_y"], tile["z"]))

                # Step 2: Build a dict of vertical cutoff per column (gx, gy) for visible tiles
                visibility_cutoff_y = {}  # (gx, gy) => min Y pixel to allow fog to reach
                for tile in self.board:
                    gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]
                    if (gx, gy, gz) in visible_set:
                        top_y = tile["y"]
                        visibility_cutoff_y[(gx, gy)] = min(visibility_cutoff_y.get((gx, gy), float("inf")), top_y)

                # Step 3: Draw fog for each topmost tile that is NOT visible,
                # but clamp the fog height to stop at the cutoff line for that column
                for (gx, gy), tile in top_tiles.items():
                    gz = tile["z"]
                    if (gx, gy, gz) in visible_set:
                        continue  # Tile is visible, no fog

                    fog_top = tile["y"]
                    fog_bottom = tile["y"] + TILE_HEIGHT

                    cutoff_y = visibility_cutoff_y.get((gx, gy), None)
                    if cutoff_y is not None and cutoff_y < fog_bottom:
                        # Clip fog to avoid covering playable tile below
                        fog_height = cutoff_y - fog_top
                        if fog_height <= 0:
                            continue  # Nothing to draw
                        partial_fog = pygame.Surface((TILE_WIDTH, fog_height), pygame.SRCALPHA)
                        partial_fog.fill((0, 0, 0, 220))
                        self.surface.blit(partial_fog, (tile["x"], fog_top))
                    else:
                        # No cutoff, draw full fog
                        self.surface.blit(fog_surface, (tile["x"], tile["y"]))

            except Exception as e:
                print(f"[FOG ERROR] {e}")

        # After drawing tiles
        # self.draw_score_text()
        # self.draw_combo_text()

        self.draw_action_bar()

        # Phase 7: Update and draw particles
        alive_particles = []
        for p in self.particles:
            if p.update():
                p.draw(self.surface)
                alive_particles.append(p)
        self.particles = alive_particles

        # Final blit to Qt
        raw_data = pygame.image.tostring(self.surface, "RGB")
        image = QPixmap.fromImage(
            QImage(raw_data, self.surface.get_width(), self.surface.get_height(), QImage.Format_RGB888)
        )
        self.canvas_label.setPixmap(image)

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
                            self.modify_score(50)

                            self.combo_display_text = f"Combo x{self.combo_multiplier}!"
                            self.combo_display_time = QtCore.QTime.currentTime().msecsSinceStartOfDay()
                            self.update()  # Triggers a repaint of the widget

                            if self.encounter_mode and self.match_count % 5 == 0:
                                print(f"[Encounter Triggered] Mode: {self.encounter_mode}")
                                self.trigger_encounter_effect()
                        self.selected_tiles.clear()
                    break

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

        self.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

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

        self.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

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

        self.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

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

        self.animate_wind_shift(animated_tiles, new_positions, steps=12, interval=30)

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

        self.animate_slot_tiles(animated_tiles, steps=14, interval=20)

    def apply_rotate_cw(self):
        self.animate_rotation(clockwise=True)

    def apply_rotate_ccw(self):
        self.animate_rotation(clockwise=False)

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

        self.animate_parallax_tiles(animated_tiles, steps=10, interval=30)

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

        self.animate_crush_tiles(animated_tiles, steps=12, interval=25)

    def animate_crush_tiles(self, tiles, steps=12, interval=25):
        self.animation_step = 0
        self.animation_steps = steps
        self.animating_tiles = tiles

        def animate_step():
            if self.animation_step >= self.animation_steps:
                for tile in self.animating_tiles:
                    tile["x"] = tile["target_x"]
                    tile["y"] = tile["target_y"]
                    tile["grid_x"] = tile["target_grid_x"]
                    tile["grid_y"] = tile["target_grid_y"]
                    tile["z"] = tile["target_z"]
                    tile["alpha"] = 255
                    tile.pop("fading", None)


                self.rebuild_tile_positions()
                self.animating_tiles = []
                self.update_canvas()
                return

            progress = (self.animation_step + 1) / self.animation_steps
            for tile in self.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                if tile.get("fading"):
                    # Fade out then back in
                    if progress <= 0.5:
                        tile["alpha"] = int(255 * (1 - 2 * progress))  # fade out
                    else:
                        tile["alpha"] = int(255 * (2 * progress - 1))  # fade in

            self.animation_step += 1
            self.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_parallax_tiles(self, tiles, steps=10, interval=30):
        self.animation_step = 0
        self.animation_steps = steps
        self.animating_tiles = tiles

        def animate_step():
            if self.animation_step >= self.animation_steps:
                for tile in self.animating_tiles:
                    tile["x"] = tile["target_x"]
                    tile["alpha"] = 255
                    tile.pop("fading", None)
                self.rebuild_tile_positions()
                self.animating_tiles = []
                return

            progress = (self.animation_step + 1) / self.animation_steps
            for tile in self.animating_tiles:
                sx = tile.get("start_x", tile["x"])
                tx = tile.get("target_x", tile["x"])
                tile["x"] = sx + (tx - sx) * progress

                if tile.get("fading"):
                    # Fade in from 80 to 255
                    tile["alpha"] = int(80 + (255 - 80) * progress)

            self.animation_step += 1
            self.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_slot_tiles(self, tiles, steps=14, interval=20):
        self.animation_step = 0
        self.animation_steps = steps
        self.animating_tiles = tiles

        def animate_step():
            if self.animation_step >= self.animation_steps:
                for tile in self.animating_tiles:
                    tile["y"] = tile["target_y"]
                    tile["grid_y"] = tile["target_grid_y"]
                    tile["z"] = tile["target_z"]
                    tile["alpha"] = 255
                    tile.pop("flicker", None)

                self.rebuild_tile_positions()
                self.animating_tiles = []
                self.update_canvas()
                return

            progress = (self.animation_step + 1) / self.animation_steps
            for tile in self.animating_tiles:
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                # Add slot machine "flash" effect
                if tile.get("flicker"):
                    flicker_phase = (self.animation_step % 4) / 4
                    tile["alpha"] = int(180 + 75 * (0.5 + 0.5 * math.sin(2 * math.pi * flicker_phase)))

            self.animation_step += 1
            self.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_wind_shift(self, tiles, new_positions, steps=12, interval=30):
        if not hasattr(self, "particles"):
            self.particles = []

        self.animation_step = 0
        self.animation_steps = steps
        self.animating_tiles = tiles

        # Identify newly exposed tiles (tiles that are no longer covered after movement)
        pre_animation_top = set(
            (gx, gy) for (gx, gy, gz) in self.tile_positions
            if not any((gx, gy, gz + 1) in self.tile_positions for gz in range(10))
        )

        # We simulate the post-shift tile positions
        post_animation_top = set()
        for tile in tiles:
            gx, gy, gz = tile["target_grid_x"], tile["target_grid_y"], tile["target_z"]
            post_animation_top.add((gx, gy))

        # These are the tiles that will become visible after shift
        newly_exposed_coords = post_animation_top - pre_animation_top

        # Mark affected tiles before animation
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"])
            tile["will_become_exposed"] = key in newly_exposed_coords
            if tile.get("will_become_exposed"):
                print(f"[EXPOSED] {tile['name']} at ({tile['grid_x']}, {tile['grid_y']}, {tile['z']})")

        # Track all source coordinates being vacated
        vacated_coords = set((tile["grid_x"], tile["grid_y"]) for tile in tiles)
        self._vacated_during_animation = vacated_coords  # Store for update_canvas()

        def animate_step():
            if self.animation_step >= self.animation_steps:
                for tile in self.animating_tiles:
                    tile["x"] = tile["target_x"]
                    tile["y"] = tile["target_y"]
                    tile["grid_x"] = tile["target_grid_x"]
                    tile["grid_y"] = tile["target_grid_y"]
                    tile["z"] = tile["target_z"]
                    tile["alpha"] = 255
                    tile.pop("fading", None)
                    key = (tile["grid_x"], tile["grid_y"], tile["z"])
                    new_positions[key] = tile
                    tile.pop("will_become_exposed", None)

                self.board = list(new_positions.values())
                self.tile_positions = new_positions
                self.animating_tiles = []
                self.update_canvas()

                if hasattr(self, "_vacated_during_animation"):
                    del self._vacated_during_animation

                return

            progress = (self.animation_step + 1) / self.animation_steps
            for tile in self.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                if tile.get("fading"):
                    tile["alpha"] = int(200 + 55 * math.sin(progress * math.pi))  # shimmer

                # Particle burst during movement
                if self.animation_step % 2 == 0:
                    px = tile["x"] + TILE_WIDTH // 2 + random.randint(-4, 4)
                    py = tile["y"] + TILE_HEIGHT // 2 + random.randint(-4, 4)
                    self.particles.append(WindParticle(px, py, direction=self.current_wind_direction))

            self.animation_step += 1
            self.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_rotation(self, clockwise=True, steps=12, interval=30):
        if not self.board:
            return

        new_board = []
        new_positions = {}
        animating_tiles = []

        # Group tiles into 3x3 blocks by top-left corner
        blocks = {}
        for tile in self.board:
            gx, gy = tile["grid_x"], tile["grid_y"]
            block_x = (gx // 3) * 3
            block_y = (gy // 3) * 3
            blocks.setdefault((block_x, block_y), []).append(tile)

        for (bx, by), tiles in blocks.items():
            # Build 2D stacks at each (x, y)
            stacks = {}
            for tile in tiles:
                key = (tile["grid_x"], tile["grid_y"])
                stacks.setdefault(key, []).append(tile)

            # Sort each stack by z
            for stack in stacks.values():
                stack.sort(key=lambda t: t["z"])

            # Create 3x3 grid of stacks
            grid = [[None for _ in range(3)] for _ in range(3)]
            for (gx, gy), stack in stacks.items():
                local_x = gx - bx
                local_y = gy - by
                if 0 <= local_x < 3 and 0 <= local_y < 3:
                    grid[local_y][local_x] = stack

            # Rotate and set new positions
            for y in range(3):
                for x in range(3):
                    stack = grid[y][x]
                    if not stack:
                        continue

                    if clockwise:
                        new_x, new_y = 2 - y, x
                    else:
                        new_x, new_y = y, 2 - x

                    target_gx = bx + new_x
                    target_gy = by + new_y

                    for dz, tile in enumerate(stack):
                        new_gz = tile["z"]  # z remains the same
                        tile["start_x"] = tile["x"]
                        tile["start_y"] = tile["y"]
                        tile["target_grid_x"] = target_gx
                        tile["target_grid_y"] = target_gy
                        tile["target_z"] = new_gz
                        tile["target_x"] = 80 + target_gx * TILE_WIDTH
                        tile["target_y"] = 60 + target_gy * TILE_HEIGHT - new_gz * TILE_DEPTH

                        animating_tiles.append(tile)

        # Start animation
        self.animation_step = 0
        self.animation_steps = steps
        self.animating_tiles = animating_tiles

        def animate_step():
            if self.animation_step >= self.animation_steps:
                final_positions = {}
                for tile in self.animating_tiles:
                    tile["x"] = tile["target_x"]
                    tile["y"] = tile["target_y"]
                    tile["grid_x"] = tile["target_grid_x"]
                    tile["grid_y"] = tile["target_grid_y"]
                    tile["z"] = tile["target_z"]
                    tile["alpha"] = 255
                    for k in ["start_x", "start_y", "target_x", "target_y", "target_grid_x", "target_grid_y",
                              "target_z"]:
                        tile.pop(k, None)

                    key = (tile["grid_x"], tile["grid_y"], tile["z"])
                    final_positions[key] = tile
                    new_board.append(tile)

                self.animating_tiles = []
                self.board = new_board
                self.tile_positions = final_positions
                self.normalize_stacks()
                self.update_canvas()
                return

            progress = (self.animation_step + 1) / self.animation_steps
            for tile in self.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

            self.animation_step += 1
            self.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

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
