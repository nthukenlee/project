"""Campus adventure progression, placed against the existing game map."""
from dataclasses import dataclass

import pygame

from .constants import TILE, WINDOW_SIZE
from .content import BUILDINGS, LAKE_POINTS, SCENERY_POINTS, SPAWN_TILE, tile_center
from .ui import GREEN, INK, PAPER, panel
from .zombie_story import LOGBOOK, RELAY, SHELTER, Zombie


@dataclass(frozen=True)
class Stop:
    key: str
    tile: tuple[float, float] | None = None
    building: str | None = None
    fixture: str | None = None

    def position(self, world):
        if self.building:
            building = next(b for b in BUILDINGS if b['id'] == self.building)
            return world.door(building)
        return pygame.Vector2(self.tile) * TILE


def landmark_tile(points, name):
    return tuple(next(point['tile'] for point in points if point['id'] == name))


def stop_at_center(key, tile):
    x, y = tile
    return Stop(key, (x + .5, y + .5))


STOPS = (
    Stop('lawn', landmark_tile(SCENERY_POINTS, 'big_lawn')),
    Stop('education', building='education', fixture='notice'),
    Stop('library', building='main_library', fixture='archive'),
    stop_at_center('station', SHELTER.tile),
    stop_at_center('log', LOGBOOK.tile),
    stop_at_center('beacon', RELAY.tile),
    stop_at_center('report', SHELTER.tile),
    Stop('xin', building='xin_hall', fixture='desk'),
)
SIDE_STOPS = (STOPS[0], Stop('garden', landmark_tile(LAKE_POINTS, 'garden_1970')))
SIDE_KEYS = ('student', 'garden')
STOP_INDEX = {stop.key: index for index, stop in enumerate(STOPS)}
ENDING_ID = 'dawn_reunion'
INTRO_SHOTS = (
    ('gate', (140, 39), (134, 46), 12),
    ('lawn', (125, 55), (120, 58), 13),
    ('lake', (96, 84), (103, 91), 17),
)
INTRO_DURATION = sum(shot[3] for shot in INTRO_SHOTS)
PATTERNS = ('reverse', 'steady', 'three_short')


class CampusAdventure:
    def __init__(self, game):
        self.game = game
        self.reset_view()

    def reset_view(self):
        self.intro_time = 0.0
        self.last_shot = None
        self.card_key = ''
        self.card_return = 'explore'
        self.answer_feedback = False
        self.suspended = False
        self.intro_zombie = Zombie(LOGBOOK.position, facing='left', moving=True)

    @property
    def state(self):
        return self.game.state

    @property
    def current(self):
        if not self.suspended and self.state.adventure_step in STOP_INDEX:
            return STOPS[STOP_INDEX[self.state.adventure_step]]
        return None

    @property
    def lake_danger(self):
        return self.current is not None and self.current.key in ('log', 'beacon', 'report')

    @property
    def enemies_active(self):
        if self.current:
            return self.lake_danger
        return self.state.zombie_stage > 0

    @property
    def journal_active(self):
        return not self.suspended and self.state.adventure_step not in ('inactive', 'intro')

    def start_or_resume(self):
        game = self.game
        game._continue_game()
        if self.state.adventure_step == 'inactive':
            self.state.adventure_step = 'intro'
            game.scene = 'adventure_intro'
            game.save_manager.save(self.state, 'auto')
        elif self.state.adventure_step == 'complete':
            self.open_card('ending', 'explore')

    def advance_intro(self, dt):
        self.intro_time = min(INTRO_DURATION, self.intro_time + dt)
        if self.intro_time >= INTRO_DURATION:
            self.finish_intro()

    def finish_intro(self):
        if self.state.adventure_step != 'intro':
            return
        game = self.game
        self.state.player_x, self.state.player_y = tile_center(SPAWN_TILE)
        self.state.time_minutes = 18 * 60
        game._ensure_walkable()
        game.riding_bike = False
        game.running_fast = False
        game.player_moving = False
        self.state.adventure_step = 'lawn'
        game.save_manager.save(self.state, 'auto')
        self.open_card('briefing', 'explore')

    def draw_intro(self, mouse):
        game = self.game
        elapsed = self.intro_time
        for key, start, end, duration in INTRO_SHOTS:
            if elapsed <= duration:
                break
            elapsed -= duration
        if key != self.last_shot:
            game.audio.play('voice' if key == 'lake' else 'select')
            self.last_shot = key
        progress = max(0, min(1, elapsed / duration))
        progress = progress * progress * (3 - 2 * progress)
        camera_position = pygame.Vector2(start).lerp(end, progress) * TILE
        camera = game.world.camera_for(*camera_position)
        actor_start, actor_end = ((95.1, 84.5), (96.1, 88.4)) if key == 'lake' else (start, end)
        actor = pygame.Vector2(actor_start).lerp(actor_end, min(1, progress * 1.15)) * TILE
        actor -= pygame.Vector2(camera.topleft)
        tick = round(self.intro_time * 1000)
        game.canvas.blit(game.world.ground, (0, 0), camera)
        for x, y, tree in game.world.trees:
            if camera.inflate(200, 200).collidepoint(x, y):
                game.canvas.blit(tree, (x-camera.x-tree.get_width()/2, y-camera.y-tree.get_height()+12))
        if key == 'lawn':
            sign = STOPS[0].position(game.world) - pygame.Vector2(camera.topleft)
            width = max(4, round(68 * min(1, abs(progress-.5)*12)))
            pygame.draw.line(game.canvas, (90, 75, 57), sign, sign - (0, 44), 6)
            board = pygame.Rect(0, 0, width, 34)
            board.midbottom = (round(sign.x), round(sign.y-25))
            pygame.draw.rect(game.canvas, (187, 175, 143) if progress < .5 else (234, 218, 178), board, border_radius=3)
            if width>30:
                pygame.draw.line(game.canvas, (132, 104, 67), board.midleft, board.midright, 2)
        if key == 'lake':
            danger = self.intro_zombie.home.lerp(SHELTER.position, min(.75, progress))
            game.world.characters.draw_zombie(game.canvas, danger-pygame.Vector2(camera.topleft), self.intro_zombie, tick)
        facing = 'down' if key == 'lake' else 'left'
        game.world.characters.draw(game.canvas, actor, facing, True, {'shirt': 4}, tick)
        wash = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        edge = min(1, elapsed / 1.1, max(0, duration-elapsed) / 1.1)
        wash.fill((16, 25, 32, round(max(55 * progress, 218 * (1-edge)))))
        game.canvas.blit(wash, (0, 0))
        if key == 'lake' and .4 < progress < .8 and (tick // 140) % 3:
            light = actor - (12, 29)
            pygame.draw.circle(game.canvas, (224, 207, 161), light, 9, 2)
            pygame.draw.circle(game.canvas, (247, 237, 193), light, 3)
        pygame.draw.rect(game.canvas, (22, 31, 29), (0, 0, 1280, 62))
        pygame.draw.rect(game.canvas, (22, 31, 29), (0, 548, 1280, 172))
        game.fonts.draw(game.canvas, game.t('adventure.intro.'+key+'.place'), (36, 21), 20, PAPER, True)
        for i, line in enumerate(game.fonts.wrapped(game.t('adventure.intro.'+key+'.text'), 24, 1060)):
            game.fonts.draw(game.canvas, line, (640, 572+i*32), 24, PAPER, False, 'midtop')
        game._button((1020, 644, 224, 42), game.t('adventure.skip'), 'adventure:skip', mouse)
        pygame.draw.rect(game.canvas, (166, 140, 96), (36, 686, round(920*self.intro_time/INTRO_DURATION), 3))

    def outdoor_stops(self):
        current = self.current
        if not current:
            return ()
        stops = []
        if not current.building:
            stops.append((current.key, current))
        if self.side_available('student'):
            stops.append(('student', SIDE_STOPS[0]))
        if self.side_available('garden'):
            stops.append(('garden', SIDE_STOPS[1]))
        return stops

    def side_available(self, key):
        if not self.current or key in self.state.adventure_sides:
            return False
        after = 'library' if key == 'student' else 'log'
        return STOP_INDEX[self.current.key] > STOP_INDEX[after]

    def interior_matches(self, building, fixture):
        current = self.current
        return current is not None and (current.building, current.fixture) == (building, fixture)

    def interact(self, key, return_to='explore'):
        if key in SIDE_KEYS:
            if self.side_available(key):
                self.state.adventure_sides.add(key)
                self.game.save_manager.save(self.state, 'auto')
                self.open_card(key, return_to)
            return
        if not self.current or self.current.key != key:
            return
        if key == 'beacon':
            self.open_card(key, return_to)
            return
        self.advance(key, return_to)

    def advance(self, key, return_to):
        game = self.game
        if key == 'xin':
            self.state.adventure_step = 'complete'
            self.state.adventure_ending = ENDING_ID
            self.state.day += 1
            self.state.time_minutes = 7 * 60
            game.audio.play('quest')
            self.open_card('ending', return_to)
        else:
            self.state.adventure_step = STOPS[STOP_INDEX[key]+1].key
            if key == 'station':
                self.state.time_minutes = 19 * 60
                game.zombies.reset()
            if key == 'report':
                self.state.health = 100
            game.audio.play('select')
            self.open_card('signal_sent' if key == 'beacon' else key, return_to)
        game.save_manager.save(self.state, 'auto')

    def open_card(self, key, return_to):
        self.card_key = key
        self.card_return = return_to
        self.answer_feedback = False
        self.game.scene = 'adventure_card'

    def close_card(self):
        self.game.scene = self.card_return

    def answer(self, pattern):
        if self.card_key != 'beacon' or self.state.adventure_step != 'beacon':
            return
        if pattern == 'three_short':
            self.advance('beacon', self.card_return)
        else:
            self.answer_feedback = True

    def beacon_on(self, tick):
        if self.state.adventure_step not in ('report', 'xin', 'complete') or self.suspended:
            return self.state.zombie_stage >= 3 and not self.current
        pulse = tick % 3600
        return any(start <= pulse < end for start, end in ((0, 200), (420, 620), (840, 1040), (1300, 2200)))

    def draw_card(self, mouse):
        game = self.game
        key = self.card_key
        game._dim()
        panel(game.canvas, (178, 125, 924, 470), (243, 240, 222), 252)
        game.fonts.draw(game.canvas, game.t('adventure.'+key+'.title'), (220, 161), 31, GREEN, True)
        for i, line in enumerate(game.fonts.wrapped(game.t('adventure.'+key+'.text'), 23, 834)):
            game.fonts.draw(game.canvas, line, (220, 226+i*34), 23, INK)
        if key == 'beacon':
            for i, pattern in enumerate(PATTERNS):
                label = f'{i+1}  '+game.t('adventure.pattern.'+pattern)
                game._button((220+i*282, 416, 264, 52), label, 'adventure:pattern:'+pattern, mouse)
            message = 'adventure.retry' if self.answer_feedback else 'adventure.beacon.tip'
            game.fonts.draw(game.canvas, game.t(message), (220, 495), 19, INK)
            game._button((852, 538, 208, 38), game.t('menu.back'), 'adventure:close', mouse)
        else:
            if key == 'ending':
                for i, side in enumerate(SIDE_KEYS):
                    if side in self.state.adventure_sides:
                        game.fonts.draw(game.canvas, game.t('adventure.ending.'+side), (220, 414+i*34), 19, GREEN)
            game._button((820, 510, 240, 49), game.t('adventure.proceed'), 'adventure:close', mouse, True, True)

    def draw_journal(self, mouse):
        game = self.game
        current = self.current
        game._dim()
        panel(game.canvas, (100, 43, 1080, 632), alpha=248)
        game.fonts.draw(game.canvas, game.t('adventure.title'), (142, 74), 33, GREEN, True)
        goal = 'adventure.goal.'+(current.key if current else 'complete')
        game.fonts.draw(game.canvas, game.t(goal), (144, 135), 23, INK, True)
        index = STOP_INDEX[current.key] if current else len(STOPS)
        clues = [('briefing', -1), ('lawn', 0), ('education', 1), ('library', 2), ('log', 4)]
        y = 199
        for key, threshold in clues:
            if index > threshold:
                for line in game.fonts.wrapped(game.t('adventure.clue.'+key), 21, 972):
                    game.fonts.draw(game.canvas, line, (144, y), 21, INK)
                    y += 26
                y += 9
        for side in SIDE_KEYS:
            if self.side_available(side) or side in self.state.adventure_sides:
                status = 'done' if side in self.state.adventure_sides else 'goal'
                game.fonts.draw(game.canvas, game.t(f'adventure.side.{side}.{status}'), (144, y), 19, GREEN, True)
                y += 33
        game._button((144, 605, 230, 40), game.t('panel.quests'), 'adventure:other_quests', mouse)
        game._button((914, 605, 220, 40), game.t('menu.back'), 'adventure:return', mouse, True, True)
