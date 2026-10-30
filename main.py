import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", type=Path, metavar="REPORT")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    from nthu_adventure.app import Game
    if not args.smoke_test:
        Game().run()
        return
    import pygame
    report = args.smoke_test.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    game = Game(report.parent / "packaged-smoke-save")
    scenes = []
    for language in ("zh_TW", "en"):
        game.localizer.set_language(language)
        for scene in ("title", "explore", "map", "notebook", "guide", "interior"):
            game.scene = scene
            if scene == "interior":
                from nthu_adventure.content import BUILDINGS
                game.current_interior = next(item for item in BUILDINGS if item["id"] == "main_library")
                game.room_position = pygame.Vector2(.5, .8)
            game._draw((0, 0))
            game._present()
            pygame.image.save(game.screen, report.parent / f"packaged-{language}-{scene}.png")
            scenes.append(f"{language}:{scene}")
        from nthu_adventure.content import DORMS,ISLANDS
        for building_id in DORMS:
            game._travel(building_id)
            game._draw((0, 0)); game._present()
            pygame.image.save(game.screen, report.parent / f"packaged-{language}-{building_id}.png")
            scenes.append(f"{language}:{building_id}")
        game._button_action('lake')
        game._draw((0,0));game._present()
        pygame.image.save(game.screen,report.parent/f'packaged-{language}-success-lake.png')
        scenes.append(f'{language}:success-lake')
        island=ISLANDS[0]
        game.state.player_x,game.state.player_y=pygame.Vector2(island['center'])*32
        game._draw((0,0));game._present()
        pygame.image.save(game.screen,report.parent/f'packaged-{language}-lake-island.png')
        scenes.append(f'{language}:lake-island')
        game.map_zoom=2.8;game.map_center=pygame.Vector2(105,83)*32;game.scene='map'
        game._draw((0,0));game._present()
        pygame.image.save(game.screen,report.parent/f'packaged-{language}-map-detail.png')
        scenes.append(f'{language}:map-detail')
        game._travel('xin_hall');game._interact()
        assert game.current_interior['id']=='xin_hall'
        game._draw((0,0));game._present()
        pygame.image.save(game.screen,report.parent/f'packaged-{language}-xin-interior.png')
        scenes.append(f'{language}:xin-interior')
        game._leave_special_area();game._button_action('map_reset')
        for building_id in ('education','general_4','main_library','engineering_1'):
            game._travel(building_id)
            game._draw((0,0));game._present()
            pygame.image.save(game.screen,report.parent/f'packaged-{language}-{building_id}.png')
            scenes.append(f'{language}:{building_id}')
            if building_id in ('education','general_4'):
                game._interact()
                assert game.current_interior['id']==building_id
                game.room_position=pygame.Vector2(.32,.45);game._interact_interior()
                game._draw((0,0));game._present()
                pygame.image.save(game.screen,report.parent/f'packaged-{language}-{building_id}-interior.png')
                scenes.append(f'{language}:{building_id}-interior')
                game._leave_special_area()
        from nthu_adventure.content import SCENERY_POINTS,ARCHITECTURE
        for point in SCENERY_POINTS:
            game._button_action('landscape:'+point['id'])
            game._interact();game._draw((0,0));game._present()
            pygame.image.save(game.screen,report.parent/f'packaged-{language}-{point["id"]}.png')
            scenes.append(f'{language}:{point["id"]}')
        keys=list(ARCHITECTURE)+list(DORMS)
        for page in range((len(keys)+4)//5):
            game.architecture_page=page;game.selected_dorm=keys[page*5];game.scene='guide'
            game._draw((0,0));game._present()
            pygame.image.save(game.screen,report.parent/f'packaged-{language}-architecture-{page+1}.png')
            scenes.append(f'{language}:architecture-{page+1}')
        game.map_zoom=3.8;game.map_center=pygame.Vector2(119,52)*32;game.scene='map';game.map_list_page=0
        game._draw((0,0));game._present()
        pygame.image.save(game.screen,report.parent/f'packaged-{language}-north-map.png')
        scenes.append(f'{language}:north-map')
        game.architecture_page=0;game.selected_dorm='education';game._button_action('map_reset')
    game.save_manager.save(game.state, "auto")
    assert game.save_manager.load("auto") is not None
    report.write_text(json.dumps({"ok": True, "scenes": scenes, "resolution": list(game.screen.get_size()), "buildings":len(BUILDINGS),"referenced_facades":len(game.world.facades)}, indent=2), encoding="utf-8")
    pygame.quit()


if __name__ == "__main__":
    main()
