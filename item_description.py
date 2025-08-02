import pygame
import os

RARITY_COLORS = {
    "common": (180, 180, 180),
    "uncommon": (80, 200, 120),
    "rare": (80, 120, 255),
    "epic": (160, 80, 255),
    "legendary": (255, 180, 60)
}


class ItemDescriptionCard:
    def __init__(self, font_title, font_body):
        self.font_title = font_title
        self.font_body = font_body
        self.visible = False
        self.item_data = None
        self.position = (0, 0)

    def show(self, item, position):
        print(f"[SHOW] Showing item card for: {item}")
        self.item_data = item
        self.position = position
        self.visible = True

    def hide(self):
        self.visible = False
        self.item_data = None

    def draw(self, surface):
        # print(f"[CARD] Visible: {self.visible}, Item Data: {self.item_data}")
        if not self.visible or not self.item_data:
            return

        # print(f"[DRAW] Showing card for {self.item_data['title']} at {self.position}")

        x, y = self.position
        width = 300
        padding = 10
        line_height = 26
        spacing = 1  # lines worth of vertical spacing between sections

        # Rarity
        rarity = self.item_data.get("rarity", "common")
        rarity_color = RARITY_COLORS.get(rarity, (180, 180, 180))
        rarity_surface = self.font_body.render(f"Rarity: {rarity.title()}", True, rarity_color)

        # Title
        title_surface = self.font_title.render(self.item_data["title"], True, rarity_color)

        # Cooldown type
        cooldown_str = ""
        if "cooldown_match" in self.item_data:
            cooldown_str = f"Cooldown: {self.item_data['cooldown_match']} matches"
        elif "cooldown_time" in self.item_data:
            cooldown_str = f"Cooldown: {self.item_data['cooldown_time']} sec"
        elif "charges" in self.item_data:
            cooldown_str = f"Charges: {self.item_data['charges']}"
        else:
            cooldown_str = "Cooldown: None"
        cooldown_surface = self.font_body.render(cooldown_str, True, (220, 220, 220))

        # Description (wrapped)
        description = self.item_data.get("description", "No description available.")
        max_chars = 20
        words = description.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line + " " + word) <= max_chars:
                current_line += (" " if current_line else "") + word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Compute height with extra spacing between segments
        num_spacers = 3  # title-rarity, rarity-cooldown, cooldown-description
        total_lines = 3 + num_spacers + len(lines)
        height = padding * 2 + line_height * total_lines
        bg_rect = pygame.Rect(x, y, width, height)

        # Draw background
        pygame.draw.rect(surface, (40, 40, 40), bg_rect)
        pygame.draw.rect(surface, rarity_color, bg_rect, 2)

        # Draw segments with spacing
        line_y = y + padding

        surface.blit(title_surface, (x + padding, line_y))
        line_y += line_height * (1 + spacing)

        surface.blit(rarity_surface, (x + padding, line_y))
        line_y += line_height * (1 + spacing)

        surface.blit(cooldown_surface, (x + padding, line_y))
        line_y += line_height * (1 + spacing)

        for line in lines:
            line_surface = self.font_body.render(line, True, (200, 200, 200))
            surface.blit(line_surface, (x + padding, line_y))
            line_y += line_height

