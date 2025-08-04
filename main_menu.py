import pygame
import os
import math
import random
import threading
vergilia = os.path.join("assets", "fonts", "vergilia.ttf")
Aveschon = os.path.join("assets", "fonts", "Aveschon.otf")
FacultyGlyphicRegular = os.path.join("assets", "fonts", "FacultyGlyphic-Regular.ttf")

WIDTH = 1000
HEIGHT = 1000

class MainMenuOverlay:
    def __init__(self, surface, logo_image):
        self.surface = surface
        self.logo_font_2 = pygame.font.Font(Aveschon, 80)
        self.logo_font = pygame.font.Font(Aveschon, 75)

        self.title_surf_2 = self.logo_font_2.render("Curiosa", True, (255, 255, 255))
        self.title_surf_1 = self.logo_font.render("Curiosa", True, (0, 0, 0)).convert_alpha()
        self.title_surf_2 = self.logo_font_2.render("Curiosa", True, (255, 255, 255)).convert_alpha()

        self.font = pygame.font.Font(vergilia, 36)
        self.logo = logo_image
        self.buttons = []
        self.active = True
        self.debug = True  # 🔍 Enable this to show mouse position

        self.title_edge_particles = []
        self.logo_edge_particles = []

        self.bg_scroll_x = -1
        self.bg_scroll_y = 1
        self.bg_scroll_speed_x = 0
        self.bg_scroll_speed_y = 0

        # Load background tile
        bg_path = os.path.join("assets", "bg", "bg.png")
        self.background_tile = pygame.image.load(bg_path).convert()

        # Shrunk emitter
        self.emitter_center = (469, 372)
        self.emitter_radius = 5  # ⬅️ smaller radius
        self.init_layout()




        self.title_particles_target = 200
        self.logo_particles_target = 500
        self.misc_particles_target = 25
        self.particles = []
        threading.Thread(target=self._create_particles_worker, args=(self.particles, 50), daemon=True).start()
        self.edge_points = []
        threading.Thread(target=self._extract_logo_edge_points_worker, daemon=True).start()

        threading.Thread(target=self._create_title_edge_particle, daemon=True).start()

        pygame.mixer.init()
        pygame.mixer.music.load(os.path.join("assets", "music", "Spooky Time.wav"))
        pygame.mixer.music.set_volume(0.4)
        pygame.mixer.music.play(-1)  # Loop forever

        self.font_body = pygame.font.Font(FacultyGlyphicRegular, 20)

    def _create_title_edge_particle(self):
        text_mask = self.title_surf_2.copy()
        width, height = text_mask.get_size()
        edge_points = []

        for y in range(1, height - 1):
            for x in range(1, width - 1):
                alpha = text_mask.get_at((x, y))[3]
                if alpha < 10:
                    continue
                neighbors = [(x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
                if any(text_mask.get_at(n)[3] < 10 for n in neighbors):
                    global_x = self.title_rect.left + x
                    global_y = self.title_rect.top + y
                    edge_points.append((global_x, global_y))

        if not edge_points:
            return {"origin": (0, 0), "angle": 0, "distance": 0, "max_distance": 0, "speed": 0, "size": 0,
                    "color": (0, 0, 0), "seed": 0}

        origin = random.choice(edge_points)
        angle = random.uniform(0, 2 * math.pi)
        return {
            "origin": origin,
            "angle": angle,
            "distance": 0,
            "max_distance": random.randint(60, 120),
            "speed": random.uniform(0.5, 1.2),
            "size": random.randint(2, 3),
            "color": (random.randint(160, 255), random.randint(160, 255), 255),
            "seed": random.uniform(0, 10)
        }

    def _create_title_edge_particles_worker(self, count=50):
        self.title_edge_particles = [self._create_title_edge_particle() for _ in range(count)]

    def _draw_title_edge_particles_worker(self, surface_copy):
        current_time = pygame.time.get_ticks() / 1000
        for i, p in enumerate(self.title_edge_particles):
            p["distance"] += p["speed"]
            if p["distance"] > p["max_distance"]:
                self.title_edge_particles[i] = self._create_title_edge_particle()
                continue

            ox, oy = p["origin"]
            dx = math.cos(p["angle"])
            dy = math.sin(p["angle"])
            nx = -dy
            ny = dx
            wave_offset = math.sin(current_time * 5 + p["seed"]) * 6
            x = int(ox + dx * p["distance"] + nx * wave_offset)
            y = int(oy + dy * p["distance"] + ny * wave_offset)

            if not self.title_rect.collidepoint(x, y):
                particle_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
                alpha = min(255, int((p["distance"] / p["max_distance"]) * 255))
                pygame.draw.circle(particle_surf, (*p["color"][:3], alpha), (p["size"], p["size"]), p["size"])
                surface_copy.blit(particle_surf, (x - p["size"], y - p["size"]))

            # Gradually populate over time
            if len(self.title_edge_particles) < self.title_particles_target:
                self.title_edge_particles.append(self._create_title_edge_particle())

            if len(self.logo_edge_particles) < self.logo_particles_target:
                self.logo_edge_particles.append(self._create_edge_particle())

            if len(self.particles) < self.misc_particles_target:
                self.particles.append(self._create_particle())

    def draw_title_edge_particles(self):
        surface_copy = self.surface.copy()  # Make a copy to draw on in another thread
        thread = threading.Thread(target=self._draw_title_edge_particles_worker, args=(surface_copy,))
        thread.start()
        thread.join()  # Wait for thread to finish
        self.surface.blit(surface_copy, (0, 0))  # Blit the completed result back

    def _create_logo_ring_particle(self):
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(self.logo.get_width() // 2 + 10, self.logo.get_width() // 2 + 60)
        speed = random.uniform(0.001, 0.005)
        size = random.randint(1, 3)
        color = (random.randint(120, 255), random.randint(120, 255), 255)
        return {"angle": angle, "distance": distance, "speed": speed, "size": size, "color": color}

    def _extract_logo_edge_points(self):
        edge_points = []
        logo = self.logo.copy()
        logo.lock()
        width, height = logo.get_size()

        for y in range(1, height - 1):
            for x in range(1, width - 1):
                alpha = logo.get_at((x, y))[3]
                if alpha < 10:
                    continue

                # Check for any adjacent transparent pixel = edge
                neighbors = [(x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
                if any(logo.get_at(n)[3] < 10 for n in neighbors):
                    global_x = self.logo_rect.left + x
                    global_y = self.logo_rect.top + y
                    edge_points.append((global_x, global_y))

        logo.unlock()
        print(f"[DEBUG] {len(edge_points)} edge points found on logo")
        return edge_points

    def _extract_logo_edge_points_worker(self):
        edge_points = []
        logo = self.logo.copy()
        logo.lock()
        width, height = logo.get_size()

        for y in range(1, height - 1):
            for x in range(1, width - 1):
                alpha = logo.get_at((x, y))[3]
                if alpha < 10:
                    continue
                neighbors = [(x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
                if any(logo.get_at(n)[3] < 10 for n in neighbors):
                    global_x = self.logo_rect.left + x
                    global_y = self.logo_rect.top + y
                    edge_points.append((global_x, global_y))

        logo.unlock()
        self.edge_points = edge_points  # Store in instance
        print(f"[DEBUG] {len(edge_points)} edge points found on logo")

    def _create_edge_particle(self):
        # Random point along the logo edge
        side = random.choice(["top", "bottom", "left", "right"])
        if side == "top":
            origin = (random.randint(self.logo_rect.left, self.logo_rect.right), self.logo_rect.top)
            angle = -math.pi / 2
        elif side == "bottom":
            origin = (random.randint(self.logo_rect.left, self.logo_rect.right), self.logo_rect.bottom)
            angle = math.pi / 2
        elif side == "left":
            origin = (self.logo_rect.left, random.randint(self.logo_rect.top, self.logo_rect.bottom))
            angle = math.pi
        else:  # right
            origin = (self.logo_rect.right, random.randint(self.logo_rect.top, self.logo_rect.bottom))
            angle = 0

        return {
            "origin": origin,
            "angle": angle,
            "distance": 0,
            "max_distance": random.randint(100, 150),
            "speed": random.uniform(0.5, 1.5),
            "size": random.randint(2, 4),
            "color": (random.randint(180, 255), random.randint(180, 255), 255),
            "seed": random.uniform(0, 10)  # unique wave seed per particle
        }

    def draw_logo_ring_particles(self):
        cx, cy = self.logo_rect.center
        for p in self.logo_ring_particles:
            p["angle"] += p["speed"]
            x = cx + math.cos(p["angle"]) * p["distance"]
            y = cy + math.sin(p["angle"]) * p["distance"]
            pygame.draw.circle(self.surface, p["color"], (int(x), int(y)), p["size"])

    def draw_logo_edge_particles(self):
        surface_copy = self.surface.copy()
        thread = threading.Thread(target=self._draw_logo_edge_particles_worker, args=(surface_copy,))
        thread.start()
        thread.join()
        self.surface.blit(surface_copy, (0, 0))

    def _draw_logo_edge_particles_worker(self, surface_copy):
        current_time = pygame.time.get_ticks() / 1000  # seconds for smoother sin wave

        for i, p in enumerate(self.logo_edge_particles):
            p["distance"] += p["speed"]
            if p["distance"] > p["max_distance"]:
                self.logo_edge_particles[i] = self._create_edge_particle()
                continue

            ox, oy = p["origin"]
            angle = p["angle"]
            distance = p["distance"]

            wave_amplitude = 8
            wave_frequency = 5
            wave_offset = math.sin(current_time * wave_frequency + p["seed"]) * wave_amplitude

            dx = math.cos(angle)
            dy = math.sin(angle)
            nx = -dy
            ny = dx

            x = int(ox + dx * distance + nx * wave_offset)
            y = int(oy + dy * distance + ny * wave_offset)

            if not self.logo_rect.collidepoint(x, y):
                particle_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
                alpha = min(255, int((p["distance"] / p["max_distance"]) * 255))
                pygame.draw.circle(particle_surf, (*p["color"][:3], alpha), (p["size"], p["size"]), p["size"])
                surface_copy.blit(particle_surf, (x - p["size"], y - p["size"]))

    def _create_particle(self):
        angle = random.uniform(0, 2 * math.pi)
        # Smaller spawn distance from center
        distance = random.uniform(0, 15)  # reduced from larger value
        x = self.emitter_center[0] + distance * math.cos(angle)
        y = self.emitter_center[1] + distance * math.sin(angle)

        # Smaller orbit radius to stay close to emitter center
        orbit_radius = random.uniform(15, 40)  # tighter swirl range

        speed = random.uniform(0.002, 0.01)
        size = random.randint(2, 4)
        color = (random.randint(100, 255), random.randint(100, 255), 255)

        return {
            "angle": angle,
            "radius": orbit_radius,  # tight orbital path
            "speed": speed,
            "size": size,
            "color": color
        }

    def _create_particles_worker(self, particle_list, count):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, 15)
            x = self.emitter_center[0] + distance * math.cos(angle)
            y = self.emitter_center[1] + distance * math.sin(angle)
            orbit_radius = random.uniform(15, 40)
            speed = random.uniform(0.002, 0.01)
            size = random.randint(2, 4)
            color = (random.randint(100, 255), random.randint(100, 255), 255)

            particle = {
                "angle": angle,
                "radius": orbit_radius,
                "speed": speed,
                "size": size,
                "color": color
            }
            particle_list.append(particle)

    def tick(self):
        self.bg_scroll_x = (self.bg_scroll_x + self.bg_scroll_speed_x) % self.background_tile.get_width()
        self.bg_scroll_y = (self.bg_scroll_y + self.bg_scroll_speed_y) % self.background_tile.get_height()

    def draw_scrolling_background(self):
        tile_w, tile_h = self.background_tile.get_size()
        screen_w, screen_h = self.surface.get_size()

        start_x = -int(self.bg_scroll_x)
        start_y = -int(self.bg_scroll_y)

        for x in range(start_x, screen_w, tile_w):
            for y in range(start_y, screen_h, tile_h):
                self.surface.blit(self.background_tile, (x, y))

    def draw_particles(self):
        cx, cy = self.emitter_center

        for p in self.particles:
            p["angle"] += p["speed"]
            x = cx + math.cos(p["angle"]) * p["radius"]
            y = cy + math.sin(p["angle"]) * p["radius"]
            pygame.draw.circle(self.surface, p["color"], (int(x), int(y)), p["size"])

    def debug_cursor_position(self, event):
        if self.debug and event.type == pygame.MOUSEMOTION:
            print(f"[DEBUG] Mouse at: {event.pos}")


    def init_layout(self):
        screen_w, screen_h = self.surface.get_size()

        # Resize the logo (e.g., 40% of screen width)
        target_width = int(screen_w * 0.4)
        aspect_ratio = self.logo.get_height() / self.logo.get_width()
        target_height = int(target_width * aspect_ratio)
        self.logo = pygame.transform.smoothscale(self.logo, (target_width, target_height))

        # Position logo
        self.logo_rect = self.logo.get_rect(center=(screen_w // 2, screen_h // 3))
        thread = threading.Thread(target=self._extract_logo_edge_points_worker)
        thread.start()
        thread.join()  # Optional: wait for it to finish if particles depend on it immediately
        self.logo_glow_particles = [self._create_edge_particle() for _ in range(200)]

        # Render title text
        try:
            # Render title text

            self.title_rect = self.title_surf_1.get_rect(
                midtop=(screen_w // 2 - 15, self.logo_rect.bottom - 85)  # Overlaps bottom of logo
            )

        except Exception as e:
            print(f"[ERROR] Failed to render title: {e}")
            self.title_surf = None
            self.title_rect = pygame.Rect(0, 0, 0, 0)

        # Define buttons
        self.buttons = [
            {"label": "New Game", "rect": pygame.Rect(0, 0, 200, 50), "action": "new_game"},
            {"label": "Options", "rect": pygame.Rect(0, 0, 200, 50), "action": "options"},
        ]

        # Position buttons below logo
        spacing = 20
        for i, button in enumerate(self.buttons):
            btn_rect = button["rect"]
            btn_rect.center = (screen_w // 2, self.logo_rect.bottom + 50 + i * (btn_rect.height + spacing))

            # Generate title edge particles only after title is rendered
        if self.title_surf_2 and self.title_rect:
            thread = threading.Thread(target=self._create_title_edge_particles_worker, args=(50,))
            thread.start()
            thread.join()  # Optional: remove if you don't need particles immediately

    def draw(self):
        self.draw_scrolling_background()


        # Dim background
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # translucent black
        self.surface.blit(overlay, (0, 0))

        if self.particles:
            self.draw_particles()

        # Draw logo
        # self.draw_logo_ring_particles()
        self.draw_logo_edge_particles()
        self.draw_title_edge_particles()
        self.surface.blit(self.logo, self.logo_rect)

        if self.title_surf_2:
            outline_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (-2, 2), (2, -2), (2, 2)]
            for ox, oy in outline_offsets:
                outline_pos = self.title_rect.move(ox, oy)
                outline_surf = self.logo_font_2.render("Curiosa", True, (0, 0, 0))
                self.surface.blit(outline_surf, outline_pos)

            self.surface.blit(self.title_surf_2, self.title_rect)



        # Draw black background behind title
        if self.title_surf_2:
            outline_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (-2, 2), (2, -2), (2, 2)]
            for ox, oy in outline_offsets:
                outline_pos = self.title_rect.move(ox, oy)
                outline_surf = self.logo_font_2.render("Curiosa", True, (0, 0, 0))
                self.surface.blit(outline_surf, outline_pos)

            # White foreground text
            self.surface.blit(self.title_surf_2, self.title_rect)

        # Draw buttons
        for button in self.buttons:
            pygame.draw.rect(self.surface, (50, 50, 50), button["rect"])
            pygame.draw.rect(self.surface, (200, 200, 200), button["rect"], 2)

            label_surf = self.font.render(button["label"], True, (255, 255, 255))
            label_rect = label_surf.get_rect(center=button["rect"].center)
            self.surface.blit(label_surf, label_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button["rect"].collidepoint(event.pos):
                    return button["action"]  # return the action string
        return None


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Curiosa")
    font = pygame.font.SysFont("Arial", 48)

    try:
        logo = pygame.image.load("assets/logo.png").convert_alpha()
    except Exception as e:
        print(f"[ERROR] Could not load logo image: {e}")
        logo = pygame.Surface((200, 100), pygame.SRCALPHA)
        pygame.draw.rect(logo, (255, 255, 255), logo.get_rect(), 2)

    menu = MainMenuOverlay(screen, logo)

    running = True
    while running:
        screen.fill((20, 20, 20))  # Background

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if menu.active:
                # menu.debug_cursor_position(event)  # 🧭 Show cursor coords
                result = menu.handle_event(event)
                if result == "new_game":
                    print("Start New Game")
                    menu.active = False
                elif result == "options":
                    print("Open Options Menu")

        if menu.active:
            menu.draw()

        pygame.display.flip()

    pygame.quit()
