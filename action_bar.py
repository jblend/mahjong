# action_bar.py
import pygame
import os
import sys
TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # If bundled by PyInstaller or similar
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()



class ActionBar:
    def __init__(self, game):
        self.game = game  # access to game state like score, wallet, combo, music_manager, etc.
        self.surface = game.surface
        self.icon_images = game.icon_images
        self.button_rects = game.button_rects
        self.action_bar_top = game.height() - game.ACTION_BAR_HEIGHT
        self.gui_font = game.gui_font

    def draw(self):
        self.__draw_score_and_wallet()
        self.__draw_combo_display()
        self.__draw_possible_matches()
        self.__draw_music_controls()
        self.__draw_volume_slider()
        self.draw_inventory_slots()
        self.__draw_encounter_info()

    def __draw_score_and_wallet(self):
        font = self.gui_font
        bar_y = self.surface.get_height() - 100
        padding = 20

        # Draw Target Score above score
        target_surface = self.gui_font.render(f"Target: {self.game.target_score}", True, (255, 180, 120))
        self.surface.blit(target_surface, (padding, bar_y - 20))

        score_surface = font.render(f"Score: {self.game.score}", True, (255, 255, 255))
        wallet_surface = font.render(f"Wallet: {self.game.wallet}", True, (200, 200, 100))

        self.surface.blit(score_surface, (padding, bar_y + 10))
        self.surface.blit(wallet_surface, (padding, bar_y + 45))

    def __draw_encounter_info(self):
        if not self.game.encounter_mode:
            return

        font = self.gui_font
        surface_w = self.surface.get_width()
        bar_y = self.surface.get_height() - 100
        padding = 20

        # Convert encounter name to Camel Case
        encounter_name = self.game.encounter_mode.replace('_', ' ').title()

        turns_remaining = self.game.encounter_trigger_in
        if turns_remaining == 1:
            turns_string = "Turn"
        else:
            turns_string = "Turns"

        encounter_text = f"Encounter: {encounter_name} Will Trigger In {turns_remaining} {turns_string}"

        # Render the text surface
        encounter_surface = font.render(encounter_text, True, (255, 150, 150))

        # === POSITIONING ===
        x_offset = 600  # ➡️ Increase to move right, decrease to move left
        y_offset = -20  # ⬇️ Increase to move down, decrease to move up

        # Final draw position
        draw_x = padding + x_offset
        draw_y = bar_y + y_offset

        self.surface.blit(encounter_surface, (draw_x, draw_y))

    def __draw_combo_display(self):
        now = pygame.time.get_ticks()
        if not self.game.combo_display_text or now > self.game.combo_end_time + self.game.combo_fade_duration:
            return

        alpha = 255
        if now > self.game.combo_end_time:
            fade_elapsed = now - self.game.combo_end_time
            progress = fade_elapsed / self.game.combo_fade_duration
            alpha = int(255 * (1 - progress ** 2))

        combo_color = self.game.get_combo_color(self.game.combo_level)
        font = pygame.font.SysFont("Arial", 28, bold=True)
        text_surface = font.render(self.game.combo_display_text, True, combo_color)
        text_surface.set_alpha(alpha)

        stroke_color = (0, 0, 0)
        stroke_surfaces = [
            (font.render(self.game.combo_display_text, True, stroke_color), dx, dy)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        ]

        surface_w = self.surface.get_width()
        combo_text_x = surface_w // 2 - text_surface.get_width() // 2
        fuse_y = (
            self.game.combo_bands[0].y + self.game.combo_bands[0].height // 2 - text_surface.get_height() // 2
            if self.game.combo_bands else self.action_bar_top - 20
        )

        for stroke, dx, dy in stroke_surfaces:
            stroke.set_alpha(alpha)
            self.surface.blit(stroke, (combo_text_x + dx, fuse_y + dy))
        self.surface.blit(text_surface, (combo_text_x, fuse_y))

    def __draw_possible_matches(self):
        font = self.gui_font
        surface_w = self.surface.get_width()
        bar_y = self.surface.get_height() - 100
        matches_surface = font.render(f"Possible Matches: {self.game.get_possible_match_count()}", True, (180, 180, 255))
        self.surface.blit(matches_surface, (surface_w - 250, bar_y - 50))

    def __draw_music_controls(self):
        font = self.gui_font
        padding = 20
        bar_y = self.surface.get_height() - 100
        button_size = 40

        # Only rescale icons if size changes
        if getattr(self, "_last_music_button_size", None) != button_size:
            self._last_music_button_size = button_size
            self._scaled_prev_icon = pygame.transform.smoothscale(
                self.icon_images["prev"], (button_size - 10, button_size - 10)
            )
            self._scaled_next_icon = pygame.transform.smoothscale(
                self.icon_images["next"], (button_size - 10, button_size - 10)
            )

        try:
            track_file = self.game.music_manager.get_current_track_name()
            current_track_name = os.path.splitext(os.path.basename(track_file))[0]
        except Exception as e:
            current_track_name = "No Track"
            print(f"[MUSIC ERROR] Failed to get current track name: {e}")

        track_label = font.render(current_track_name, True, (255, 255, 255))
        self.surface.blit(track_label, (padding + 250, bar_y + 10))

        prev_rect = pygame.Rect(padding + 250, bar_y + 45, button_size, button_size)
        pygame.draw.rect(self.surface, (60, 60, 60), prev_rect)
        pygame.draw.rect(self.surface, (15, 15, 15), prev_rect, 2)
        self.surface.blit(self._scaled_prev_icon, self._scaled_prev_icon.get_rect(center=prev_rect.center))
        self.button_rects["prev_track"] = prev_rect

        next_rect = pygame.Rect(padding + 300, bar_y + 45, button_size, button_size)
        pygame.draw.rect(self.surface, (60, 60, 60), next_rect)
        pygame.draw.rect(self.surface, (15, 15, 15), next_rect, 2)
        self.surface.blit(self._scaled_next_icon, self._scaled_next_icon.get_rect(center=next_rect.center))
        self.button_rects["next_track"] = next_rect

    def __draw_volume_slider(self):
        padding = 20
        bar_y = self.game.surface.get_height() - 100
        vol_x = padding + 360
        vol_y = bar_y + 60
        vol_width = 100
        vol_height = 6
        vol_knob_radius = 6

        # Draw volume bar
        pygame.draw.rect(self.surface, (150, 150, 150), (vol_x, vol_y, vol_width, vol_height))

        # Draw knob
        knob_x = vol_x + int(self.game.music_volume * vol_width)
        pygame.draw.circle(self.surface, (255, 255, 255), (knob_x, vol_y + vol_height // 2), vol_knob_radius)

        # Volume icon (optional)
        volume_icon = self.icon_images.get("volume")
        if volume_icon:
            self.surface.blit(volume_icon, (vol_x - 20, vol_y - 4))

        # Interaction area
        self.button_rects["volume_slider"] = pygame.Rect(
            vol_x, vol_y - vol_knob_radius, vol_width, vol_knob_radius * 2
        )

    def draw_inventory_slots(self):
        surface_w = self.surface.get_width()
        bar_y = self.surface.get_height() - 100
        padding = 20
        slot_margin = 10
        slot_w = TILE_WIDTH
        slot_h = TILE_HEIGHT
        start_x = surface_w - (slot_w + slot_margin) * 5 - padding
        slot_y = bar_y - 10

        # Setup drag state (from game)
        dragging_idx = getattr(self.game, "dragging_item_idx", None)
        drag_pos = getattr(self.game, "drag_mouse_pos", None)
        hover_drop = getattr(self.game, "hover_drop_index", None)

        # Cache for scaled icons (avoid scaling every frame)
        if not hasattr(self, "_inv_icon_cache"):
            self._inv_icon_cache = {}  # {(path, slot_w, slot_h): Surface}

        def get_scaled_icon(icon_path):
            key = (icon_path, slot_w, slot_h)
            surf = self._inv_icon_cache.get(key)
            if surf:
                return surf
            full_path = os.path.join(BASE_DIR, icon_path)
            if not os.path.exists(full_path):
                return None
            raw = pygame.image.load(full_path).convert_alpha()
            surf = pygame.transform.smoothscale(raw, (slot_w - 4, slot_h - 4))
            self._inv_icon_cache[key] = surf
            return surf

        # Build & draw slots
        self.slot_rects = []
        for i in range(5):
            rect = pygame.Rect(start_x + i * (slot_w + slot_margin), slot_y, slot_w, slot_h)
            self.slot_rects.append(rect)

            is_hovered = (i == self.game.hovered_inventory_index)
            is_selected = (i == self.game.selected_inventory_index)
            is_drop_target = (hover_drop == i and dragging_idx is not None)

            # Base slot visuals
            bg_color = (100, 100, 100) if is_selected else (80, 80, 80)
            border_color = (255, 255, 0) if is_hovered else (200, 200, 200)
            if is_drop_target:
                border_color = (120, 190, 255)  # highlight drop target

            pygame.draw.rect(self.surface, bg_color, rect)
            pygame.draw.rect(self.surface, border_color, rect, 2)

            # Draw icon (skip if this is the tile being dragged so we don't double-draw)
            if 0 <= i < len(self.game.inventory):
                inv_item = self.game.inventory[i]
                if inv_item:
                    if i != dragging_idx:
                        icon_path = inv_item.get("image")
                        if icon_path:
                            icon = get_scaled_icon(icon_path)
                            if icon:
                                self.surface.blit(icon, (rect.x + 2, rect.y + 2))
                    else:
                        # Draw a faint placeholder in the source slot while dragging
                        pygame.draw.rect(self.surface, (60, 60, 60), rect)
                        pygame.draw.rect(self.surface, (120, 120, 120), rect, 2)

            # Keep button mapping intact
            self.button_rects[f"inventory_{i}"] = rect

        # Draw dragged item ghost last so it’s above everything
        if dragging_idx is not None and drag_pos and dragging_idx < len(self.game.inventory):
            inv_item = self.game.inventory[dragging_idx]
            if inv_item:
                icon_path = inv_item.get("image")
                if icon_path:
                    icon = get_scaled_icon(icon_path)
                    if icon:
                        ghost = icon.copy()
                        ghost.set_alpha(200)  # a bit transparent
                        gx = drag_pos[0] - (icon.get_width() // 2)
                        gy = drag_pos[1] - (icon.get_height() // 2)
                        self.surface.blit(ghost, (gx, gy))
                        # optional ghost outline
                        pygame.draw.rect(self.surface, (120, 190, 255), (gx, gy, icon.get_width(), icon.get_height()),
                                         2)




