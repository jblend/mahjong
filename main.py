import os
import json
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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

        self.tile_images = {}
        self.board = []
        self.history = []
        self.selected_tiles = []
        self.score = 0
        self.tile_positions = {}
        self.match_counts = {}

        self.score_label = tk.Label(root, text="Score: 0", font=("Arial", 12), bg="dark green", fg="white")
        self.score_label.place(x=10, y=10)

        self.match_label = tk.Label(root, text="Matches: 0", font=("Arial", 12), bg="dark green", fg="white")
        self.match_label.place(x=10, y=30)

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
        self.history.append([dict(t) for t in self.board])

    def new_game(self):
        self.load_tileset_images(self.tileset_var.get())
        self.history.clear()
        self.score = 0
        self.score_label.config(text="Score: 0")
        self.selected_tiles.clear()
        self.tile_positions.clear()

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

        self.draw_board()

    def undo(self):
        if self.history:
            self.board = self.history.pop()
            self.tile_positions = {(t["grid_x"], t["grid_y"], t["z"]): t for t in self.board}
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

                pair_name = tile1["name"]
                count = self.match_counts.get(pair_name, 0)
                points = max(10, 10 * (2 ** count))  # 10, 20, 40, 80, ...
                self.score += points
                self.match_counts[pair_name] = count + 1

                self.score_label.config(text=f"Score: {self.score}")
                self.canvas.after(100, lambda: self.flash_tiles(tile1, tile2))
                self.root.after(400, self.draw_board)
                if not self.board:
                    messagebox.showinfo("You win!", f"Congratulations! Final score: {self.score}")
                elif self.count_possible_matches() == 0:
                    messagebox.showerror("Game Over", "No more possible moves!")
            self.selected_tiles.clear()

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

if __name__ == "__main__":
    root = tk.Tk()
    MahjongGame(root)
    root.mainloop()
