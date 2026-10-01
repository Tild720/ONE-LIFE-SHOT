"""Exercise the Pistol acquisition loop in a fresh, disposable PIE session.

Run with Unreal Python after the player controller has begun play. The check
uses the existing Fire, Die, EquipPistol, ReturnToPlayer, and TryAcquire functions;
it never writes Ammo. All test actors are runtime spawns, and the result is saved
to Saved/OneShotLoopTest.json. A builtins session guard preserves the result
through OpenLevel. Stop PIE before explicitly clearing the guard for another run:
    import builtins
    session = builtins.__dict__.get('_one_shot_loop_qa_session')
    session and session.get('cancel', lambda: None)()
    builtins.__dict__.pop('_one_shot_loop_qa_session', None)
"""

import builtins
import json
from pathlib import Path

import unreal


def run():
    session_key = "_one_shot_loop_qa_session"
    if hasattr(builtins, session_key):
        unreal.log("ONE_SHOT_LOOP_TEST: existing QA session preserved; skipped reload replay")
        return
    output = Path(unreal.Paths.project_saved_dir()) / "OneShotLoopTest.json"
    result = {"passed": False, "status": "running", "checks": {}, "events": [], "phase": "startup"}
    session = {"report": result, "handle": None}
    setattr(builtins, session_key, session)
    spawned = {}
    state = {"time": 0.0, "phase_started": 0.0, "phase": "startup"}
    callback = [None]
    disabled_spawners = []

    def valid(actor):
        try:
            return actor is not None and unreal.SystemLibrary.is_valid(actor)
        except Exception:
            # A level restart can leave a Python wrapper for a stale UObject.
            return False

    def remember(actor):
        if valid(actor):
            spawned[actor.get_path_name()] = actor
        return actor

    def write_result():
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    try:
        write_result()
    except Exception as error:
        result["status"] = "failed"
        result["error"] = "Could not write QA result: " + str(error)
        unreal.log_error(result["error"])
        return

    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert valid(world), "Start a fresh PIE session before running this check"
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        assert valid(pawn) and valid(controller), "PIE player is not ready"
        classes = {
            "spawner": unreal.load_asset(
                "/Game/Enemies/BP_EnemySpawnPoint").generated_class(),
            "enemy": unreal.load_asset(
                "/Game/Enemies/BP_EnemyStraightRunner").generated_class(),
            "pickup": unreal.load_asset(
                "/Game/Weapons/Pistol/BP_PistolPickup").generated_class(),
            "pistol": unreal.load_asset(
                "/Game/Weapons/Pistol/BP_Pistol").generated_class(),
            "bullet": unreal.load_asset(
                "/Game/Weapons/Pistol/BP_BulletProjectile").generated_class(),
        }
        initial_gun = pawn.get_editor_property("EquippedPistol")
        result["initial_equipped"] = (
            initial_gun.get_path_name() if valid(initial_gun) else None)
        camera = pawn.get_editor_property("FollowCamera")
        boom = pawn.get_editor_property("CameraBoom")
        initial_rotation = camera.get_world_rotation()
        result["camera"] = {
            "pitch": initial_rotation.pitch,
            "yaw": initial_rotation.yaw,
            "arm_length": boom.get_editor_property("target_arm_length"),
            "collision_test": boom.get_editor_property("do_collision_test"),
        }
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        result["spawn_method"] = "GameplayStatics reflected deferred runtime spawn"
        result["return_clock"] = "GameplayStatics.GetTimeSeconds (game time)"
        result["spawner_configuration"] = []
        for spawner in unreal.GameplayStatics.get_all_actors_of_class(world, classes["spawner"]):
            location = spawner.get_actor_location()
            try:
                speed_override = spawner.get_editor_property("UseSpawnSpeedOverride")
            except Exception:
                speed_override = None
            result["spawner_configuration"].append({
                "position": [location.x, location.y, location.z],
                "enabled": spawner.get_editor_property("Enabled"),
                "spawn_speed": spawner.get_editor_property("SpawnSpeed"),
                "spawn_delay": spawner.get_editor_property("SpawnDelay"),
                "max_alive_enemies": spawner.get_editor_property("MaxAliveEnemies"),
                "use_spawn_speed_override": speed_override,
            })
            disabled_spawners.append((spawner, spawner.get_editor_property("Enabled")))
            spawner.set_editor_property("Enabled", False)
        result["isolated_spawners"] = len(disabled_spawners)
    except Exception as error:
        for spawner, enabled in disabled_spawners:
            if valid(spawner):
                spawner.set_editor_property("Enabled", enabled)
        result["status"] = "failed"
        result["error"] = str(error)
        write_result()
        unreal.log_error("ONE_SHOT_LOOP_TEST: " + str(error))
        return

    def actors(kind):
        return list(unreal.GameplayStatics.get_all_actors_of_class(
            world, classes[kind]))

    def paths(kind):
        return {actor.get_path_name() for actor in actors(kind)}

    def new_actors(kind, before):
        return [remember(actor) for actor in actors(kind)
                if actor.get_path_name() not in before]

    def equipped():
        return pawn.get_editor_property("EquippedPistol")

    def ammo(gun=None):
        gun = gun if gun is not None else equipped()
        assert valid(gun), "No equipped Pistol"
        return gun.get_editor_property("Ammo")

    def position(actor):
        point = actor.get_actor_location()
        return [point.x, point.y, point.z]

    def event(name, **values):
        result["events"].append({"time": state["time"], "name": name, **values})

    def check(name, condition, **values):
        result["checks"][name] = {"passed": bool(condition), **values}
        assert condition, name

    def phase(name):
        state["phase"] = name
        state["phase_started"] = state["time"]
        state["phase_started_game"] = float(statics.call_method("GetTimeSeconds", args=(world,)))
        result["phase"] = name
        result["elapsed"] = state["time"]
        write_result()

    def spawn_enemy(offset):
        # The native deferred-spawn helpers are BlueprintInternalUseOnly and are
        # absent from the generated Python stubs. Object.call_method reaches the
        # existing UFunction by name without editing production spawners or CDOs.
        transform = unreal.get_default_object(unreal.MathLibrary.static_class()).call_method(
            'MakeTransform', args=(pawn.get_actor_location() + offset,
                                   unreal.Rotator(), unreal.Vector(1.0, 1.0, 1.0)))
        scale_method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        enemy = statics.call_method("BeginDeferredActorSpawnFromClass", args=(
            world, classes["enemy"], transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale_method))
        assert valid(enemy), "Could not create QA Runner in the PIE world"
        remember(enemy)
        enemy.set_editor_property("MoveSpeed", 0.0)
        statics.call_method("FinishSpawningActor", args=(enemy, transform, scale_method))
        enemy.set_editor_property("MoveSpeed", 0.0)
        distance = enemy.get_distance_to(pawn)
        event("qa_enemy_spawned", position=position(enemy), distance_to_player=distance)
        assert distance > 500.0, "QA Runner spawned too close to the player"
        return enemy

    def aim_away():
        point = pawn.get_actor_location() + unreal.Vector(-250.0, 150.0, -92.0)
        pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
        assert pixel is not None, "QA aim point could not be projected into the PIE viewport"
        controller.set_mouse_location(round(pixel.x), round(pixel.y))
        result["last_aim"] = {"world_point": [point.x, point.y, point.z],
                              "projected_pixel": [pixel.x, pixel.y]}

    def aim_context():
        # Unreal Python's bool-plus-output methods return None on failure. Keep
        # their complete values in the report so focus/deprojection failures are
        # distinguished from production Fire failures.
        def serial(value):
            if value is None or isinstance(value, (bool, int, float, str)):
                return value
            if isinstance(value, (tuple, list)):
                return [serial(item) for item in value]
            if isinstance(value, unreal.Vector):
                return [value.x, value.y, value.z]
            if isinstance(value, unreal.Vector2D):
                return [value.x, value.y]
            return str(value)
        mouse = controller.get_mouse_position()
        ray = controller.deproject_mouse_position_to_world()
        viewport = controller.get_viewport_size()
        gun = equipped()
        context = {
            "world": world.get_path_name(), "pawn": pawn.get_path_name(),
            "pawn_position": position(pawn),
            "camera_position": serial(camera.get_world_location()),
            "projection": result.get("last_aim"),
            "mouse_position": serial(mouse), "deprojection": serial(ray),
            "viewport_size": serial(viewport),
            "gun": gun.get_path_name() if valid(gun) else None,
            "gun_position": position(gun) if valid(gun) else None,
            "elapsed": state["time"],
        }
        result["last_aim_context"] = context
        ready = mouse is not None and ray is not None
        if ready and isinstance(viewport, (tuple, list)) and len(viewport) == 2:
            ready = viewport[0] > 0 and viewport[1] > 0
            if isinstance(mouse, (tuple, list)) and len(mouse) == 2:
                ready = ready and 0 <= mouse[0] < viewport[0] and 0 <= mouse[1] < viewport[1]
        return ready, context

    def fire_once():
        gun = equipped()
        assert ammo(gun) == 1, "Real firing check requires one loaded shot"
        ready, context = aim_context()
        assert ready, "PIE mouse position/deprojection is unavailable; focus the PIE viewport"
        event("fire_request", aim=context)
        before = paths("bullet")
        gun.call_method("Fire")
        bullets = new_actors("bullet", before)
        check("successful_fire_consumes_one_shot", ammo(gun) == 0,
              ammo_after=ammo(gun), created_projectiles=len(bullets))
        assert len(bullets) == 1, "Successful Fire must create exactly one projectile"
        return gun, {bullet.get_path_name() for bullet in bullets}

    def collect_qa_guns(before):
        return new_actors("pistol", before)

    def cleanup():
        if callback[0] is not None:
            unreal.unregister_slate_post_tick_callback(callback[0])
            callback[0] = None
            session["handle"] = None
        # A test-created Pistol may be equipped. Clear its reference before cleanup;
        # no original actor or original pickup is deleted by this function.
        current = equipped() if valid(pawn) else None
        if valid(current) and current.get_path_name() in spawned:
            pawn.set_editor_property("EquippedPistol", None)
        for actor in list(spawned.values()):
            if valid(actor):
                actor.destroy_actor()
        for spawner, enabled in disabled_spawners:
            if valid(spawner):
                spawner.set_editor_property("Enabled", enabled)
        result["cleanup"] = "Removed only tracked QA runtime actors; restart PIE to reset ammunition"

    def tick(dt):
        try:
            assert valid(pawn), "Player disappeared or level restarted during QA"
            state["time"] += dt
            assert state["time"] < 12.0, "One-shot loop QA timed out"
            age = state["time"] - state["phase_started"]
            current_phase = state["phase"]
            if current_phase in ("death_return", "loaded_return", "concurrent_return"):
                age = float(statics.call_method("GetTimeSeconds", args=(world,))) - state["phase_started_game"]

            if current_phase == "startup":
                if age < 2.0:
                    return
                before = paths("pistol")
                if not valid(equipped()) or ammo() == 0:
                    pawn.call_method("EquipPistol")
                collect_qa_guns(before)
                check("initial_weapon_has_one_shot", ammo() == 1)
                check("unlimited_ammo_disabled",
                      not equipped().get_editor_property("UnlimitedAmmo"))
                aim_away()
                phase("initial_fire")
                return

            if current_phase == "initial_fire":
                aim_away()
                ready, _ = aim_context()
                if age < 0.2 or (not ready and age < 2.0):
                    return
                state["spent_gun"], state["first_bullets"] = fire_once()
                # Three explicit presses: only the loaded first press may shoot.
                before = paths("bullet")
                state["spent_gun"].call_method("Fire")
                state["spent_gun"].call_method("Fire")
                extra = new_actors("bullet", before)
                check("spent_weapon_rejects_additional_shots", not extra and ammo() == 0,
                      extra_projectiles=len(extra))
                phase("enemy_death")
                return

            if current_phase == "enemy_death":
                if age < 0.1:
                    return
                enemy = spawn_enemy(unreal.Vector(850.0, 400.0, 0.0))
                before = paths("pickup")
                state["guns_before_return"] = paths("pistol")
                enemy.call_method("Die")
                enemy.call_method("Die")
                drops = new_actors("pickup", before)
                check("double_die_creates_exactly_one_drop", len(drops) == 1,
                      drop_count=len(drops))
                state["drop"] = drops[0]
                state["drop_start"] = drops[0].get_actor_location()
                state["drop_start_distance"] = drops[0].get_distance_to(pawn)
                check("death_drop_starts_returning",
                      drops[0].get_editor_property("Returning"))
                event("enemy_drop", location=position(drops[0]),
                      duration=drops[0].get_editor_property("ReturnDuration"))
                phase("death_return")
                return

            if current_phase == "death_return":
                drop = state["drop"]
                if 0.08 <= age < 0.45 and "return_is_visible_before_ammo_refill" not in result["checks"]:
                    distance = drop.get_distance_to(pawn) if valid(drop) else 0.0
                    moved = ((drop.get_actor_location() - state["drop_start"]).length()
                             if valid(drop) else 0.0)
                    check("return_is_visible_before_ammo_refill",
                          valid(drop) and ammo() == 0 and moved > 5.0
                          and distance < state["drop_start_distance"],
                          elapsed=age, moved=moved, remaining_distance=distance)
                if equipped() != state["spent_gun"] and ammo() == 1:
                    collect_qa_guns(state["guns_before_return"])
                    check("death_return_acquires_within_09_seconds", age <= 0.9 and not valid(drop),
                          elapsed=age, ammo=ammo())
                    assert "return_is_visible_before_ammo_refill" in result["checks"], "No visible flight sampled"
                    before = paths("pickup")
                    state["loaded_gun"] = equipped()
                    enemy = spawn_enemy(unreal.Vector(750.0, -450.0, 0.0))
                    enemy.call_method("Die")
                    drops = new_actors("pickup", before)
                    assert len(drops) == 1, "Loaded-weapon scenario must create one drop"
                    state["retained_drop"] = drops[0]
                    phase("loaded_return")
                elif age > 0.9:
                    raise AssertionError("Death drop did not provide the next shot within 0.9 seconds")
                return

            if current_phase == "loaded_return":
                assert equipped() == state["loaded_gun"] and ammo() == 1, "Returning drop replaced a loaded weapon"
                if age < 0.85:
                    return
                drop = state["retained_drop"]
                check("loaded_arrival_preserves_weapon_and_pickup",
                      valid(drop) and not drop.get_editor_property("Returning")
                      and equipped() == state["loaded_gun"] and ammo() == 1,
                      elapsed=age, distance=drop.get_distance_to(pawn) if valid(drop) else None)
                assert drop.get_distance_to(pawn) <= drop.get_editor_property("PickupRadius"), "Returned pickup out of reach"
                aim_away()
                phase("spend_then_acquire")
                return

            if current_phase == "spend_then_acquire":
                if age < 0.12:
                    return
                spent, _ = fire_once()
                before = paths("pistol")
                drop = state["retained_drop"]
                drop.call_method("TryAcquire")
                collect_qa_guns(before)
                check("nearby_pickup_replaces_actual_spent_weapon",
                      equipped() != spent and ammo() == 1 and not valid(drop))
                aim_away()
                phase("concurrent_setup")
                return

            if current_phase == "concurrent_setup":
                if age < 0.12:
                    return
                state["concurrent_spent"], _ = fire_once()
                state["concurrent_guns_before"] = paths("pistol")
                before = paths("pickup")
                enemies = [spawn_enemy(unreal.Vector(850.0, 350.0, 0.0)),
                           spawn_enemy(unreal.Vector(850.0, -350.0, 0.0))]
                for enemy in enemies:
                    enemy.call_method("Die")
                drops = new_actors("pickup", before)
                assert len(drops) == 2, "Concurrent deaths must create two distinct drops"
                state["concurrent_drops"] = drops
                state["equipped_history"] = {state["concurrent_spent"].get_path_name()}
                phase("concurrent_return")
                return

            if current_phase == "concurrent_return":
                if valid(equipped()):
                    state["equipped_history"].add(equipped().get_path_name())
                collect_qa_guns(state["concurrent_guns_before"])
                if age < 0.85:
                    return
                remaining = [drop for drop in state["concurrent_drops"] if valid(drop)]
                replacements = len(state["equipped_history"]) - 1
                check("concurrent_returns_equip_exactly_one_weapon",
                      ammo() == 1 and replacements == 1 and len(remaining) == 1,
                      equipped_replacements=replacements, remaining_pickups=len(remaining), elapsed=age)
                final_rotation = camera.get_world_rotation()
                check("mouse_aim_keeps_camera_rotation_fixed",
                      abs(final_rotation.pitch - initial_rotation.pitch) < 0.01
                      and abs(final_rotation.yaw - initial_rotation.yaw) < 0.01,
                      pitch=final_rotation.pitch, yaw=final_rotation.yaw)
                result["passed"] = all(item["passed"] for item in result["checks"].values())
                result["phase"] = "complete"
                result["status"] = "complete"
                result["elapsed"] = state["time"]
                cleanup()
                write_result()
                unreal.log("ONE_SHOT_LOOP_TEST: PASS")
                return

        except Exception as error:
            result["status"] = "failed"
            result["error"] = str(error)
            result["elapsed"] = state["time"]
            try:
                cleanup()
            except Exception as cleanup_error:
                result["cleanup_error"] = str(cleanup_error)
            write_result()
            unreal.log_error("ONE_SHOT_LOOP_TEST: " + str(error))

    session["cancel"] = cleanup
    try:
        callback[0] = unreal.register_slate_post_tick_callback(tick)
        session["handle"] = callback[0]
    except Exception as error:
        result["status"] = "failed"
        result["error"] = "Could not register QA callback: " + str(error)
        cleanup()
        write_result()
        unreal.log_error(result["error"])


run()
