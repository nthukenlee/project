from collections import deque
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from nthu_adventure.app import Game
from nthu_adventure.constants import MAP_COLS, MAP_ROWS
from nthu_adventure.content import tile_center
from nthu_adventure.state import GameState
from nthu_adventure.zombie_story import (
    ATTACK_RADIUS, DETECT_RADIUS, FINISHED, LOGBOOK, OBJECTIVES, SHELTER, SPAWNS,
    Zombie, body_at,
)


class ZombieStoryTests(unittest.TestCase):
    def test_detection_windup_dodge_hit_and_return(self):
        home = pygame.Vector2(300, 300)
        enemy = Zombie(home)
        def open_ground(_):
            return False

        enemy.step(home + (DETECT_RADIUS + 1, 0), .05, open_ground)
        self.assertFalse(enemy.chasing)
        enemy.step(home + (100, 0), .05, open_ground)
        self.assertTrue(enemy.chasing)
        self.assertGreater(enemy.position.x, home.x)
        close = enemy.position + (ATTACK_RADIUS - 5, 0)
        self.assertFalse(enemy.step(close, .05, open_ground))
        self.assertGreater(enemy.windup, 0)
        out_of_reach = enemy.position + (ATTACK_RADIUS + 5, 0)
        for _ in range(12):
            self.assertFalse(enemy.step(out_of_reach, .05, open_ground))
        for _ in range(35):
            if enemy.step(enemy.position + (30, 0), .05, open_ground):
                break
        else:
            self.fail("A player standing close should take a hit")
        enemy.step(home + (400, 0), .05, open_ground)
        self.assertFalse(enemy.chasing)

    def test_wall_blocks_detection_and_attack(self):
        enemy = Zombie(pygame.Vector2(100, 100))
        player = pygame.Vector2(136, 100)
        wall = pygame.Rect(116, 70, 4, 60)
        enemy.step(player, .05, wall.colliderect)
        self.assertFalse(enemy.chasing)
        enemy.chasing = True
        enemy.windup = .01
        self.assertFalse(enemy.step(player, .05, wall.colliderect))

    def test_playable_chapter_and_saved_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Game(Path(directory))
            self.addCleanup(pygame.quit)
            self.assertEqual(GameState.from_dict({"version": 4}).health, 100)
            self.assertEqual(GameState.from_dict({"version": 4}).zombie_stage, 0)
            required = {stop.tile for stop in OBJECTIVES} | set(SPAWNS)
            visited = {SHELTER.tile}
            frontier = deque(visited)
            while frontier and not required <= visited:
                x, y = frontier.popleft()
                for tile in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    a,b=tile
                    if (
                        tile not in visited and 0<=a<MAP_COLS and 0<=b<MAP_ROWS
                        and not game.world.collides(body_at(pygame.Vector2(tile_center(tile))))
                    ):
                        visited.add(tile)
                        frontier.append(tile)
            self.assertEqual(required - visited, set())
            game._button_action("zombie_chapter")
            self.assertEqual(game.state.zombie_stage,1)
            self.assertEqual(game.scene,"dialog")
            game.scene="explore"
            game.state.player_x,game.state.player_y=LOGBOOK.position
            game._interact()
            self.assertEqual(game.state.zombie_stage,2)
            game.scene="explore"
            enemy=game.zombies.enemies[0]
            game.state.player_x,game.state.player_y=enemy.position
            game.state.health=20
            for _ in range(20):
                game._update_explore(.05)
                if game.state.health==100:
                    break
            self.assertEqual((game.state.player_x,game.state.player_y),tuple(SHELTER.position))
            self.assertEqual(game.state.health,100)
            self.assertEqual(game.save_manager.load("auto").zombie_stage,2)
            for stage in (2,3):
                game.scene="explore"
                game.state.player_x,game.state.player_y=OBJECTIVES[stage].position
                game._interact()
                self.assertEqual(game.state.zombie_stage,stage+1)
                for language in ("zh_TW","en"):
                    game.localizer.set_language(language)
                    game._draw((0,0))
                    for scene in ("map","notebook"):
                        game.scene=scene
                        game._draw((0,0))
            self.assertEqual(game.save_manager.load("auto").zombie_stage,FINISHED)
