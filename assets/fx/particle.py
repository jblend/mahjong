import random
import pygame
from matplotlib import colormaps
import math

TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
INFERNO_CMAP = colormaps.get_cmap("inferno").reversed()
PRISM_CMAP = colormaps.get_cmap("prism")

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
