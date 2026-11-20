import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", type=Path, metavar="REPORT")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame
    from nthu_adventure.survival_game import Game
    if not args.smoke_test:
        Game().run()
        return
    report = args.smoke_test.resolve()
    game = Game(report.parent / "survival-smoke-save")
    game.begin(415)
    scenes = []
    for language in ("zh_TW", "en"):
        game.localizer.set_language(language)
        game.run_state.area = "campus"
        game.run_state.position = game.slots.start
        for scene in ("title", "profile", "intro", "incident", "map", "journal", "event_log", "pause", "settings"):
            game.scene = scene
            game.draw((0, 0))
            game.present()
            name = f"{language}-{scene}"
            pygame.image.save(game.screen, report.parent / f"{name}.png")
            scenes.append(name)
        game.scene = "play"
        campus_point = next(actor.position for actor in game.run_state.actors.values() if actor.infected)
        for area, point in [("campus", campus_point), *((key, room.entry) for key, room in game.rooms.items())]:
            game.run_state.area, game.run_state.position = area, point
            game.draw((0, 0))
            game.present()
            name = f"{language}-{area}"
            pygame.image.save(game.screen, report.parent / f"{name}.png")
            scenes.append(name)
    game.store.save(game.run_state)
    assert game.store.load().seed == 415
    report.write_text(json.dumps({"ok": True, "scenes": scenes}), encoding="utf-8")
    pygame.quit()


if __name__ == "__main__":
    main()
