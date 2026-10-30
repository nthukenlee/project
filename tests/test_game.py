import os
import tempfile
import unittest
from unittest.mock import patch
from collections import deque
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')

from nthu_adventure import content
from nthu_adventure.content import BUILDINGS,NPCS,QUESTS,DORMS,SPAWN_TILE,tile_center,validate_content
from nthu_adventure.constants import SAVE_VERSION,TILE,MAP_COLS,MAP_ROWS
from nthu_adventure.state import GameState,QuestSystem,migrate_save
from nthu_adventure.savegame import SaveManager
from nthu_adventure.localization import Localizer
from nthu_adventure.geometry import pixel_points

TEMP_ROOT=Path(__file__).resolve().parents[1]/'work'/'test-temp'
TEMP_ROOT.mkdir(parents=True,exist_ok=True)

class ContentTests(unittest.TestCase):
    def test_data_and_removed_pickups(self):
        self.assertEqual(validate_content(),[])
        self.assertEqual(len(BUILDINGS),34)
        self.assertEqual(len(QUESTS),8)
        for removed in ('COLLECTIBLES','RESOURCE_NODES','HIDDEN_ITEMS','RECIPES'):
            self.assertFalse(hasattr(content,removed),removed)
        self.assertTrue(all(q['kind'] in ('visit','talk','complete_quests') for q in QUESTS))

    def test_dorms_have_distinct_official_references(self):
        self.assertEqual(set(DORMS),{'ren_hall','shi_hall','li_hall','yi_hall','xin_hall'})
        self.assertEqual(len({d['source'] for d in DORMS.values()}),5)
        self.assertTrue(all(d['source'].startswith('https://sthousing.site.nthu.edu.tw/') for d in DORMS.values()))
        self.assertIn('疊層半圓玻璃窗帶',DORMS['yi_hall']['features'])
        self.assertIn('圓弧樓梯塔',DORMS['ren_hall']['features'])

    def test_every_modeled_building_has_its_own_referenced_facade(self):
        registry=content.ARCHITECTURE
        self.assertEqual({b['id'] for b in BUILDINGS},set(registry)|set(DORMS))
        self.assertNotIn('electrical',{b['id'] for b in BUILDINGS})
        self.assertEqual(registry['general_4']['marker_id'],'62')
        self.assertEqual(registry['education']['marker_id'],'28')
        self.assertEqual(len({(s.get('art'),tuple(s.get('crop',[])),s.get('renderer')) for s in registry.values()}),len(registry))
        for spec in registry.values():
            self.assertTrue(spec['source'].startswith('https://'))
            self.assertTrue(spec['description_zh'] and spec['description_en'])

    def test_languages_match(self):
        l=Localizer()
        self.assertEqual(l.missing_keys(),{'zh_TW':set(),'en':set()})
        self.assertNotIn('拾光',l.t('dialog.librarian'))
        l.set_language('en')
        self.assertEqual(l.t('v5.tool.camera'),'Camera')

    def test_reference_landmark_relationships_and_labels(self):
        # Relationships visible on NTHU's published campus road plan.
        buildings={b['id']:b['rect'] for b in BUILDINGS}
        self.assertGreater(SPAWN_TILE[0],content.LAKE_ENTRANCE_TILE[0])
        self.assertLess(SPAWN_TILE[1],content.LAKE_ENTRANCE_TILE[1])
        self.assertLess(buildings['main_library'].y,content.LAKE_ENTRANCE_TILE[1])
        self.assertLess(buildings['xin_hall'].x,buildings['ren_hall'].x)
        self.assertGreater(buildings['xin_hall'].y,content.LAKE_ENTRANCE_TILE[1])
        self.assertLess(buildings['humanities_building'].x,buildings['xin_hall'].x)
        localizer=Localizer()
        for language in localizer.supported:
            localizer.set_language(language)
            for feature in content.ROADS+content.WALKWAYS+content.LAKE_POINTS+BUILDINGS:
                self.assertFalse(localizer.t(feature['label']).startswith('['),feature['label'])
            for feature in content.LAKE_POINTS:
                self.assertFalse(localizer.t('lake.note.'+feature['id']).startswith('['))

class StateTests(unittest.TestCase):
    def test_old_inventory_is_removed_without_losing_profile_or_quests(self):
        old=GameState().to_dict()
        old.update(version=1,collected=['memory_01'],resources={'flower':999},crafted=['campus_lantern'],gathered_nodes=['resource_01'],hidden_items=['lake_pearl'],decorations={'ren_hall':[]},area='courtyard',inventory_selected=7)
        old['profile']['name']='測試玩家'
        old['quest_states']['welcome']['status']='completed'
        loaded=GameState.from_dict(old)
        self.assertEqual(loaded.player_name,'測試玩家')
        self.assertEqual(loaded.quest_states['welcome']['status'],'completed')
        self.assertEqual(loaded.inventory_selected,0)
        for removed in ('collected','resources','crafted','gathered_nodes','hidden_items','decorations','area'):
            self.assertNotIn(removed,loaded.to_dict())
            self.assertFalse(hasattr(loaded,removed))

    def test_all_quests_finish_through_visits_and_conversations(self):
        state=GameState(); quests=QuestSystem(state)
        for npc in NPCS: quests.activate_from_npc(npc['id']); quests.record_talk(npc['id'])
        for zone in content.ZONES: quests.record_visit(zone['id'])
        quests.refresh()
        self.assertTrue(all(value['status']=='completed' for value in state.quest_states.values()))
        self.assertEqual(quests.completion_percent(),100)

    def test_legacy_flat_save_and_newer_version(self):
        old=migrate_save({'player_x':800,'player_y':900})
        self.assertEqual(old['version'],SAVE_VERSION)
        self.assertEqual(old['player']['x'],tile_center(SPAWN_TILE)[0])
        self.assertEqual(old['player']['y'],tile_center(SPAWN_TILE)[1])
        with self.assertRaises(ValueError): migrate_save({'version':999})

    def test_save_roundtrip_and_corrupt_backup(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            manager=SaveManager(Path(directory)); state=GameState()
            state.player_name='清華'; state.photos={'ren_hall'}; state.observations={'ren_hall:desk'}
            state.visited_zones={'dorms'}; state.appearance['hair_style']=2
            manager.save(state,1); loaded=manager.load(1)
            self.assertEqual(loaded.to_dict(),state.to_dict())
            manager.path_for(2).write_text('{broken',encoding='utf-8')
            self.assertIsNone(manager.load(2))
            self.assertTrue(list(Path(directory).glob('slot_2.corrupt-*.json')))

    def test_v5_save_repositions_player_and_keeps_trip_progress(self):
        old=GameState().to_dict()
        old.update(version=2,map_revision='old-layout',photos=['ren_hall'],observations=['yi_hall:desk'],visited_zones=['library'])
        old['profile']['name']='回校同學'
        old['player']={'x':3200,'y':2400,'facing':'left'}
        state=GameState.from_dict(old)
        self.assertEqual((state.player_x,state.player_y),tile_center(SPAWN_TILE))
        self.assertEqual(state.player_name,'回校同學')
        self.assertEqual(state.photos,{'ren_hall'})
        self.assertEqual(state.observations,{'yi_hall:desk'})
        self.assertEqual(state.visited_zones,{'library'})

    def test_windows_temporary_file_lock_and_preserved_previous_save(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            manager=SaveManager(Path(directory)); state=GameState()
            state.player_name='原本'; manager.save(state)
            original_replace=Path.replace; attempts=[]
            def transient_lock(source,target):
                attempts.append(1)
                if len(attempts)<3: raise PermissionError('temporary Windows lock')
                return original_replace(source,target)
            state.player_name='更新'
            with patch.object(Path,'replace',transient_lock),patch('nthu_adventure.savegame.time.sleep'):
                manager.save(state)
            self.assertEqual(manager.load().player_name,'更新')
            state.player_name='未儲存'
            with patch.object(Path,'replace',side_effect=PermissionError('persistent lock')),patch('nthu_adventure.savegame.time.sleep'):
                with self.assertRaises(PermissionError): manager.save(state)
            self.assertEqual(manager.load().player_name,'更新')

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        from nthu_adventure.app import Game
        cls.directory=tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        cls.game=Game(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls):
        import pygame
        pygame.quit(); cls.directory.cleanup()

    def test_native_2d_scenes_and_no_pickup_callbacks(self):
        g=self.game
        for removed in ('_check_collectibles','_check_hidden_items','_craft_item','_courtyard_tool'):
            self.assertFalse(hasattr(g,removed))
        for language in ('zh_TW','en'):
            g.localizer.set_language(language)
            for scene in ('title','explore','map','notebook','guide','settings','customize','pause','save_menu'):
                g.scene=scene; g._draw((0,0))
                self.assertEqual(g.canvas.get_size(),(1280,720))
        g.localizer.set_language('zh_TW')

    def test_education_and_general4_interiors_have_distinct_reading_actions(self):
        import pygame
        g=self.game
        for language in ('zh_TW','en'):
            g.localizer.set_language(language)
            for key,kind in (('education','seminar'),('general_4','postal')):
                g._travel(key); g._interact()
                self.assertEqual(g.scene,'interior')
                self.assertEqual(g.current_interior['id'],key)
                g.state.hunger=42;g.state.supplies['snack']=0
                g.room_position=pygame.Vector2(.32,.45);g._interact_interior()
                self.assertIn(key+':'+kind,g.state.observations)
                self.assertEqual(g.state.hunger,42)
                self.assertEqual(g.state.supplies['snack'],0)
                self.assertEqual(g.notification,g.t('v5.observe.'+kind))
                self.assertFalse(g.notification.startswith('['))
                g._draw((0,0));g._button_action('leave')
        g.localizer.set_language('zh_TW')

    def test_new_scenery_and_all_paged_destinations_are_accessible(self):
        g=self.game
        for point in content.SCENERY_POINTS:
            g._button_action('landscape:'+point['id'])
            self.assertFalse(g.world.collides(g._player_rect()),point['id'])
            g._interact()
            self.assertIn('campus:'+point['id'],g.state.observations)
        for language in ('zh_TW','en'):
            g.localizer.set_language(language);g.map_list_page=0
            seen=set()
            for _ in range(6):
                g.scene='map';g._draw((0,0))
                seen.update(b.action for b in g.buttons if b.action.startswith('travel:'))
                g._button_action('map_page:1')
            self.assertTrue({'travel:'+b['id'] for b in BUILDINGS}<=seen)
            keys=list(content.ARCHITECTURE)+list(DORMS)
            for i,key in enumerate(keys):
                g.architecture_page=i//5;g.selected_dorm=key;g.scene='guide';g._draw((0,0))
                self.assertFalse(g.t('landmark.'+key).startswith('['),key)
                self.assertIn('dorm:'+key,{b.action for b in g.buttons})
                self.assertGreater(g.world.facades[key].get_width(),50)
            g._button_action('architecture_page:1')
            self.assertEqual(g.architecture_page,0)
        g.localizer.set_language('zh_TW');g.architecture_page=0;g.selected_dorm='education';g.map_list_page=0

    def test_all_npcs_and_doors_reachable(self):
        import pygame
        world=self.game.world
        def open_tile(tile):
            x,y=tile_center(tile)
            return not world.collides(pygame.Rect(x-8,y-6,16,13))
        reachable={SPAWN_TILE}; frontier=deque([SPAWN_TILE])
        while frontier:
            x,y=frontier.popleft()
            for point in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if 0<=point[0]<MAP_COLS and 0<=point[1]<MAP_ROWS and point not in reachable and open_tile(point):
                    reachable.add(point); frontier.append(point)
        for npc in NPCS: self.assertTrue(tuple(npc['tile']) in reachable,npc['id'])
        for building in BUILDINGS:
            door=world.door(building)
            self.assertTrue(any(pygame.Vector2(tile_center(tile)).distance_to(door)<60 for tile in reachable),building['id'])

    def test_dorm_entry_read_rest_and_exit_without_items(self):
        import pygame
        g=self.game
        for key in DORMS:
            g._travel(key)
            door=g.world.door(next(b for b in BUILDINGS if b['id']==key))
            g.state.player_x,g.state.player_y=door
            g._interact()
            self.assertEqual(g.scene,'interior')
            self.assertEqual(g.current_interior['id'],key)
            g.room_position=pygame.Vector2(.35,.66); g._interact_interior()
            self.assertIn(key+':desk',g.state.observations)
            g.state.energy=10; g.room_position=pygame.Vector2(.35,.39); g._interact_interior()
            self.assertEqual(g.state.energy,100)
            g._draw((0,0)); g._button_action('leave')
            self.assertEqual(g.scene,'explore')

    def test_old_pickup_location_does_not_create_items(self):
        g=self.game
        g.state=GameState(); g.quests=QuestSystem(g.state)
        g.state.player_x,g.state.player_y=tile_center((22,105))
        g._update_explore(.01)
        self.assertFalse(hasattr(g.state,'collected'))
        self.assertNotIn('collected',g.state.to_dict())

    def test_every_road_shore_walk_and_entrance_is_unblocked(self):
        g=self.game
        for spec,points in g.world.paths:
            for a,b in zip(points,points[1:]):
                steps=max(1,round(a.distance_to(b)/6))
                for index in range(steps+1):
                    p=a.lerp(b,index/steps)
                    self.assertFalse(g.world.collides(g._player_rect(p.x,p.y)),f"{spec.get('id','entrance')} at {p/TILE}")

    def test_bridges_and_entire_lake_loop_can_be_walked_both_ways(self):
        g=self.game; saved=g.state
        try:
            g.state=GameState()
            for spec in content.WALKWAYS:
                for points in (pixel_points(spec['points']),list(reversed(pixel_points(spec['points'])))):
                    g.state.player_x,g.state.player_y=points[0]
                    for target in points[1:]:
                        g._move(target.x-g.state.player_x,target.y-g.state.player_y)
                        self.assertLess(abs(g.state.player_x-target.x)+abs(g.state.player_y-target.y),2,spec['id'])
        finally: g.state=saved

    def test_lake_collision_follows_shore_and_all_observation_spots_work(self):
        import pygame
        g=self.game
        self.assertTrue(g.world.collides(g._player_rect(120*TILE,89*TILE)))
        # This land indentation lies inside the lake's bounding rectangle.
        self.assertFalse(g.world.collides(g._player_rect(100*TILE,92*TILE)))
        for point in content.LAKE_POINTS:
            p=pygame.Vector2(point['tile'])*TILE
            g.state.player_x,g.state.player_y=p
            self.assertFalse(g.world.collides(g._player_rect()),point['id'])
            g.scene='explore'; g._interact()
            self.assertIn('lake:'+point['id'],g.state.observations)

    def test_map_zoom_pan_and_xin_marker_travel(self):
        import pygame
        g=self.game
        for language in ('zh_TW','en'):
            g.localizer.set_language(language)
            for zoom in (1,2.5,5):
                g.map_zoom=zoom; g.map_center=pygame.Vector2(107*TILE,115*TILE)
                g.scene='map';g._draw((0,0))
                target=g.world.door(next(b for b in BUILDINGS if b['id']=='xin_hall'))
                marker=pygame.Vector2(g.map_rect.topleft)+(target-pygame.Vector2(g.map_camera.topleft))*g.map_scale
                g._map_click(marker)
                self.assertEqual(g.scene,'explore')
                self.assertLess(pygame.Vector2(g.state.player_x,g.state.player_y).distance_to(target),40)
        g._button_action('map_reset');g.localizer.set_language('zh_TW')

if __name__=='__main__': unittest.main()
