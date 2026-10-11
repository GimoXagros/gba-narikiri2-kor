"""Read-only natural-route audit for the fixed 8 MiB diagnostic ROM.

Each run records the exact ROM/core/save hashes, inputs, frame numbers and
screenshots. RAM writes are deliberately absent; this can establish observed
game routes, not reachability of every translated string or release fitness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from libretro_probe import Probe


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exercise(probe: Probe, route: str, replay_operations: Path | None = None) -> list[dict]:
    observations = []

    def frames(count: int, *buttons: str) -> None:
        probe.execute({"op": "frames", "count": count, "buttons": list(buttons)})

    def shot(label: str) -> None:
        result = probe.execute({"op": "screenshot", "name": label + ".png"})
        observations.append({"label": label, "frame": probe.frame,
                             "png_sha256": result["sha256"]})

    if route == "historical_battle_replay":
        if replay_operations is None:
            raise ValueError("The historical battle replay requires an operations log")
        source = [json.loads(line) for line in replay_operations.read_text(
            encoding="utf-8").splitlines()]
        if not source or source[0].get("op") != "initialize":
            raise ValueError("The source log has no initialization record")
        if source[0].get("ram_interventions") != 0:
            raise ValueError("The source route used a RAM intervention")
        for record in source[1:]:
            request = record.get("request", {})
            if request.get("op") == "frames":
                count = request["count"]
                buttons = request.get("buttons", [])
                if not isinstance(count, int) or count < 0 or count > 2000:
                    raise ValueError("Invalid source frame count")
                if not isinstance(buttons, list) or any(
                    key not in ("a", "b", "start", "select", "up", "down",
                                "left", "right", "l", "r") for key in buttons
                ):
                    raise ValueError("Invalid source buttons")
                probe.execute({"op": "frames", "count": count,
                               "buttons": buttons})
            elif request.get("op") == "screenshot":
                label = Path(request["name"]).stem
                shot(label)
                scene = probe.read_memory(0x02000E11, 1)[0]
                next_scene = probe.read_memory(0x02000E10, 1)[0]
                mode = probe.read_memory(0x02001CC8, 1)[0]
                ptr = int.from_bytes(probe.read_memory(0x0200400C, 4), "little")
                flags = None
                if 0x02000000 <= ptr < 0x0203FFDC:
                    flags = list(probe.read_memory(ptr + 0x19, 11))
                observations[-1].update({"scene": scene, "next_scene": next_scene,
                                         "mode_02001CC8": mode,
                                         "scene_object": hex(ptr),
                                         "object_bytes_19_through_23": flags})
            elif request.get("op") == "dump":
                continue
            else:
                raise ValueError("Unexpected historical operation")
            if probe.frame != record["frame"]:
                raise AssertionError("Source replay frame mismatch")
        return observations

    if route == "battle_natural":
        # Frozen 8 KiB suspend save from the v1.0 release audit. This starts
        # fresh from EEPROM and uses only game controls to reach the cave fight.
        if probe.input_save_hash != (
            "3dd036e865b0b1a038f1eb67afc37a549749687f80abdb1d1fdd2f4e850eee66"
        ):
            raise ValueError("battle_natural requires the frozen suspend input")
        for count, buttons in ((120, ()), (6, ("a",)), (600, ()),
                               (6, ("start",)), (180, ()), (6, ("a",)),
                               (240, ())):
            frames(count, *buttons)
        shot("00_resumed_cave")
        sequence = [("up", 70), ("left", 180), ("down", 80),
                    ("left", 80), ("down", 80)]
        sequence += [("left", 100), ("right", 100)] * 3
        sequence += [("select", 1), ("-", 90),
                     ("a", 1), ("-", 90), ("a", 1), ("-", 90)]
        for index, (button, count) in enumerate(sequence):
            frames(count, *(() if button == "-" else (button,)))
            shot(f"{index + 1:02}_{button}_{count}")
            observations[-1]["scene"] = probe.read_memory(0x02000E11, 1)[0]
        if observations[11]["scene"] != 5 or observations[-1]["scene"] != 5:
            raise AssertionError("The expected natural battle was not reached")
        actor_ptr = int.from_bytes(probe.read_memory(0x02003FF8, 4), "little")
        if not 0x02000000 <= actor_ptr <= 0x0203FF4C:
            raise AssertionError("Battle actor pointer left work RAM")
        actor_records = probe.read_memory(actor_ptr, 180)
        observations[-1].update({"actor_ptr": hex(actor_ptr),
                                 "actor_records_180_sha256": hashlib.sha256(
                                     actor_records).hexdigest(),
                                 "actor_records_180_hex": actor_records.hex()})
        return observations

    # The first steps are the prior independently recorded cold-SAV route.
    for count, buttons in ((240, ()), (1, ("a",)), (120, ()),
                           (1, ("start",)), (180, ()), (1, ("a",)),
                           (360, ()), (1, ("start",)), (60, ()),
                           (1, ("a",)), (90, ()), (1, ("a",)), (180, ())):
        frames(count, *buttons)
    shot("00_continued")

    if route in ("menus", "skills", "costumes", "costume_deep",
                 "costume_first", "custom",
                 "status", "strategy"):
        for _ in range(26):
            frames(1, "a")
            frames(90)
        shot("00_map_before_menu")
        if route == "menus":
            sequence = (("01_select", "select"), ("02_down", "down"),
                        ("03_open", "a"), ("04_down", "down"),
                        ("05_open", "a"), ("06_back", "b"),
                        ("07_back", "b"))
        elif route == "custom":
            sequence = [("01_select", "select")]
            sequence += [(f"02_down_{i+1}", "down") for i in range(8)]
            sequence += [("03_custom", "a"),
                         ("04_character_select", "a"),
                         ("05_first_character", "a"),
                         ("06_job_list", "a")]
        else:
            down = {"skills": 0, "costumes": 2, "costume_deep": 2,
                    "costume_first": 2, "status": 3,
                    "strategy": 5}[route]
            sequence = [("01_select", "select")]
            sequence += [(f"02_down_{i+1}", "down") for i in range(down)]
            sequence += [("03_open", "a")]
            if route != "costume_first":
                sequence += [("04_down", "down")]
            sequence += [("05_open", "a")]
            if route == "costume_deep":
                sequence += [("06_open_job", "a"), ("07_down", "down"),
                             ("08_open_job", "a")]
            elif route == "costume_first":
                sequence += [("06_open_job", "a"), ("07_down", "down"),
                             ("08_open_job", "a")]
            else:
                sequence += [("06_back", "b")]
        for label, key in sequence:
            frames(1, key)
            frames(90)
            shot(label)
    elif route == "arte_pair_fixture":
        for _ in range(26):
            frames(1, "a")
            frames(90)
        shot("00_map_before_fixture")
        address = 0x0200325C
        before = probe.read_memory(address, 56)
        after = bytearray(before)
        after[0], after[1] = 10, 15
        after[0x1B:0x25] = bytes((158, 159)) + bytes(8)
        after[0x25:0x29] = bytes((158, 0, 0, 0))
        after[0x2C:0x30] = struct.pack("<I", 3)
        probe.execute({"op": "write_ram", "address": hex(address),
                       "expected_hex": before.hex(), "final_hex": after.hex(),
                       "test_fixture_only": True,
                       "reason": "Isolated ARTE 158/159 known-skill fixture for menu rendering; not natural learning or save compatibility"})
        for label, key in (("01_select", "select"), ("02_skills", "a"),
                           ("03_party", "a"), ("04_list", "a"),
                           ("05_second", "down")):
            frames(1, key)
            frames(90)
            shot(label)
    elif route == "pubrose":
        for _ in range(26):
            frames(1, "a")
            frames(90)
        for key in ("up", "right"):
            frames(1, key)
            frames(60)
        shot("01_map")
        frames(1, "a")
        frames(120)
        for index in range(31):
            shot(f"dialog_{index:02}")
            frames(1, "a")
            frames(90)
    else:
        raise ValueError(route)
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "rom", "save", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--route", choices=("menus", "skills", "costumes",
                                           "costume_deep", "costume_first", "custom", "status",
                                           "strategy", "pubrose",
                                           "arte_pair_fixture", "historical_battle_replay",
                                           "battle_natural"), required=True)
    parser.add_argument("--replay-operations", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Evidence directory must be new")
    if args.rom.stat().st_size != 0x800000 or args.save.stat().st_size != 8192:
        raise ValueError("Expected exact 8 MiB ROM and 8 KiB save")
    before = {name: sha(getattr(args, name)) for name in ("core", "rom", "save")}
    probe = Probe(args.core, args.rom, args.out, args.save)
    try:
        observations = exercise(probe, args.route, args.replay_operations)
        fixture = args.route == "arte_pair_fixture"
        if probe.ram_interventions != int(fixture):
            raise AssertionError("Natural route was modified by RAM intervention")
        result = {"status": ("RAM_FIXTURE_GAME_ROUTE_NOT_NATURAL" if fixture else
                              "NATURAL_ROUTE_OBSERVATION_DIAGNOSTIC_ONLY"),
                  "route": args.route, "inputs": before,
                  "replay_operations_sha256": sha(args.replay_operations)
                  if args.replay_operations else None,
                  "core_name": probe.core_name, "core_version": probe.core_version,
                  "ram_interventions": probe.ram_interventions,
                  "observations": observations,
                  "limitations": ["Screenshots prove observed frames only.",
                                  "Arte pair fixture does not prove natural learning or save compatibility." if fixture else "No RAM intervention.",
                                  "Menu identity and all alias contexts require separate tracing.",
                                  "No hardware or release eligibility claim."]}
        (args.out / "AUDIT.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "route": args.route,
                          "rom_sha256": before["rom"], "frames": probe.frame,
                          "screenshots": len(observations),
                          "ram_interventions": probe.ram_interventions}, ensure_ascii=False))
    finally:
        probe.lib.retro_unload_game()
        probe.lib.retro_deinit()
    after = {name: sha(getattr(args, name)) for name in before}
    if after != before:
        raise AssertionError("A frozen input changed during the audit")


if __name__ == "__main__":
    main()
