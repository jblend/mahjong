import math
import random
from PyQt5.QtCore import QTimer

# These constants may need to be imported from your main settings
TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH = 64, 96, 6
from assets.fx.particle import WindParticle


class EncounterEngine:
    def __init__(self, context):
        self.context = context

    def animate_crush_tiles(self, tiles, steps=12, interval=25):
        ctx = self.context
        ctx.animation_step = 0
        ctx.animation_steps = steps
        ctx.animating_tiles = tiles

        def animate_step():
            if ctx.animation_step >= ctx.animation_steps:
                for tile in ctx.animating_tiles:
                    tile.update({
                        "x": tile["target_x"],
                        "y": tile["target_y"],
                        "grid_x": tile["target_grid_x"],
                        "grid_y": tile["target_grid_y"],
                        "z": tile["target_z"],
                        "alpha": 255
                    })
                    tile.pop("fading", None)

                ctx.rebuild_tile_positions()
                ctx.animating_tiles = []
                ctx.update_canvas()
                return

            progress = (ctx.animation_step + 1) / ctx.animation_steps
            for tile in ctx.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                if tile.get("fading"):
                    tile["alpha"] = int(255 * (1 - 2 * progress)) if progress <= 0.5 else int(255 * (2 * progress - 1))

            ctx.animation_step += 1
            ctx.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_parallax_tiles(self, tiles, steps=10, interval=30):
        ctx = self.context
        ctx.animation_step = 0
        ctx.animation_steps = steps
        ctx.animating_tiles = tiles

        def animate_step():
            if ctx.animation_step >= ctx.animation_steps:
                for tile in ctx.animating_tiles:
                    tile["x"] = tile["target_x"]
                    tile["y"] = tile.get("target_y", tile["y"])
                    tile["grid_x"] = tile["target_grid_x"]  # ✅ properly update here
                    tile["grid_y"] = tile.get("target_grid_y", tile["grid_y"])
                    tile["alpha"] = 255
                    tile.pop("fading", None)

                ctx.rebuild_tile_positions()
                ctx.animating_tiles = []
                return

            progress = (ctx.animation_step + 1) / ctx.animation_steps
            for tile in ctx.animating_tiles:
                sx = tile.get("start_x", tile["x"])
                tx = tile.get("target_x", tile["x"])
                tile["x"] = sx + (tx - sx) * progress

                sy = tile.get("start_y", tile["y"])
                ty = tile.get("target_y", tile.get("y", sy))
                tile["y"] = sy + (ty - sy) * progress

                if tile.get("fading"):
                    tile["alpha"] = int(80 + (255 - 80) * progress)

            ctx.animation_step += 1
            ctx.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_slot_tiles(self, tiles, steps=14, interval=20):
        ctx = self.context
        ctx.animation_step = 0
        ctx.animation_steps = steps
        ctx.animating_tiles = tiles

        def animate_step():
            if ctx.animation_step >= ctx.animation_steps:
                for tile in ctx.animating_tiles:
                    tile.update({
                        "y": tile["target_y"],
                        "grid_y": tile["target_grid_y"],
                        "z": tile["target_z"],
                        "alpha": 255
                    })
                    tile.pop("flicker", None)

                ctx.rebuild_tile_positions()
                ctx.animating_tiles = []
                ctx.update_canvas()
                return

            progress = (ctx.animation_step + 1) / ctx.animation_steps
            for tile in ctx.animating_tiles:
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                if tile.get("flicker"):
                    flicker_phase = (ctx.animation_step % 4) / 4
                    tile["alpha"] = int(180 + 75 * (0.5 + 0.5 * math.sin(2 * math.pi * flicker_phase)))

            ctx.animation_step += 1
            ctx.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_wind_shift(self, tiles, new_positions, steps=12, interval=30):
        ctx = self.context

        if not hasattr(ctx, "particles"):
            ctx.particles = []

        ctx.animation_step = 0
        ctx.animation_steps = steps
        ctx.animating_tiles = tiles

        pre_top = set(
            (gx, gy)
            for (gx, gy, gz) in ctx.tile_positions
            if not any((gx, gy, gz + 1) in ctx.tile_positions for gz in range(10))
        )
        post_top = {(t["target_grid_x"], t["target_grid_y"]) for t in tiles}
        newly_exposed = post_top - pre_top

        for tile in ctx.board:
            key = (tile["grid_x"], tile["grid_y"])
            tile["will_become_exposed"] = key in newly_exposed

        ctx._vacated_during_animation = {(t["grid_x"], t["grid_y"]) for t in tiles}

        def animate_step():
            if ctx.animation_step >= ctx.animation_steps:
                for tile in ctx.animating_tiles:
                    tile.update({
                        "x": tile["target_x"],
                        "y": tile["target_y"],
                        "grid_x": tile["target_grid_x"],
                        "grid_y": tile["target_grid_y"],
                        "z": tile["target_z"],
                        "alpha": 255
                    })
                    tile.pop("fading", None)
                    tile.pop("will_become_exposed", None)
                    new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

                ctx.board = list(new_positions.values())
                ctx.tile_positions = new_positions
                ctx.animating_tiles = []
                ctx.update_canvas()
                del ctx._vacated_during_animation
                return

            progress = (ctx.animation_step + 1) / ctx.animation_steps
            for tile in ctx.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

                if tile.get("fading"):
                    tile["alpha"] = int(200 + 55 * math.sin(progress * math.pi))

                if ctx.animation_step % 2 == 0:
                    px = tile["x"] + TILE_WIDTH // 2 + random.randint(-4, 4)
                    py = tile["y"] + TILE_HEIGHT // 2 + random.randint(-4, 4)
                    ctx.particles.append(WindParticle(px, py, direction=ctx.current_wind_direction))

            ctx.animation_step += 1
            ctx.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

    def animate_rotation(self, clockwise=True, steps=12, interval=30):
        ctx = self.context

        if not ctx.board:
            return

        new_board = []
        new_positions = {}
        animating_tiles = []

        tile_w, tile_h, tile_d = TILE_WIDTH, TILE_HEIGHT, TILE_DEPTH
        offset_x, offset_y = ctx.offset_x, ctx.offset_y

        blocks = {}
        for tile in ctx.board:
            gx, gy = tile["grid_x"], tile["grid_y"]
            bx, by = (gx // 3) * 3, (gy // 3) * 3
            blocks.setdefault((bx, by), []).append(tile)

        for (bx, by), tiles in blocks.items():
            stacks = {}
            for t in tiles:
                stacks.setdefault((t["grid_x"], t["grid_y"]), []).append(t)

            for stack in stacks.values():
                stack.sort(key=lambda t: t["z"])

            grid = [[None for _ in range(3)] for _ in range(3)]
            for (gx, gy), stack in stacks.items():
                lx, ly = gx - bx, gy - by
                if 0 <= lx < 3 and 0 <= ly < 3:
                    grid[ly][lx] = stack

            for y in range(3):
                for x in range(3):
                    stack = grid[y][x]
                    if not stack:
                        continue

                    nx, ny = (2 - y, x) if clockwise else (y, 2 - x)
                    tx, ty = bx + nx, by + ny

                    for dz, tile in enumerate(stack):
                        abs_x, abs_y = ctx.get_tile_pixel_position(
                            tx, ty, tile["z"], tile_w, tile_h, tile_d, offset_x, offset_y
                        )

                        tile.update({
                            "start_x": tile["x"],
                            "start_y": tile["y"],
                            "target_grid_x": tx,
                            "target_grid_y": ty,
                            "target_z": tile["z"],
                            "target_x": abs_x,
                            "target_y": abs_y
                        })
                        animating_tiles.append(tile)

        ctx.animation_step = 0
        ctx.animation_steps = steps
        ctx.animating_tiles = animating_tiles

        def animate_step():
            if ctx.animation_step >= ctx.animation_steps:
                for tile in ctx.animating_tiles:
                    tile.update({
                        "x": tile["target_x"],
                        "y": tile["target_y"],
                        "grid_x": tile["target_grid_x"],
                        "grid_y": tile["target_grid_y"],
                        "z": tile["target_z"],
                        "alpha": 255
                    })
                    for k in ["start_x", "start_y", "target_x", "target_y", "target_grid_x", "target_grid_y", "target_z"]:
                        tile.pop(k, None)
                    new_board.append(tile)
                    new_positions[(tile["grid_x"], tile["grid_y"], tile["z"])] = tile

                ctx.animating_tiles = []
                ctx.board = new_board
                ctx.tile_positions = new_positions
                ctx.normalize_stacks()
                ctx.update_canvas()
                return

            progress = (ctx.animation_step + 1) / ctx.animation_steps
            for tile in ctx.animating_tiles:
                tile["x"] = tile["start_x"] + (tile["target_x"] - tile["start_x"]) * progress
                tile["y"] = tile["start_y"] + (tile["target_y"] - tile["start_y"]) * progress

            ctx.animation_step += 1
            ctx.update_canvas()
            QTimer.singleShot(interval, animate_step)

        animate_step()

