import os
import json
import random
import pygame
import traceback
from constants import TILE_WIDTH, TILE_HEIGHT, ITEMS, BASE_DIR


class Shop:
    def __init__(self, game):
        self.game = game
        self.surface = game.surface
        self.gui_font = game.gui_font
        self.money_font = game.money_font
        self.item_font = game.item_font
        self.button_font = game.button_font
        self.inventory = game.inventory
        self.wallet = game.wallet
        self.items_loaded_this_round = False

        self.in_shop = False
        self.shop_items = []
        self.shop_button_rects = []
        self.shop_selected_item_index = None
        self.shop_message = ""

    def init_shop(self):
        self.shop_selected_item_index = None
        self.shop_message = ""
        self.shop_items = []

    def enter_shop_screen(self):
        print("[SHOP] Entering shop screen...")

        self.in_shop = True

        # Transfer leftover points
        leftover = self.game.score - self.game.target_score
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
        self.game.update()

    def load_items(self):
        print(f"[SHOP] Attempting to load shop items from: {ITEMS}")
        try:
            with open(ITEMS, "r") as f:
                all_items = json.load(f)
                print(f"[SHOP] Loaded {len(all_items)} items from JSON.")
                k = min(4, len(all_items))
                self.shop_items = random.sample(all_items, k=k) if k > 0 else []
                print(f"[SHOP] Selected {len(self.shop_items)} random shop items.")
        except Exception as e:
            print("[SHOP ERROR] Failed to load shop items.")
            traceback.print_exc()
            self.shop_items = []

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

    def draw_overlay(self):
        try:
            self.__draw_overlay_background()
            self.__draw_title_and_wallet()
            self.__draw_shop_items()
            self.__draw_shop_buttons()
            self.__draw_inventory()
            self.__draw_shop_message()
        except Exception as e:
            print("[DRAW SHOP ERROR]")
            traceback.print_exc()

    def __draw_shop_message(self):
        if self.shop_message:
            y = self.surface.get_height() - 70  # Adjust up/down
            msg = self.gui_font.render(self.shop_message, True, (255, 100, 100))
            self.surface.blit(msg, (80, y))

    def __draw_overlay_background(self):
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 215))
        self.surface.blit(overlay, (0, 0))

    def __draw_shop_items(self):
        self.shop_button_rects.clear()

        start_y = 150  # Raise/lower the list by adjusting this
        x = 80

        for i, item in enumerate(self.shop_items):
            # print(f"[DRAW SHOP] Drawing {len(self.shop_items)} items")
            y = start_y + i * (TILE_HEIGHT + 30)
            name = item.get("title", "???")
            cost = item.get("cost", 999)
            img_path = item.get("image", None)

            item_rect = pygame.Rect(x, y, 400, TILE_HEIGHT + 10)
            self.shop_button_rects.append((item_rect, item))

            # Draw icon
            if img_path:
                full_path = os.path.join(BASE_DIR, img_path)
                if os.path.exists(full_path):
                    icon = pygame.image.load(full_path).convert_alpha()
                    icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                    self.surface.blit(icon, (x + 10, y + 5))

            # Draw name and cost
            name_text = self.item_font.render(name, True, (255, 255, 255))
            cost_text = self.money_font.render(f"{cost} pts", True, (255, 255, 100))
            self.surface.blit(name_text, (x + TILE_WIDTH + 20, y + 5))
            self.surface.blit(cost_text, (x + TILE_WIDTH + 20, y + TILE_HEIGHT // 2))

    def __draw_shop_buttons(self):
        font = self.button_font
        btn_height = 60
        shadow_offset = 2

        # Y-position based on number of items
        base_y = 150 + len(self.shop_items) * (TILE_HEIGHT + 30) + 80
        reroll_x = 80
        continue_x = self.surface.get_width() - 750 - 260

        # Colors
        bg_color = (15, 15, 15, 38)
        border_color = (0, 60, 0, 128)
        shadow_color = (0, 0, 0)
        hover_color = (0, 125, 0)

        # Reroll
        reroll_rect = pygame.Rect(reroll_x, base_y, 180, btn_height)
        self.game.button_rects["shop_reroll"] = reroll_rect
        hovering_reroll = reroll_rect.collidepoint(pygame.mouse.get_pos())

        pygame.draw.rect(self.surface, bg_color, reroll_rect)
        pygame.draw.rect(self.surface, border_color, reroll_rect, 3)
        self.__blit_centered_button(font, "Reroll (-50)", reroll_rect, hover_color if hovering_reroll else hover_color,
                                    shadow_color, shadow_offset)

        # Continue
        continue_rect = pygame.Rect(continue_x, base_y, 260, btn_height)
        self.game.button_rects["shop_continue"] = continue_rect
        hovering_continue = continue_rect.collidepoint(pygame.mouse.get_pos())

        pygame.draw.rect(self.surface, bg_color, continue_rect)
        pygame.draw.rect(self.surface, border_color, continue_rect, 3)
        self.__blit_centered_button(font, "Continue", continue_rect, hover_color if hovering_continue else hover_color,
                                    shadow_color, shadow_offset)

    def __draw_title_and_wallet(self):
        self.surface.blit(self.gui_font.render("Welcome to the Shop", True, (255, 255, 255)), (80, 60))
        self.surface.blit(self.money_font.render(f"Wallet: {self.wallet} pts", True, (255, 255, 100)), (80, 100))

    def __draw_items(self):
        self.shop_button_rects.clear()
        base_y = 150
        for i, item in enumerate(self.shop_items):
            name = item.get("title", "???")
            cost = item.get("cost", 999)
            img_path = item.get("image", None)
            y = base_y + i * (TILE_HEIGHT + 30)
            item_rect = pygame.Rect(80, y, 400, TILE_HEIGHT + 10)

            if img_path:
                full_path = os.path.join(BASE_DIR, img_path)
                if os.path.exists(full_path):
                    icon = pygame.image.load(full_path).convert_alpha()
                    icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                    self.surface.blit(icon, (90, y + 5))

            name_text = self.item_font.render(name, True, (255, 255, 255))
            cost_text = self.money_font.render(f"{cost} pts", True, (255, 255, 100))
            self.surface.blit(name_text, (100 + TILE_WIDTH, y + 5))
            self.surface.blit(cost_text, (100 + TILE_WIDTH, y + TILE_HEIGHT // 2))

            self.shop_button_rects.append((item_rect, item))

    def __draw_buttons(self):
        font = self.button_font
        bar_y = 150 + len(self.shop_items) * (TILE_HEIGHT + 30) + 80
        btn_h = 60
        shadow_offset = 2
        green = (0, 125, 0)
        bg_color = (15, 15, 15, 38)
        border_color = (0, 60, 0, 128)
        shadow = (0, 0, 0)

        # Reroll button
        reroll_rect = pygame.Rect(80, bar_y, 180, btn_h)
        self.game.button_rects["shop_reroll"] = reroll_rect
        hover_reroll = reroll_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.surface, bg_color, reroll_rect)
        pygame.draw.rect(self.surface, border_color, reroll_rect, 3)
        text = "Reroll (-50)"
        self.__blit_centered_button(font, text, reroll_rect, green if hover_reroll else green, shadow, shadow_offset)

        # Continue button
        continue_rect = pygame.Rect(self.surface.get_width() - 750 - 260, bar_y, 260, 60)
        self.game.button_rects["shop_continue"] = continue_rect
        hover_continue = continue_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.surface, bg_color, continue_rect)
        pygame.draw.rect(self.surface, border_color, continue_rect, 3)
        self.__blit_centered_button(font, "Continue", continue_rect, green if hover_continue else green, shadow, shadow_offset)

    def __draw_inventory(self):
        self.surface.blit(self.gui_font.render("Inventory:", True, (255, 255, 255)), (500, 150))
        for i in range(5):
            x = 500 + i * (TILE_WIDTH + 10)
            y = 190
            rect = pygame.Rect(x, y, TILE_WIDTH, TILE_HEIGHT)
            pygame.draw.rect(self.surface, (15, 15, 15), rect)
            pygame.draw.rect(self.surface, (0, 60, 0), rect, 2)
            if i < len(self.inventory):
                icon_path = self.inventory[i].get("image", None)
                if icon_path:
                    full_path = os.path.join(BASE_DIR, icon_path)
                    if os.path.exists(full_path):
                        icon = pygame.image.load(full_path).convert_alpha()
                        icon = pygame.transform.scale(icon, (TILE_WIDTH, TILE_HEIGHT))
                        self.surface.blit(icon, (x, y))
            self.game.button_rects[f"inventory_{i}"] = rect

    def __draw_message(self):
        if self.shop_message:
            msg = self.gui_font.render(self.shop_message, True, (255, 100, 100))
            self.surface.blit(msg, (80, self.surface.get_height() - 70))

    def __blit_centered_button(self, font, text, rect, color, shadow_color, offset):
        label = font.render(text, True, color)
        shadow = font.render(text, True, shadow_color)
        self.surface.blit(shadow, (rect.centerx - label.get_width() // 2 + offset,
                                   rect.centery - label.get_height() // 2 + offset))
        self.surface.blit(label, (rect.centerx - label.get_width() // 2,
                                  rect.centery - label.get_height() // 2))
