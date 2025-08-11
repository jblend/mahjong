import random
import pygame
from matplotlib import colormaps
import matplotlib.colors as mcolors
import math
import logging

TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
INFERNO_CMAP = colormaps.get_cmap("inferno").reversed()
PRISM_CMAP = colormaps.get_cmap("prism")
LIGHT_RAY_COLOR_MAP = [
    (255, 255, 255),   # Pure White
    (240, 240, 200),   # Pale Yellow
    (255, 250, 180),   # Warm Glow
    (200, 200, 255),   # Cool Blue Tint
    (255, 220, 200)    # Warm Peach Tint
]

class SmokeParticle:
    def __init__(self, x, y):
        self.x = x + TILE_WIDTH // 2
        self.y = y + TILE_HEIGHT // 2
        self.radius = 5 + random.randint(0, 5)
        self.alpha = 255
        self.lifetime = 600  # milliseconds
        self.start_time = pygame.time.get_ticks()
        self.dx = random.uniform(-1, 1)
        self.dy = random.uniform(-2, -0.5)

    def update(self):
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed > self.lifetime:
            return False

        progress = elapsed / self.lifetime
        self.alpha = max(0, 255 * (1 - progress))
        self.radius = 5 + int(10 * progress)
        self.x += self.dx
        self.y += self.dy
        return True

    def draw(self, surface):
        if self.alpha <= 0:
            return
        surf = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (180, 180, 180, int(self.alpha)), (self.radius, self.radius), self.radius)
        surface.blit(surf, (self.x - self.radius, self.y - self.radius))

class SparkleParticle:
    def __init__(self, x, y):
        self.x = x + TILE_WIDTH // 2
        self.y = y + TILE_HEIGHT // 2
        self.start_x = self.x
        self.start_y = self.y

        self.radius = random.randint(3, 5)
        self.base_radius = self.radius
        self.alpha = 255
        self.lifetime = 600  # milliseconds
        self.start_time = pygame.time.get_ticks()

        # Explosion: use angle and speed for radial movement
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 3.5)
        self.dx = math.cos(angle) * speed
        self.dy = math.sin(angle) * speed

        self.jitter = random.uniform(0.2, 0.5)

    def update(self):
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed > self.lifetime:
            return False

        progress = elapsed / self.lifetime
        self.alpha = max(0, 255 * (1 - progress))
        self.radius = max(1, self.base_radius * (1 - progress))  # shrink over time
        self.x += self.dx + random.uniform(-self.jitter, self.jitter)
        self.y += self.dy + random.uniform(-self.jitter, self.jitter)
        return True

    def draw(self, surface):
        if self.alpha <= 0:
            return

        # Color from prism colormap based on progress
        progress = 1 - self.alpha / 255
        r, g, b, _ = PRISM_CMAP(progress)
        color = (int(r * 255), int(g * 255), int(b * 255))

        surf = pygame.Surface((int(self.radius * 2), int(self.radius * 2)), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*color, int(self.alpha)), (int(self.radius), int(self.radius)), int(self.radius))
        surface.blit(surf, (self.x - self.radius, self.y - self.radius))


class FireParticle:
    def __init__(self, x, y):
        self.x = x + TILE_WIDTH // 2
        self.y = y + TILE_HEIGHT // 2
        self.radius = random.randint(3, 5)
        self.alpha = 255
        self.lifetime = 700
        self.start_time = pygame.time.get_ticks()
        self.dx = random.uniform(-0.7, 0.7)
        self.dy = random.uniform(-1.5, -0.3)

    def update(self):
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed > self.lifetime:
            return False

        progress = elapsed / self.lifetime
        self.alpha = max(0, 255 * (1 - progress))
        self.radius = int(5 + 3 * (1 - progress))
        self.x += self.dx
        self.y += self.dy
        return True

    def draw(self, surface):
        if self.alpha <= 0:
            return
        # Get RGB from colormap based on progress (inverse of fade-out)
        progress = 1 - self.alpha / 255
        r, g, b, _ = INFERNO_CMAP(progress)
        rgb_color = (int(r * 255), int(g * 255), int(b * 255))

        surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*rgb_color, int(self.alpha)), (self.radius, self.radius), self.radius)
        surface.blit(surf, (self.x - self.radius, self.y - self.radius))

class WindParticle:
    def __init__(self, x, y, direction="east"):
        self.x = x
        self.y = y
        self.alpha = 200 + random.randint(-30, 30)
        self.radius = random.randint(6, 10)
        self.lifetime = 800  # milliseconds
        self.start_time = pygame.time.get_ticks()

        # Directional velocity mapping
        direction = direction.lower()
        angle_map = {
            "north": -math.pi / 2,
            "south": math.pi / 2,
            "east": 0,
            "west": math.pi,
        }
        angle = angle_map.get(direction, 0)  # Default to east
        speed = random.uniform(1.0, 2.5)

        self.dx = math.cos(angle) * speed + random.uniform(-0.2, 0.2)
        self.dy = math.sin(angle) * speed + random.uniform(-0.2, 0.2)

        # Gentle wave motion (perlin-esque wobble)
        self.phase = random.uniform(0, 2 * math.pi)
        self.wobble_amplitude = random.uniform(1, 3)

    def update(self):
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed > self.lifetime:
            return False

        progress = elapsed / self.lifetime
        self.alpha = max(0, int(200 * (1 - progress)))
        self.radius = max(1, int(6 + 4 * (1 - progress)))

        # Movement with wobble
        self.x += self.dx + math.sin(progress * 6 + self.phase) * self.wobble_amplitude * 0.1
        self.y += self.dy + math.cos(progress * 6 + self.phase) * self.wobble_amplitude * 0.1

        return True

    def draw(self, surface):
        if self.alpha <= 0:
            return

        surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (180, 220, 255, self.alpha), (self.radius, self.radius), self.radius)
        surface.blit(surf, (self.x - self.radius, self.y - self.radius))

class SelectedParticle:
    def __init__(self, x, y, width, height):
        # Choose a perimeter edge for emission
        edge = random.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            self.x = x + random.uniform(0, width)
            self.y = y
        elif edge == "bottom":
            self.x = x + random.uniform(0, width)
            self.y = y + height
        elif edge == "left":
            self.x = x
            self.y = y + random.uniform(0, height)
        elif edge == "right":
            self.x = x + width
            self.y = y + random.uniform(0, height)

        self.vx = 0
        self.vy = random.uniform(-2.0, -1.2)
        self.lifetime = random.randint(10, 25)
        self.initial_alpha = random.randint(200, 255)
        self.alpha = self.initial_alpha

        self.stroke_color = random.choice([
            # (255, 255, 100),  # warm yellow
            (200, 255, 255),  # icy blue
            # (255, 200, 240),  # pink tint
            (180, 220, 255),  # soft cyan
        ])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        self.alpha = int(self.initial_alpha * (self.lifetime / 60))
        return self.is_alive()

    def is_alive(self):
        return self.lifetime > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return

        # Create feathered 3x14 surface with transparent background
        surf = pygame.Surface((3, 14), pygame.SRCALPHA)

        # Outer feather (1px border)
        feather_alpha = int(self.alpha * 0.25)
        feather_color = (*self.stroke_color, feather_alpha)
        pygame.draw.rect(surf, feather_color, pygame.Rect(0, 0, 3, 14), border_radius=2)

        # Center white beam
        white_color = (255, 255, 255, self.alpha)
        pygame.draw.rect(surf, white_color, pygame.Rect(1, 1, 1, 12))  # Inner bright line

        surface.blit(surf, (self.x - 1, self.y - 1))  # Offset to center the 3px beam

class SelectedParticle_B:
    def __init__(self, x, y, width, height):
        self.rect_x = x
        self.rect_y = y
        self.width = width
        self.height = height

        self.perimeter = 2 * (width + height)
        self.perimeter_pos = random.uniform(0, self.perimeter)
        self.speed = random.uniform(2.0, 4.5)

        self.lifetime = random.randint(100, 120)
        self.initial_alpha = random.randint(180, 240)
        self.alpha = self.initial_alpha

        self.stroke_color = random.choice([
            (255, 255, 100),   # warm yellow
            (255, 200, 240),   # pink tint
            (180, 220, 255),   # soft cyan
        ])

    def update(self):
        self.perimeter_pos = (self.perimeter_pos + self.speed) % self.perimeter
        self.lifetime -= 1
        self.alpha = int(self.initial_alpha * (self.lifetime / 60))
        return self.is_alive()

    def is_alive(self):
        return self.lifetime > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return

        x, y = self.rect_x, self.rect_y
        w, h = self.width, self.height
        pos = self.perimeter_pos

        # Determine position along the perimeter
        if pos < w:  # Top edge
            px, py = x + pos, y
        elif pos < w + h:  # Right edge
            px, py = x + w, y + (pos - w)
        elif pos < w + h + w:  # Bottom edge
            px, py = x + w - (pos - w - h), y + h
        else:  # Left edge
            px, py = x, y + h - (pos - 2 * w - h)

        # Draw particle
        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        color = (self.stroke_color)
        try:
            pygame.draw.circle(surf, color, (2, 2), 2)
        except ValueError:
            print(f"[ERROR] Invalid color: {color}")
            return

        surface.blit(surf, (px - 2, py - 2))

class SelectedParticle_Fire:
    """
    Perimeter-tracing 'flame' particle:
      - Traverses the rectangle perimeter (like SelectedParticle_B)
      - Colors from INFERNO_CMAP with alpha fade (like FireParticle)
      - Small outward drift along edge normal to feel 'fiery'
    """
    def __init__(self, x, y, width, height):
        # Emitter rectangle (screen-space)
        self.rect_x = x
        self.rect_y = y
        self.width = max(1, int(width))
        self.height = max(1, int(height))

        # Perimeter motion
        self.perimeter = 2 * (self.width + self.height)
        self.perimeter_pos = random.uniform(0, self.perimeter)
        self.speed = random.uniform(2.0, 4.0)  # px/frame along the edge path

        # Lifetime (ms) & fade
        self.lifetime_ms = random.randint(600, 900)
        self.start_time = pygame.time.get_ticks()

        # Size & drift
        self.base_radius = random.randint(3, 5)
        self.max_perp_drift = random.uniform(3.0, 7.0)   # outward from edge
        self.jitter = random.uniform(0.5, 1.25)          # small lateral wobble

        # Cache current draw state
        self.alpha = 255
        self.rgb = (255, 180, 80)

    def _edge_point_and_normal(self, pos):
        """
        Return (px,py) on perimeter and outward normal (nx,ny) for the given pos.
        Screen Y increases downward, so 'outward' is: top(-y), right(+x), bottom(+y), left(-x).
        """
        x, y, w, h = self.rect_x, self.rect_y, self.width, self.height

        if pos < w:                               # top edge, left→right
            px, py = x + pos, y
            nx, ny = 0.0, -1.0
        elif pos < w + h:                         # right edge, top→bottom
            t = pos - w
            px, py = x + w, y + t
            nx, ny = 1.0, 0.0
        elif pos < w + h + w:                     # bottom edge, right→left
            t = pos - (w + h)
            px, py = x + w - t, y + h
            nx, ny = 0.0, 1.0
        else:                                     # left edge, bottom→top
            t = pos - (2 * w + h)
            px, py = x, y + h - t
            nx, ny = -1.0, 0.0

        return (px, py), (nx, ny)

    def update(self):
        # Time-based progress
        now = pygame.time.get_ticks()
        elapsed = now - self.start_time
        if elapsed >= self.lifetime_ms:
            return False

        progress = max(0.0, min(1.0, elapsed / self.lifetime_ms))  # 0→1

        # Advance along perimeter
        self.perimeter_pos = (self.perimeter_pos + self.speed) % self.perimeter

        # Color & alpha from Inferno
        r, g, b, _ = INFERNO_CMAP(progress)  # 0..1 floats
        self.rgb = (int(r * 255), int(g * 255), int(b * 255))
        self.alpha = int(255 * (1.0 - progress))  # fade out over lifetime

        return True

    def draw(self, surface):
        if self.alpha <= 0:
            return

        # Base point + outward drift
        (px, py), (nx, ny) = self._edge_point_and_normal(self.perimeter_pos)

        # Make flames 'lick' outward, more drift later in life; add tiny wobble
        # Use perimeter_pos as a phase so neighbors don't sync
        phase = (self.perimeter_pos * 0.025)
        wobble = (math.sin(phase) + math.cos(1.37 * phase)) * 0.5
        life_scale = 0.35 + 0.65 * (1.0 - self.alpha / 255.0)  # grows a bit as it fades
        drift = self.max_perp_drift * life_scale

        ox = nx * drift + wobble * self.jitter
        oy = ny * drift + wobble * self.jitter

        # Flame radius: grows slightly, then shrinks
        t = 1.0 - self.alpha / 255.0
        radius = max(2, int(self.base_radius + 2 * (1.0 - abs(2 * t - 1.0))))

        # Draw
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.rgb, self.alpha), (radius, radius), radius)
        surface.blit(surf, (px + ox - radius, py + oy - radius))

class ComboBand:
    def __init__(self, x, y, width, height, color, duration, current_points=0, max_points=5):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.duration = duration  # in ms
        self.current_points = current_points
        self.max_points = max_points
        self.start_time = pygame.time.get_ticks()

    def is_active(self):
        return pygame.time.get_ticks() - self.start_time <= self.duration

    def refresh(self, current_points=None, max_points=None):
        """Update fuse fill and restart burn."""
        if current_points is not None:
            self.current_points = current_points
        if max_points is not None:
            self.max_points = max_points
        self.start_time = pygame.time.get_ticks()  # Reset the fuse burn

    def draw(self, surface, particles, gradient=None):
        now = pygame.time.get_ticks()
        elapsed = now - self.start_time

        if elapsed > self.duration:
            return

        burn_progress = min(elapsed / self.duration, 1.0)
        fill_ratio = min(self.current_points / self.max_points, 1.0)
        fill_width = int(self.width * fill_ratio)
        remaining_width = int(fill_width * (1.0 - burn_progress))

        # Draw background bar
        pygame.draw.rect(surface, (50, 50, 50), (self.x, self.y, self.width, self.height))

        if remaining_width > 0:
            burn_rect = pygame.Rect(self.x, self.y, remaining_width, self.height)
            pygame.draw.rect(surface, self.color, burn_rect)

            # Emit 1 particle per draw cycle at burn tip (avoid duplicates here!)
            if gradient:
                particle_color = random.choice(gradient)
            else:
                particle_color = self.color

            tip_x = self.x + remaining_width
            tip_y = self.y + self.height // 2

            # Only emit a particle with some throttling (e.g., every 50ms)
            if not hasattr(self, "last_emit_time"):
                self.last_emit_time = 0
            if now - self.last_emit_time > 50:
                particles.append(FuseParticle(tip_x, tip_y, particle_color))
                self.last_emit_time = now


class FuseParticle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-1.5, -0.5)
        self.alpha = 255
        self.color = color
        self.radius = random.randint(1, 2)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.alpha -= 5  # Fade out

    def draw(self, surface):
        if self.alpha > 0:
            surface_color = (*self.color[:3], max(0, min(255, int(self.alpha))))
            s = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, surface_color, (self.radius, self.radius), self.radius)
            surface.blit(s, (self.x, self.y))






