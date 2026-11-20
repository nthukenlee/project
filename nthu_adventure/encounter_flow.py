"""Connect randomly cast incidents to character, resource, and route state."""
from pygame import Vector2

from .expedition import EVENTS, MINUTE_SECONDS, OUTDOOR_POINTS
from .survival import Actor, distance


CHOICES = {
    "investigate": "approach", "verify": "approach", "information": "ask",
    "trade": "exchange", "share": "offer_water", "shelter": "offer_water",
    "wait": "wait_here", "route": "take_route", "light": "lend_light",
    "storm": "wait_here", "invite": "invite", "custody": "entrust",
    "recover": "recover", "warning": "warn", "divert": "divert",
    "barricade": "barricade", "escort": "escort",
}
LINES = {
    "helpful": "cooperate", "guarded": "bargain", "panicked": "plead",
    "selfish": "bargain", "mimic": "plead",
}


class EncounterFlow:
    def __init__(self, game):
        self.game = game
        self.outdoors = {key: game.slots.near(Vector2(tile) * 32) for key, tile in OUTDOOR_POINTS.items()}

    def locations(self):
        state = self.game.run_state
        if state.area == "campus":
            for key, event in state.encounters.items():
                if key in self.outdoors:
                    yield key, event, self.outdoors[key]
        elif state.area in state.encounters:
            yield state.area, state.encounters[state.area], self.game.rooms[state.area].event_point

    def sync(self):
        state = self.game.run_state
        for _, event, point in self.locations():
            if not event.available(state) or distance(point, state.position) > 480:
                continue
            if event.actor_id not in state.actors:
                state.actors[event.actor_id] = Actor(
                    event.role, point, state.area, status="disguised" if event.motive == "mimic" else "waiting",
                    identity=event.person,
                )
            if event.event == "stormfront" and not event.clock and distance(point, state.position) <= 84:
                state.storm_until = max(state.storm_until, state.elapsed + 45)
                event.clock = state.minute
                self.game.notify("exp.rain_arrived")

    def targets(self):
        state = self.game.run_state
        for key, event, point in self.locations():
            actor = state.actors.get(event.actor_id)
            if event.available(state) and (actor is None or actor.status in ("waiting", "disguised")):
                yield "encounter", key, point

    def encounter_for_actor(self, actor_id):
        return next((event for event in self.game.run_state.encounters.values() if event.actor_id == actor_id), None)

    def line(self, event):
        state = self.game.run_state
        if event.motive == "mimic" and state.heard_event:
            return state.heard_event
        return LINES[event.motive] + "." + str(event.person % 2)

    def title(self, event):
        return f"encounter.{event.event}.title"

    def open(self, key):
        game = self.game
        state = game.run_state
        event = state.encounters[key]
        if not event.available(state):
            return
        self.sync()
        if not event.clock:
            event.clock = state.minute
        if event.status == "unseen":
            event.status = "heard"
        if event.activity == "storm":
            state.storm_until = max(state.storm_until, state.elapsed + 45)
        line = self.line(event)
        if event.motive != "mimic":
            state.heard_event, state.heard_voice = line, event.voice
        game.show(self.title(event), f"encounter.{event.event}.text", self.options(key, event),
                  speaker=event.name(game.localizer.language),
                  quote="exp.voice." + line if event.motive == "mimic" else None)

    @staticmethod
    def options(key, event):
        verbs = ("food", "water") if event.activity == "kit" else (CHOICES[event.activity],)
        actions = [verb + "/" + key for verb in verbs]
        if event.status != "checked":
            actions.insert(0, "check/" + key)
        actions.append("leave/" + key)
        return tuple("event_" + action for action in actions)

    def inspect(self, key, event, person):
        game = self.game
        event.status = "checked"
        detail = event.motive if event.motive in ("mimic", "selfish") else event.activity
        game.show(self.title(event), "exp.inspect." + detail, self.options(key, event),
                  speaker=event.name(game.localizer.language))
        if person and event.motive == "mimic":
            person.facing = "left" if event.person % 2 else "right"

    def resolve(self, action, key):
        game = self.game
        state = game.run_state
        event = state.encounters[key]
        person = state.actors.get(event.actor_id)
        game.scene = "play"
        if not event.available(state) or person is None or person.status not in ("waiting", "disguised"):
            return
        if action == "check":
            self.inspect(key, event, person)
            return
        if action == "leave":
            return
        if event.motive == "mimic":
            if event.status == "checked":
                # The actor is exposed, but the player still has time to move.
                person.linger, person.cooldown = 2.2, 1.45
            else:
                person.linger, person.cooldown = .6, .75
            person.status, person.kind, person.alerted = "turned", "mimic", 6
            game.cue_scare("mimic")
            self.finish(event, "lure", quote="exp.voice." + self.line(event))
            return
        result = self.apply(action, key, event, person)
        if result:
            self.finish(event, result)

    def result_key(self, event):
        specific = f"encounter.{event.event}.{event.outcome}"
        catalog = self.game.localizer.catalogs[self.game.localizer.language]
        return specific if "survival." + specific in catalog else "exp.result." + event.outcome

    def finish(self, event, outcome, *, quote=None):
        game = self.game
        event.status, event.outcome = "resolved", outcome
        game.show(self.title(event), self.result_key(event),
                  speaker=event.name(game.localizer.language), quote=quote)

    def apply(self, action, key, event, person):
        game = self.game
        state = game.run_state
        pack = state.pack
        selfish = event.motive == "selfish" and event.status != "checked"
        if action in ("food", "water"):
            state.add_gear(action)
            return "kit_" + action
        if action == "barricade":
            state.latched[state.area] = state.elapsed + (50 if event.status == "checked" else 29)
            return "barred"
        if action == "divert":
            state.lure_area = state.area
            state.lure_point = person.position
            state.lure_until = state.elapsed + (18 if event.status == "checked" else 10)
            game.sound("call")
            return "divert"
        if action == "escort":
            if len(state.team) >= 2:
                game.notify("event.team_full")
                return None
            person.status, person.choice = "joined", "escort"
            return "escort"
        if action == "recover":
            if event.status != "checked":
                state.elapsed += MINUTE_SECONDS
                state.thirst = max(1, state.thirst - 3)
            if selfish:
                person.status = "gone"
                return "recover_taken"
            state.add_gear(EVENTS[event.event]["reward"])
            return "recover"
        if action == "warn":
            if event.status == "checked":
                state.add_gear("water")
                return "warning_quiet"
            listeners = [
                enemy for enemy in state.actors.values()
                if enemy.infected and enemy.status not in ("dormant", "gone") and enemy.area == state.area
                and distance(enemy.position, person.position) <= 275
            ]
            for enemy in listeners:
                enemy.alerted = max(enemy.alerted, 6)
            return "warning_loud" if listeners else "warning_unanswered"
        if action == "exchange":
            given, reward = ("food", "water") if event.event == "last_water" else ("water", "cell")
            if not pack[given]:
                game.notify("exp.missing", item=game.tr("gear." + given))
                return None
            pack[given] -= 1
            if selfish:
                person.status = "gone"
                return "taken"
            state.add_gear(reward)
            return "exchange_water" if reward == "water" else "exchange_cell"
        if action == "lend_light":
            if not pack["lamp"] or state.battery < 12:
                game.notify("exp.need_light")
                return None
            state.battery -= 12
            state.lamp_on = state.lamp_on and state.battery > 0
            if selfish:
                person.status = "gone"
                return "left_with_light"
            state.add_gear("cell")
            return "light"
        if action == "offer_water":
            if not pack["water"]:
                game.notify("event.no_water")
                return None
            pack["water"] -= 1
            if event.activity == "shelter" and len(state.team) < 2 and not selfish:
                person.status, person.choice = "joined", "join"
                return "shelter"
            if not selfish:
                state.add_gear("food")
                return "share"
            return "taken"
        if action == "wait_here":
            state.elapsed += 2 * MINUTE_SECONDS
            state.hunger = max(1, state.hunger - 3)
            state.thirst = max(1, state.thirst - 4)
            if event.activity == "storm":
                state.storm_until = state.elapsed
                return "storm"
            if event.motive == "panicked":
                person.status = "gone"
                return "wait_empty"
            state.add_gear("water")
            return "wait_help"
        if action == "take_route":
            if key in game.slots.side_exits and key not in state.shortcuts:
                state.shortcuts.append(key)
                return "route"
            return "information"
        if action in ("invite", "entrust"):
            if len(state.team) >= 2:
                game.notify("event.team_full")
                return None
            if action == "entrust":
                if not pack["water"]:
                    game.notify("event.no_water")
                    return None
                pack["water"] -= 1
                person.carried = event.motive == "selfish"
            person.status, person.choice = "joined", "trust" if action == "entrust" else "join"
            return "custody" if action == "entrust" else "joined"
        if action == "approach" and event.motive == "panicked":
            state.elapsed += MINUTE_SECONDS
            return "panicked"
        return "information"
