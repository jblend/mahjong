import os
import json
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import copy
import threading

# Paths
TILES_ROOT = os.path.join("assets", "tiles")
BOARD_WIDTH, BOARD_HEIGHT = 1024, 768
TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
NUM_ROWS = 6
STACK_HEIGHT = 4
PAIR_COUNT = 8  # Each unique tile appears this many times

class MahjongGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Mahjong")

        self.canvas = tk.Canvas(root, width=BOARD_WIDTH, height=BOARD_HEIGHT, bg="dark green")
        self.canvas.pack()

        button_bar = tk.Frame(root)
        button_bar.pack(pady=4)

        ttk.Button(button_bar, text="New Game", command=self.new_game).pack(side="left")
        ttk.Button(button_bar, text="Undo", command=self.undo).pack(side="left")
        ttk.Button(button_bar, text="Save", command=self.save_game).pack(side="left")
        ttk.Button(button_bar, text="Load", command=self.load_game).pack(side="left")

        ttk.Label(button_bar, text="Tileset:").pack(side="left", padx=(12, 2))
        self.tileset_var = tk.StringVar()
        self.tileset_combo = ttk.Combobox(button_bar, textvariable=self.tileset_var, state="readonly", values=self.available_tilesets())
        self.tileset_combo.current(0)
        self.tileset_combo.pack(side="left")
        self.available_encounters = [
            "west_wind",
            "east_wind",
            "south_wind",
            "north_wind",
            "crush",
            "parallax",
            "slot_machine",
            "rotate_cw",
            "rotate_ccw"
        ]

        self.tile_images = {}
        self.board = []
        self.history = []
        self.selected_tiles = []
        self.score = 0


        self.total_matches_made = 0
        self.round_number = 1

        self.target_score = 200
        self.wallet = 0

        self.tile_positions = {}
        self.match_counts = {}
        self.matched_pairs = {}  # Track pairs scored more than once

        self.score_label = tk.Label(root, text="Score: 0", font=("Arial", 12), bg="dark green", fg="white")
        self.score_label.place(x=10, y=10)

        self.match_label = tk.Label(root, text="Matches: 0", font=("Arial", 12), bg="dark green", fg="white")
        self.match_label.place(x=10, y=30)

        # self.encounter_mode = "west_wind"  # or None

        if self.round_number % 3 == 0:
            self.encounter_mode = random.choice(self.available_encounters)
        else:
            self.encounter_mode = None

        self.encounter_trigger_interval = 5  # how often encounters trigger (in matches)
        self.encounter_match_counter = 0  # reset every time an encounter is triggered

        self.match_counter_label = tk.Label(self.root, text="", font=("Arial", 10))
        self.match_counter_label.pack_forget()  # hidden by default

        self.encounter_type_label = tk.Label(self.root, text="Encounter: None", font=("Arial", 10), fg="red")
        self.encounter_type_label.pack()

        self.encounter_occurs_label = tk.Label(self.root, text="Encounter Occurs in", font=("Arial", 10), fg="red")
        self.encounter_occurs_label.pack()

        self.root.update_idletasks()


        self.root.bind("<F12>", lambda e: self.debug_trigger_encounter())
        self.root.bind("<F1>", self.debug_add_score)
        self.root.bind("<F2>", self.debug_end_round)


        print(f"\U0001F4C2 Working directory: {os.getcwd()}")
        self.new_game()

    @staticmethod
    def available_tilesets():
        return sorted(d for d in os.listdir(TILES_ROOT) if os.path.isdir(os.path.join(TILES_ROOT, d)))

    def load_tileset_images(self, set_name):
        folder = os.path.join(TILES_ROOT, set_name)
        self.tile_images.clear()

        abs_folder = os.path.abspath(folder)
        print(f"\n\U0001F4E6 Loading tiles from: {abs_folder}")

        if not os.path.exists(abs_folder):
            print("❌ Folder does not exist:", abs_folder)
            return

        files = os.listdir(abs_folder)
        print(f"🔲 Found {len(files)} files: {files}")

        for fname in files:
            if fname.lower().endswith(".png"):
                key = os.path.splitext(fname)[0]
                path = os.path.abspath(os.path.join(folder, fname))
                try:
                    img = tk.PhotoImage(file=path)
                    self.tile_images[key] = img
                    print(f"  ✓ Loaded: {key} from {path}")
                except Exception as e:
                    print(f"  ✗ Failed to load {path}: {e}")

        print(f"🔹 Total tiles successfully loaded: {len(self.tile_images)}")

    def push_history(self):
        self.history.append({
            "board": copy.deepcopy(self.board),
            "tile_positions": copy.deepcopy(self.tile_positions),
            "score": self.score,
            "match_counts": copy.deepcopy(self.match_counts),
            "total_matches_made": self.total_matches_made,
        })

    def new_game(self):
        self.load_tileset_images(self.tileset_var.get())
        self.history.clear()
        self.score = 0
        self.score_label.config(text="Score: 0")
        self.selected_tiles.clear()
        self.tile_positions.clear()
        self.total_tiles_at_start = len(self.board)

        rounds_until_encounter = 3 - (self.round_number % 3)
        if rounds_until_encounter == 3:
            rounds_until_encounter = 0  # Encounter happens *this* round

        self.encounter_occurs_label.config(text=f"Next encounter in {rounds_until_encounter} round(s)")

        available_names = list(self.tile_images.keys())
        if not available_names:
            print("❌ No tiles available for matching.")
            return

        chosen_names = random.sample(available_names, min(len(available_names), 144 // PAIR_COUNT))
        name_pool = []
        for name in chosen_names:
            name_pool.extend([name] * PAIR_COUNT)

        random.shuffle(name_pool)

        self.board = []
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

        for i, (x, y, z) in enumerate(layout):
            if i >= len(name_pool):
                break

            # Avoid placing same tile name directly next to same row unless necessary
            for attempt in range(10):
                name = name_pool[i]
                left = (x - 1, y, z)
                right = (x + 1, y, z)
                conflict = False
                for neighbor in (left, right):
                    neighbor_tile = self.tile_positions.get(neighbor)
                    if neighbor_tile and neighbor_tile["name"] == name:
                        conflict = True
                        break

                if not conflict:
                    break
                else:
                    # Try to find a different tile to swap with
                    for j in range(i + 1, len(name_pool)):
                        swap_name = name_pool[j]
                        # Check if the swap avoids adjacent conflict
                        adjacent_ok = True
                        for neighbor in (left, right):
                            neighbor_tile = self.tile_positions.get(neighbor)
                            if neighbor_tile and neighbor_tile["name"] == swap_name:
                                adjacent_ok = False
                                break
                        if adjacent_ok:
                            name_pool[i], name_pool[j] = name_pool[j], name_pool[i]
                            break

            abs_x = margin_x + x * TILE_WIDTH
            abs_y = margin_y + y * TILE_HEIGHT - z * TILE_DEPTH
            tile = {"name": name_pool[i], "x": abs_x, "y": abs_y, "z": z, "grid_x": x, "grid_y": y}
            self.board.append(tile)
            self.tile_positions[(x, y, z)] = tile

        # After layout is created
        self.min_grid_x = min(t["grid_x"] for t in self.board)
        self.max_grid_x = max(t["grid_x"] for t in self.board)
        self.min_grid_y = min(t["grid_y"] for t in self.board)
        self.max_grid_y = max(t["grid_y"] for t in self.board)
        self.center_x = (self.min_grid_x + self.max_grid_x) // 2

        self.draw_board()

    def start_new_round(self):
        # Score handling
        leftover = self.score - self.target_score
        if leftover > 0:
            self.wallet += leftover
        self.score = 0
        self.round_number += 1

        # Set new encounter every 3 rounds
        if self.round_number % 3 == 0:
            self.encounter_mode = random.choice(self.available_encounters)
            print(f"the encounter is now {self.encounter_mode}")
            self.encounter_type_label.config(text=f"Encounter: {self.encounter_mode}")
            self.encounter_type_label.pack()
            self.match_counter_label.pack()  # show the label
            self.update_match_counter_label()
        else:
            self.encounter_mode = None
            self.match_counter_label.pack_forget()  # hide the label

        # Update GUI label to show current encounter
        self.encounter_type_label.config(text=f"Encounter: {self.encounter_mode}")

        # Recalculate the next target score
        self.target_score = self.calculate_target_score()

        # Update UI labels
        self.score_label.config(text=f"Score: {self.score}")
        # self.wallet_label.config(text=f"Wallet: {self.wallet}")
        self.encounter_type_label.config(text=f"Encounter: {self.encounter_mode}")

        # self.encounter_countdown_label.config(
        #     text=f"Next encounter in {3 - (self.round_number % 3)} rounds"
        # )

        # Start new game
        self.new_game()

    def undo(self):
        if self.history:
            state = self.history.pop()
            self.board = state["board"]
            self.tile_positions = state["tile_positions"]
            self.score = state["score"]
            self.match_counts = state["match_counts"]
            self.total_matches_made = state["total_matches_made"]
            self.score_label.config(text=f"Score: {self.score}")
            self.draw_board()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")


    def save_game(self):
        if not self.board:
            messagebox.showwarning("Save", "No game in progress.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", initialdir="saves", title="Save game as…")
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                json.dump({
                    "tileset": self.tileset_var.get(),
                    "board": self.board,
                    "history": self.history,
                    "score": self.score
                }, fh)
            messagebox.showinfo("Save", "Game saved successfully!")

    def load_game(self):
        path = filedialog.askopenfilename(initialdir="saves", filetypes=[("JSON saves", "*.json")], title="Load saved game")
        if path:
            with open(path, "r") as fh:
                data = json.load(fh)
            self.tileset_var.set(data["tileset"])
            self.load_tileset_images(data["tileset"])
            self.board = data["board"]
            self.history = data.get("history", [])
            self.score = data.get("score", 0)
            self.score_label.config(text=f"Score: {self.score}")
            self.tile_positions = {(t["grid_x"], t["grid_y"], t["z"]): t for t in self.board}
            self.draw_board()

    def on_tile_click(self, event):
        self.canvas.delete("highlight")
        for tile in sorted(self.board, key=lambda t: -t["z"]):
            x, y = tile["x"], tile["y"]
            if x <= event.x <= x + TILE_WIDTH and y <= event.y <= y + TILE_HEIGHT:
                if self.is_tile_selectable(tile):
                    self.select_tile(tile)
                return

    def is_tile_selectable(self, tile):
        x, y, z = tile.get("grid_x"), tile.get("grid_y"), tile.get("z")
        if (x, y, z + 1) in self.tile_positions:
            return False
        left = (x - 1, y, z) in self.tile_positions
        right = (x + 1, y, z) in self.tile_positions
        return not (left and right)

    def calculate_target_score(self):
        """
        Calculates the required target score for the current round.
        The target increases with each round and scales with the number of pairs.
        """
        base_score_per_pair = 15  # Average match reward baseline
        pair_count = len(self.board) // 2  # Number of pairs on the board
        difficulty_multiplier = 1 + (self.round_number - 1) * 0.2  # Increases 20% each round

        target = int(base_score_per_pair * pair_count * difficulty_multiplier)
        print(f"[DEBUG] Target score for round {self.round_number}: {target}")
        return target

    def select_tile(self, tile):
        if tile in self.selected_tiles:
            return

        if len(self.selected_tiles) >= 2:
            self.selected_tiles.clear()
            self.canvas.delete("highlight")

        self.selected_tiles.append(tile)
        self.highlight_tile(tile)

        if len(self.selected_tiles) == 2:
            tile1, tile2 = self.selected_tiles
            if tile1["name"] == tile2["name"] and tile1 != tile2:
                self.push_history()

                self.board.remove(tile1)
                self.board.remove(tile2)
                self.tile_positions.pop((tile1["grid_x"], tile1["grid_y"], tile1["z"]))
                self.tile_positions.pop((tile2["grid_x"], tile2["grid_y"], tile2["z"]))

                # Scoring: increase score for matching same pair again
                pair_name = tile1["name"]
                self.matched_pairs[pair_name] = self.matched_pairs.get(pair_name, 0) + 1
                multiplier = self.matched_pairs[pair_name]
                points = max(10, 10 * multiplier)

                # Count how many times this tile has been matched

                match_info = f"Matched {pair_name} (x{self.matched_pairs[pair_name]}) for {points} pts"
                info_label = tk.Label(self.root,
                                      text=match_info,
                                      font=("Arial", 20),
                                      fg="white",
                                      bg="green"
                                      )
                info_label.place(relx=0.5, y=20, anchor="n")

                # Show for 4 seconds
                self.root.after(4000, info_label.destroy)

                self.total_matches_made += 1

                if self.encounter_mode:
                    self.encounter_match_counter += 1
                    remaining = self.encounter_trigger_interval - self.encounter_match_counter
                    self.update_match_counter_label()

                    if self.encounter_match_counter >= self.encounter_trigger_interval:
                        self.encounter_match_counter = 0
                        self.trigger_encounter_effect()



                self.score += points
                self.score_label.config(text=f"Score: {self.score}")

                self.canvas.after(100, lambda: self.flash_tiles(tile1, tile2))
                self.root.after(400, self.draw_board)

            self.selected_tiles.clear()

        # Check end-of-round conditions if no tiles selected (i.e., after clear)
        if not self.selected_tiles:
            tiles_removed = self.total_tiles_at_start - len(self.board)
            calculated_score = tiles_removed * 100
            if calculated_score > self.score:
                self.score = calculated_score
                self.score_label.config(text=f"Score: {self.score}")

            if not self.board:
                messagebox.showinfo("You win!", f"Congratulations! Final score: {self.score}")
            elif self.count_possible_matches() == 0:
                if self.score >= self.target_score:
                    surplus = self.score - self.target_score
                    self.wallet += surplus
                    self.round_number += 1
                    self.score = 0
                    self.target_score = int(self.target_score * 1.5)
                    self.show_store_screen()
                else:
                    messagebox.showerror("Game Over", "No more possible moves and target score not reached!")

    def flash_tiles(self, tile1, tile2):
        for _ in range(3):
            self.canvas.delete("highlight")
            self.root.update()
            self.root.after(100)
            self.highlight_tile(tile1, "yellow")
            self.highlight_tile(tile2, "yellow")
            self.root.update()
            self.root.after(100)
        self.canvas.delete("highlight")

    def highlight_tile(self, tile, color="red"):
        x1 = tile["x"]
        y1 = tile["y"]
        x2 = x1 + TILE_WIDTH
        y2 = y1 + TILE_HEIGHT
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3, tags="highlight")

    def count_possible_matches(self):
        open_tiles = [t for t in self.board if self.is_tile_selectable(t)]
        name_count = {}
        for t in open_tiles:
            name_count[t["name"]] = name_count.get(t["name"], 0) + 1
        return sum(v // 2 for v in name_count.values())

    def update_match_counter_label(self):
        if self.encounter_mode:
            remaining = self.encounter_trigger_interval - self.encounter_match_counter
            if remaining == 0:
                remaining = self.encounter_trigger_interval
            self.match_counter_label.config(text=f"Encounter Triggering in {remaining} Matches")

    def draw_board(self):
        self.canvas.delete("all")
        for tile in sorted(self.board, key=lambda t: t["z"]):
            x, y, z = tile["x"], tile["y"], tile["z"]
            grid_key_above = (tile["grid_x"], tile["grid_y"], z + 1)
            if grid_key_above in self.tile_positions:
                self.canvas.create_rectangle(x, y, x + TILE_WIDTH, y + TILE_HEIGHT, fill="black")
            else:
                img = self.tile_images[tile["name"]]
                tag = f"tile_{x}_{y}_{z}"
                self.canvas.create_image(x, y, image=img, anchor="nw", tags=tag)
                thickness = max(1, z + 1)
                self.canvas.create_line(x, y + TILE_HEIGHT, x + TILE_WIDTH, y + TILE_HEIGHT, fill="black", width=thickness)
                self.canvas.tag_bind(tag, "<Button-1>", self.on_tile_click)
        self.root.images = list(self.tile_images.values())
        match_count = self.count_possible_matches()
        self.match_label.config(text=f"Matches: {match_count}")

    def trigger_encounter_effect(self):
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

    def debug_trigger_encounter(self):
        if self.encounter_mode:
            self.trigger_encounter_effect()

    def show_store_screen(self):
        store_win = tk.Toplevel(self.root)
        store_win.title("Store")
        store_win.geometry("400x300")

        tk.Label(store_win, text=f"Wallet: {self.wallet}").pack(pady=10)
        tk.Label(store_win, text=f"Next Target: {self.target_score}").pack(pady=5)

        def buy_hint():
            if self.wallet >= 50:
                self.wallet -= 50
                # Add hint to powerups
                messagebox.showinfo("Purchased", "Hint powerup added!")
                store_win.destroy()
            else:
                messagebox.showwarning("Insufficient Funds", "Not enough points.")

        tk.Button(store_win, text="Buy Hint (50 pts)", command=buy_hint).pack(pady=10)
        tk.Button(store_win, text="Start Next Round", command=lambda: [store_win.destroy(), self.new_game()]).pack(
            pady=20)

    def apply_west_wind_shift(self):
        new_positions = {}
        updated_board = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            # Tile is on the bottom or covered — don't move it
            if gz == 0 or (gx, gy, gz + 1) in occupied:
                key = (gx, gy, gz)

            else:
                new_gx = gx - 1
                if (
                        new_gx < self.min_grid_x or  # Would go past left wall
                        (new_gx, gy, gz) in occupied  # Blocked at same Z level
                ):
                    # Can't shift left, so stay put
                    key = (gx, gy, gz)
                else:
                    # Tile is free to shift left and fall
                    new_gz = 0
                    while (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                        new_gz += 1

                    tile["grid_x"], tile["grid_y"], tile["z"] = new_gx, gy, new_gz
                    tile["x"] = 80 + new_gx * TILE_WIDTH
                    tile["y"] = 60 + gy * TILE_HEIGHT - new_gz * TILE_DEPTH
                    key = (new_gx, gy, new_gz)

            new_positions[key] = tile
            updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def apply_east_wind_shift(self):
        new_positions = {}
        updated_board = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            # Only move tiles that are not on the bottom level and not covered
            if gz == 0 or (gx, gy, gz + 1) in occupied:
                key = (gx, gy, gz)

            else:
                new_gx = gx + 1
                if (
                        new_gx > self.max_grid_x or  # Prevent moving past rightmost wall
                        (new_gx, gy, gz) in occupied  # Prevent stacking at same Z
                ):
                    key = (gx, gy, gz)  # Blocked, so don't move
                else:
                    # Tile is free to shift right and fall
                    new_gz = 0
                    while (new_gx, gy, new_gz) in new_positions or (new_gx, gy, new_gz) in occupied:
                        new_gz += 1

                    tile["grid_x"], tile["grid_y"], tile["z"] = new_gx, gy, new_gz
                    tile["x"] = 80 + new_gx * TILE_WIDTH
                    tile["y"] = 60 + gy * TILE_HEIGHT - new_gz * TILE_DEPTH
                    key = (new_gx, gy, new_gz)

            new_positions[key] = tile
            updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def apply_north_wind_shift(self):
        new_positions = {}
        updated_board = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx, gy, gz + 1) in occupied:
                key = (gx, gy, gz)

            else:
                new_gy = gy - 1
                if (
                        new_gy < self.min_grid_y or
                        (gx, new_gy, gz) in occupied
                ):
                    key = (gx, gy, gz)
                else:
                    new_gz = 0
                    while (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                        new_gz += 1

                    tile["grid_x"], tile["grid_y"], tile["z"] = gx, new_gy, new_gz
                    tile["x"] = 80 + gx * TILE_WIDTH
                    tile["y"] = 60 + new_gy * TILE_HEIGHT - new_gz * TILE_DEPTH
                    key = (gx, new_gy, new_gz)

            new_positions[key] = tile
            updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def apply_south_wind_shift(self):
        new_positions = {}
        updated_board = []

        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for tile in sorted(self.board, key=lambda t: -t["z"]):
            gx, gy, gz = tile["grid_x"], tile["grid_y"], tile["z"]

            if gz == 0 or (gx, gy, gz + 1) in occupied:
                key = (gx, gy, gz)

            else:
                new_gy = gy + 1
                if (
                        new_gy > self.max_grid_y or
                        (gx, new_gy, gz) in occupied
                ):
                    key = (gx, gy, gz)
                else:
                    new_gz = 0
                    while (gx, new_gy, new_gz) in new_positions or (gx, new_gy, new_gz) in occupied:
                        new_gz += 1

                    tile["grid_x"], tile["grid_y"], tile["z"] = gx, new_gy, new_gz
                    tile["x"] = 80 + gx * TILE_WIDTH
                    tile["y"] = 60 + new_gy * TILE_HEIGHT - new_gz * TILE_DEPTH
                    key = (gx, new_gy, new_gz)

            new_positions[key] = tile
            updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def apply_slot_machine_shift(self):
        new_positions = {}
        updated_board = []

        # Group tiles by (grid_x, grid_y)
        stack_map = {}
        for tile in self.board:
            key = (tile["grid_x"], tile["grid_y"])
            stack_map.setdefault(key, []).append(tile)

        # Sort each stack so lowest z comes first
        for stack in stack_map.values():
            stack.sort(key=lambda t: t["z"])

        # Group stacks by column (grid_x)
        column_map = {}
        for (gx, gy), stack in stack_map.items():
            column_map.setdefault(gx, []).append((gy, stack))

        # Determine occupied grid spaces
        occupied = set(self.tile_positions.keys())
        self.tile_positions.clear()

        for gx, gy_stacks in column_map.items():
            # Sort by Y so we maintain order
            gy_stacks.sort(key=lambda s: s[0])

            if gx % 2 == 0:
                # Even column -> shift DOWN
                gy_stacks = gy_stacks[-1:] + gy_stacks[:-1]
            else:
                # Odd column -> shift UP
                gy_stacks = gy_stacks[1:] + gy_stacks[:1]

            # Reassign Y positions and determine new Z-levels
            for new_gy, (_, stack) in zip(range(len(gy_stacks)), gy_stacks):
                for i, tile in enumerate(stack):
                    # Reassign position
                    tile["grid_y"] = new_gy
                    tile["z"] = i  # re-stack from 0 up
                    tile["x"] = 80 + tile["grid_x"] * TILE_WIDTH
                    tile["y"] = 60 + new_gy * TILE_HEIGHT - tile["z"] * TILE_DEPTH
                    key = (tile["grid_x"], new_gy, tile["z"])
                    new_positions[key] = tile
                    updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def apply_rotate_cw(self):
        self.rotate_local_blocks(True)

    def apply_rotate_ccw(self):
        self.rotate_local_blocks(False)

    def apply_parallax_shift(self):
        if not self.board:
            return

        min_x = min(tile["grid_x"] for tile in self.board)
        max_x = max(tile["grid_x"] for tile in self.board)
        center_x = (min_x + max_x) / 2

        # Map tiles by original column
        columns = {}
        for tile in self.board:
            gx = tile["grid_x"]
            columns.setdefault(gx, []).append(tile)

        used_columns = set()
        new_board = []
        new_positions = {}

        def find_nearest_unoccupied_column(target, direction):
            """
            If a tile hits the edge, find the nearest unused column closer to the center.
            """
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
                    return target  # fallback to original if nothing free

        for gx in sorted(columns.keys()):
            stack = columns[gx]
            if gx < center_x:
                target_gx = gx - 1
                if target_gx < min_x or target_gx in used_columns:
                    # Snap to nearest column left of center not yet used
                    target_gx = find_nearest_unoccupied_column(int(center_x), 1)
            elif gx > center_x:
                target_gx = gx + 1
                if target_gx > max_x or target_gx in used_columns:
                    # Snap to nearest column right of center not yet used
                    target_gx = find_nearest_unoccupied_column(int(center_x), -1)
            else:
                # Center column stays
                target_gx = gx

            used_columns.add(target_gx)

            for tile in stack:
                tile["grid_x"] = target_gx
                tile["x"] = 80 + target_gx * TILE_WIDTH
                key = (tile["grid_x"], tile["grid_y"], tile["z"])
                new_positions[key] = tile
                new_board.append(tile)

        self.board = new_board
        self.tile_positions = new_positions
        self.draw_board()

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
        self.draw_board()

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
        print("⚙️ Applying Crush Shift (limited to 4-tile stacks)")

        from collections import defaultdict
        rows = defaultdict(list)
        for tile in self.board:
            rows[tile["grid_y"]].append(tile)

        new_positions = {}
        updated_board = []

        max_stack_height = 4  # Limit for stacking

        for gy, row_tiles in rows.items():
            left = [t for t in row_tiles if t["grid_x"] < self.center_x]
            right = [t for t in row_tiles if t["grid_x"] > self.center_x]
            stationary = [t for t in row_tiles if t["grid_x"] == self.center_x]

            left_sorted = sorted(left, key=lambda t: -t["grid_x"])  # Closest to center first
            right_sorted = sorted(right, key=lambda t: t["grid_x"])  # Closest to center first

            # Add center tiles
            for tile in stationary:
                key = (tile["grid_x"], gy, tile["z"])
                new_positions[key] = tile
                updated_board.append(tile)

            # Helper to find next available z level in a column, returns None if full or duplicate
            def find_stack_spot(gx, name):
                stack = [pos for pos in new_positions if pos[0] == gx and pos[1] == gy]
                stack.sort(key=lambda pos: pos[2])  # Sort by z
                if any(new_positions[pos]["name"] == name for pos in stack):
                    return None
                return len(stack) if len(stack) < max_stack_height else None

            # Process left-moving tiles
            for tile in left_sorted:
                new_x = tile["grid_x"] + 1
                z_spot = find_stack_spot(new_x, tile["name"])
                if z_spot is not None:
                    tile["grid_x"], tile["grid_y"], tile["z"] = new_x, gy, z_spot
                    tile["x"] = 80 + new_x * TILE_WIDTH
                    tile["y"] = 60 + gy * TILE_HEIGHT - z_spot * TILE_DEPTH
                # else tile stays in place
                new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile
                updated_board.append(tile)

            # Process right-moving tiles
            for tile in right_sorted:
                new_x = tile["grid_x"] - 1
                z_spot = find_stack_spot(new_x, tile["name"])
                if z_spot is not None:
                    tile["grid_x"], tile["grid_y"], tile["z"] = new_x, gy, z_spot
                    tile["x"] = 80 + new_x * TILE_WIDTH
                    tile["y"] = 60 + gy * TILE_HEIGHT - z_spot * TILE_DEPTH
                # else tile stays in place
                new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile
                updated_board.append(tile)

        self.board = updated_board
        self.tile_positions = new_positions
        self.draw_board()

    def debug_end_round(self, event=None):
        print("[DEBUG] Ending current round.")
        self.start_new_round()

    def debug_add_score(self, event=None):
        self.score += 100
        self.score_label.config(text=f"Score: {self.score}")
        print("[DEBUG] Score increased by 100.")




if __name__ == "__main__":
    root = tk.Tk()
    MahjongGame(root)
    root.mainloop()
