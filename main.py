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
        for building_id in ("ren_hall", "shi_hall", "li_hall", "yi_hall"):
            game._travel(building_id)
            game._draw((0, 0)); game._present()
            pygame.image.save(game.screen, report.parent / f"packaged-{language}-{building_id}.png")
            scenes.append(f"{language}:{building_id}")
    game.save_manager.save(game.state, "auto")
    assert game.save_manager.load("auto") is not None
    report.write_text(json.dumps({"ok": True, "scenes": scenes, "resolution": list(game.screen.get_size())}, indent=2), encoding="utf-8")
    pygame.quit()


if __name__ == "__main__":
    main()
