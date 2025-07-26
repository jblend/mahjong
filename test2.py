import sys
import os
import random
import pygame
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage


TILES_ROOT = "./assets/tiles/classic"
TILE_WIDTH, TILE_HEIGHT = 64, 96
PAIR_COUNT = 2
STACK_HEIGHT = 4
NUM_ROWS = 6

class MahjongGame(QWidget):
    def __init__(self):
        super().__init__()
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
        self.target_score = self.calculate_target_score()
        self.encounter_mode = None
        self.available_encounters = [
            "west_wind", "east_wind", "south_wind", "north_wind",
            "crush", "parallax", "slot_machine", "rotate_cw", "rotate_ccw"
        ]

        # ✅ Initialize pygame before loading tiles
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.HIDDEN)  # Allow image conversion
        self.surface = pygame.Surface((900, 900))

        # ✅ Now safe to load tile images
        self.tile_images = {}
        self.load_tileset_images()

        # GUI setup
        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_canvas)
        self.timer.start(30)

        self.new_game()

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
        debug_score.clicked.connect(lambda: self.modify_score(100))
        btns.addWidget(debug_score)

        end_round = QPushButton("End Round")
        end_round.clicked.connect(self.start_new_round)
        btns.addWidget(end_round)

        layout.addLayout(btns)
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

    def modify_score(self, points):
        self.score += points
        self.score_label.setText(f"Score: {self.score}")

    def start_new_round(self):
        leftover = self.score - self.target_score
        if leftover > 0:
            self.wallet += leftover
        self.score = 0
        self.round_number += 1
        self.target_score = self.calculate_target_score()

        if self.round_number % 3 == 0:
            self.encounter_mode = random.choice(self.available_encounters)
            self.encounter_label.setText(f"Encounter: {self.encounter_mode}")
            self.match_counter_label.setText("Encounter Triggering Every 5 Matches")
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

    def update_canvas(self):
        self.surface.fill((0, 80, 80))
        for tile in sorted(self.board, key=lambda t: t["z"]):
            img = self.tile_images.get(tile["name"])
            if img:
                self.surface.blit(img, (tile["x"], tile["y"]))

        raw_data = pygame.image.tostring(self.surface, "RGB")
        image = QPixmap.fromImage(
            QImage(raw_data, self.surface.get_width(), self.surface.get_height(), QImage.Format_RGB888)
        )

        if not hasattr(self, "canvas_label"):
            self.canvas_label = QLabel()
            self.layout().addWidget(self.canvas_label)
        self.canvas_label.setPixmap(image)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = MahjongGame()
    game.show()
    sys.exit(app.exec_())
