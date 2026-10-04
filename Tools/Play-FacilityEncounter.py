"""Observe the saved facility through production movement, mouse aim and actions.

This is a playback policy, not a pass/fail gameplay test. It never spawns actors,
writes inventory/AI state, injects damage, calls Die/FailRun, hides actors, or
freezes gameplay. It holds a Sniper for a Heavy and an RPG for a nearby group,
and reacts after warning aim commits. A poor run is not proof of a gameplay bug.

Run once in a fresh PIE session, with the floating viewport focused. The report
survives OpenLevel and is written to Saved/FacilityEncounterPlay.json. Stop PIE
before resetting for another run:
    import builtins
    playback = builtins.__dict__.get('_ols_facility_play_session')
    playback and playback.get('cancel', lambda: None)()
    builtins.__dict__.pop('_ols_facility_play_session', None)
"""

import builtins
import json
import math
import time
from pathlib import Path

import unreal


SESSION_KEY = '_ols_facility_play_session'
RUN_SECONDS = 42.0


def run():
    previous_session = getattr(builtins, SESSION_KEY, None)
    if previous_session and previous_session.get('finished'):
        delattr(builtins, SESSION_KEY)
    elif previous_session:
        unreal.log('FACILITY_PLAY: keeping previous playback through level reload')
        return
    policy = str(getattr(builtins, '_ols_facility_play_policy', 'order'))
    report = {
        'status': 'running', 'policy': 'facility_target_order_and_committed_attack_evade',
        'scenario': policy,
        'run_seconds': RUN_SECONDS, 'events': [], 'samples': [],
        'controls': 'Production AddMovementInput, projected mouse location, Fire, TryDodge',
        'limitations': 'Bot decisions are observations, not a human fun verdict or guaranteed winning strategy',
    }
    session = {'handle': None, 'finished': False, 'report': report}
    setattr(builtins, SESSION_KEY, session)
    output = Path(unreal.Paths.project_saved_dir()) / (
        'FacilityEncounterPlay_miss.json' if policy == 'miss' else 'FacilityEncounterPlay.json')
    state = {
        'start_wall': time.monotonic(), 'pawn': None, 'epoch': -1,
        'seen_dead': set(), 'last_gun': None, 'last_sample': -1.0,
        'last_fire': -10.0, 'aim_key': None, 'aim_started': 0.0,
        'previous_move': (0.0, 1.0), 'last_positions': {}, 'max_y': 0.0,
        'last_policy': None,
        'intentionally_missed': False,
    }

    def valid(obj):
        try:
            return obj is not None and unreal.SystemLibrary.is_valid(obj)
        except Exception:
            return False

    def xyz(vector):
        return [round(vector.x, 2), round(vector.y, 2), round(vector.z, 2)]

    def normal(x, y):
        magnitude = math.hypot(x, y)
        return (x / magnitude, y / magnitude) if magnitude > 0.001 else (0.0, 1.0)

    def elapsed():
        return time.monotonic() - state['start_wall']

    def write():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def event(name, **values):
        report['events'].append({'at': round(elapsed(), 3), 'epoch': state['epoch'], 'name': name, **values})

    def finish(error=None):
        if session['finished']:
            return
        session['finished'] = True
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        report['status'] = 'error' if error else 'complete'
        if error:
            report['error'] = str(error)
        report['max_player_y'] = round(state['max_y'], 2)
        report['restarts'] = max(state['epoch'], 0)
        report['fires_by_kind'] = {str(kind): sum(
            event_row['name'] == 'fire' and event_row.get('kind') == kind
            for event_row in report['events']) for kind in range(4)}
        write()
        unreal.log('FACILITY_PLAY ' + report['status'])

    session['cancel'] = lambda: finish('Explicitly cancelled')

    def tick(_dt):
        try:
            wall_time = elapsed()
            if wall_time >= RUN_SECONDS:
                finish()
                return
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not valid(world):
                return
            pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            if not valid(pawn) or not valid(controller):
                return
            game_time = float(statics.call_method('GetTimeSeconds', args=(world,)))
            if state['pawn'] != pawn:
                state['pawn'] = pawn
                state['epoch'] += 1
                state['last_gun'] = None
                state['aim_key'] = None
                state['last_positions'] = {}
                event('spawn_or_restart', pawn=pawn.get_path_name())

            enemies = list(unreal.GameplayStatics.get_all_actors_of_class(world, enemy_class))
            living = []
            for actor in enemies:
                identity = (state['epoch'], actor.get_path_name())
                if actor.get_editor_property('Dead'):
                    if identity not in state['seen_dead']:
                        state['seen_dead'].add(identity)
                        event('enemy_defeated', kind=actor.get_editor_property('WeaponKind'),
                              enemy=actor.get_path_name(), position=xyz(actor.get_actor_location()))
                    continue
                point = actor.get_actor_location()
                prior = state['last_positions'].get(identity)
                velocity = actor.get_velocity()
                if prior and game_time > prior[0] and velocity.length() < 1.0:
                    velocity = (point - prior[1]) / (game_time - prior[0])
                state['last_positions'][identity] = (game_time, point)
                living.append({
                    'actor': actor, 'id': actor.get_path_name(),
                    'kind': int(actor.get_editor_property('WeaponKind')),
                    'point': point, 'velocity': velocity,
                    'distance': actor.get_distance_to(pawn),
                    'ai': int(actor.get_editor_property('AIState')),
                    'remaining': float(actor.get_editor_property('StateEndTime')) - game_time,
                    'charge': bool(actor.get_editor_property('ChargeActive')),
                })
            living.sort(key=lambda row: row['distance'])
            location = pawn.get_actor_location()
            state['max_y'] = max(state['max_y'], location.y)
            current_gun = pawn.get_editor_property('EquippedPistol')
            ammo = int(current_gun.get_editor_property('Ammo')) if valid(current_gun) else 0
            kind = int(current_gun.get_editor_property('WeaponKind')) if valid(current_gun) else None
            if valid(current_gun) and state['last_gun'] != current_gun.get_path_name():
                state['last_gun'] = current_gun.get_path_name()
                event('acquired_weapon', kind=kind, ammo=ammo, player=xyz(location))
                state['aim_key'] = None
            dead = bool(pawn.get_editor_property('Dead'))
            decision = 'advance'
            target = None
            move = (0.0, 0.0)
            threat = None
            if not dead:
                nearest = living[0] if living else None
                # Carry the penetrating shot on the left of the route so the
                # Heavy and the Basic behind it are not accidentally collinear.
                preferred_x = -230.0 if kind == 2 and ammo else 0.0
                move = normal(max(-0.65, min(0.65, (preferred_x - location.x) / 240.0)),
                              1.0 if location.y < 3720.0 else 0.0)
                if location.y >= 3720.0 and abs(preferred_x - location.x) < 25.0:
                    move = (0.0, 0.0)
                if policy == 'miss' and ammo == 0:
                    # A visible permanent wall is the bait, rather than a test
                    # obstacle. Stay close enough for the committed charge to
                    # reach it, then use the same late perpendicular escape.
                    assaults = [row for row in living if row['kind'] == 1]
                    near_assault = min(assaults, key=lambda row: row['distance']) if assaults else None
                    vertical = 0.0 if near_assault and near_assault['distance'] < 900.0 else 0.35
                    move = normal(max(-1.0, min(1.0, (548.0 - location.x) / 140.0)), vertical)
                    decision = 'empty_bait_charge_at_existing_wall'

                if ammo and living:
                    ranges = {0: 'PistolRange', 1: 'ShotgunRange', 2: 'SniperRange', 3: 'RocketRange'}
                    usable_range = float(current_gun.get_editor_property(ranges[kind])) - (60.0 if kind == 1 else 90.0)
                    available = [row for row in living if row['distance'] < usable_range]
                    if kind == 2:
                        heavy = [row for row in available if row['kind'] == 3]
                        target = min(heavy, key=lambda row: row['distance']) if heavy else None
                        decision = 'sniper_target_heavy' if target else 'hold_sniper_advance_to_heavy'
                        if target:
                            # Settle the mouse projection before the trace and
                            # keep the source in front of the fixed camera.
                            move = (0.0, 0.0)
                        elif location.y >= 2700.0:
                            move = (0.0, 0.0)
                        if nearest and nearest['distance'] < 155.0:
                            target = nearest
                            decision = 'sniper_emergency_contact'
                    elif kind == 3:
                        radius = float(current_gun.get_editor_property('BlastRadius'))
                        groups = []
                        for candidate in available:
                            neighbours = [other for other in living if
                                          (other['point'] - candidate['point']).length() <= radius - 25.0]
                            core_bonus = candidate['point'].y > 2700.0
                            groups.append((len(neighbours), core_bonus, -candidate['distance'], candidate))
                        groups.sort(key=lambda row: row[:3], reverse=True)
                        if groups and groups[0][0] >= 2:
                            target = groups[0][3]
                            decision = 'rpg_target_group'
                        elif nearest and nearest['distance'] < 200.0:
                            target = nearest
                            decision = 'rpg_emergency_contact'
                        else:
                            decision = 'hold_rpg_advance_for_group'
                    elif kind == 0:
                        # A Pistol can remove the ranged source before entering
                        # its lane. Earlier in the route, the Assault supplies
                        # the close-range next shot.
                        snipers = [row for row in available if row['kind'] == 2]
                        assaults = [row for row in available if row['kind'] == 1]
                        target = (snipers[0] if snipers else assaults[0] if assaults else available[0] if available else None)
                        if nearest and nearest['distance'] < 210.0:
                            target = nearest
                        decision = 'pistol_choose_next_weapon'
                    else:
                        target = available[0] if available else None
                        decision = 'shotgun_close_target' if target else 'shotgun_close_distance'
                if kind == 2 and ammo == 0 and location.y >= 2700.0:
                    move = (0.0, 0.0)
                    decision = 'empty_sniper_keep_heavy_in_front'

                # Walking out of the final locked shape preserves dodge for
                # danger that is still present just before impact, rather than
                # spending the brief window as soon as a warning appears.
                for row in living:
                    actor = row['actor']
                    if row['ai'] != 1 and not row['charge']:
                        continue
                    if row['kind'] == 3:
                        attack_target = actor.get_editor_property('AttackTarget')
                        delta_x = location.x - attack_target.x
                        delta_y = location.y - attack_target.y
                        danger_distance = math.hypot(delta_x, delta_y)
                        radius = float(actor.get_editor_property('BlastRadius'))
                        if row['ai'] == 1 and row['remaining'] <= 0.55 and danger_distance < radius + 35.0:
                            if danger_distance < 35.0:
                                delta_x = -1.0 if location.x > 0.0 else 1.0
                                delta_y = 0.15
                            evade = normal(delta_x, delta_y)
                            candidate = {'row': row, 'move': evade, 'urgent': row['remaining'] <= 0.14,
                                         'reason': 'locked_heavy_blast', 'remaining': row['remaining']}
                        else:
                            continue
                    elif row['kind'] in (1, 2):
                        origin = actor.get_editor_property('AttackOrigin')
                        direction = actor.get_editor_property('AttackDirection')
                        along = ((location.x - origin.x) * direction.x
                                 + (location.y - origin.y) * direction.y)
                        lateral = ((location.x - origin.x) * -direction.y
                                   + (location.y - origin.y) * direction.x)
                        width = float(actor.get_editor_property('AttackWidth')) + 45.0
                        length = float(actor.get_editor_property('AttackLength')) + 80.0
                        locked = row['charge'] or (row['ai'] == 1 and row['remaining'] <= 0.38)
                        if not locked or not (-50.0 <= along <= length and abs(lateral) <= width):
                            continue
                        sides = [normal(-direction.y, direction.x), normal(direction.y, -direction.x)]
                        # Choose the side with usable floor space; prefer forward
                        # progress only after avoiding the surrounding walls.
                        def score(side):
                            end_x = location.x + side[0] * 240.0
                            wall_penalty = max(abs(end_x) - 490.0, 0.0) * 10.0
                            current_side = side[0] * -direction.y + side[1] * direction.x
                            return -wall_penalty + (30.0 if lateral * current_side > 0.0 else 0.0) + side[1] * 15.0
                        evade = max(sides, key=score)
                        urgent = (row['charge'] and row['distance'] < 230.0) or (row['ai'] == 1 and row['remaining'] <= 0.13)
                        candidate = {'row': row, 'move': evade, 'urgent': urgent,
                                     'reason': 'committed_charge' if row['kind'] == 1 else 'locked_sniper_lane',
                                     'remaining': row['remaining']}
                    else:
                        continue
                    if threat is None or (candidate['urgent'], -candidate['remaining']) > (threat['urgent'], -threat['remaining']):
                        threat = candidate
                if nearest and nearest['distance'] < 145.0:
                    delta = location - nearest['point']
                    threat = {'row': nearest, 'move': normal(delta.x, delta.y), 'urgent': True,
                              'reason': 'near_contact', 'remaining': 0.0}
                if threat:
                    move = threat['move']
                    decision = threat['reason']
                # Keep the controller inside the central walkable lane. Cover
                # can still physically stop movement; the policy never moves
                # the actor through it or deletes the obstacle.
                boundary = 548.0 if policy == 'miss' and ammo == 0 else 490.0
                if location.x > boundary:
                    move = normal(min(move[0], -0.4), move[1])
                elif location.x < -boundary:
                    move = normal(max(move[0], 0.4), move[1])
                pawn.add_movement_input(unreal.Vector(move[0], move[1], 0.0), 1.0, False)
                prior_move = state['previous_move']
                direction_ready = move[0] * prior_move[0] + move[1] * prior_move[1] > 0.75
                if (threat and threat['urgent'] and direction_ready
                        and not pawn.get_editor_property('DodgeCooling')):
                    pawn.call_method('TryDodge')
                    event('dodge', ammo=ammo, reason=threat['reason'],
                          remaining=round(threat['remaining'], 3),
                          enemy_kind=threat['row']['kind'], distance=round(threat['row']['distance'], 1),
                          movement=[round(move[0], 3), round(move[1], 3)])
                state['previous_move'] = move

                if ammo and target and not pawn.get_editor_property('Dodging') and wall_time - state['last_fire'] > 0.7:
                    point = target['point']
                    speed = 2200.0 if kind in (0, 1) else float(current_gun.get_editor_property('RocketSpeed')) if kind == 3 else 0.0
                    travel = min(target['distance'] / speed, 1.5) if speed else 0.0
                    lead = target['velocity'] * travel
                    point = unreal.Vector(point.x + lead.x, point.y + lead.y, 50.0)
                    intended_miss = policy == 'miss' and not state['intentionally_missed']
                    if intended_miss:
                        point = location + unreal.Vector(-450.0, 150.0, -92.0)
                    pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
                    viewport = controller.get_viewport_size()
                    if (pixel is not None and 0 <= pixel.x < viewport[0] and 0 <= pixel.y < viewport[1]):
                        controller.set_mouse_location(round(pixel.x), round(pixel.y))
                        aim_key = (state['epoch'], current_gun.get_path_name(), target['id'])
                        if state['aim_key'] != aim_key:
                            state['aim_key'] = aim_key
                            state['aim_started'] = game_time
                        elif game_time - state['aim_started'] >= 0.12 and controller.deproject_mouse_position_to_world() is not None:
                            current_gun.call_method('Fire')
                            if intended_miss and int(current_gun.get_editor_property('Ammo')) == 0:
                                state['intentionally_missed'] = True
                            state['last_fire'] = wall_time
                            state['aim_key'] = None
                            evidence = {'kind': kind, 'ammo_after': int(current_gun.get_editor_property('Ammo')),
                                        'target_kind': target['kind'], 'target': target['id'],
                                        'target_position': xyz(target['point']), 'aim_point': xyz(point),
                                        'target_velocity': xyz(target['velocity']), 'distance': round(target['distance'], 1),
                                        'player': xyz(location), 'decision': decision, 'intended_miss': intended_miss}
                            try:
                                origin = current_gun.get_editor_property('ShotOrigin')
                                rotation = current_gun.get_editor_property('ShotRotation')
                                yaw = math.radians(rotation.yaw)
                                pitch = math.radians(rotation.pitch)
                                shot_direction = unreal.Vector(math.cos(pitch) * math.cos(yaw),
                                                               math.cos(pitch) * math.sin(yaw), math.sin(pitch))
                                target_delta = target['point'] - origin
                                along = target_delta.x * shot_direction.x + target_delta.y * shot_direction.y + target_delta.z * shot_direction.z
                                evidence['shot_origin'] = xyz(origin)
                                evidence['shot_rotation'] = [round(rotation.pitch, 2), round(rotation.yaw, 2), round(rotation.roll, 2)]
                                evidence['target_distance_from_shot_line'] = round(math.sqrt(max(target_delta.length() ** 2 - along ** 2, 0.0)), 2)
                                if kind == 2:
                                    evidence['sniper_visual_end'] = xyz(current_gun.get_editor_property('SniperVisualEnd'))
                                    evidence['sniper_ignored'] = [actor.get_path_name() if valid(actor) else None
                                                                  for actor in current_gun.get_editor_property('SniperIgnored')]
                                    evidence['target_visibility_components'] = []
                                    for component in target['actor'].get_components_by_class(unreal.PrimitiveComponent):
                                        evidence['target_visibility_components'].append({
                                            'component': component.get_name(),
                                            'enabled': str(component.get_collision_enabled()),
                                            'visibility': str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)),
                                        })
                            except Exception as diagnostic_error:
                                evidence['shot_diagnostic_error'] = str(diagnostic_error)
                            event('fire', **evidence)
                    else:
                        state['aim_key'] = None
                else:
                    state['aim_key'] = None

            if decision != state['last_policy']:
                event('decision', policy=decision, weapon=kind, ammo=ammo, player=xyz(location))
                state['last_policy'] = decision
            if wall_time - state['last_sample'] >= 0.25:
                state['last_sample'] = wall_time
                pickups = list(unreal.GameplayStatics.get_all_actors_of_class(world, pickup_class))
                report['samples'].append({
                    'at': round(wall_time, 3), 'game_time': round(game_time, 3), 'epoch': state['epoch'],
                    'player': xyz(location), 'dead': dead, 'ammo': ammo, 'weapon': kind,
                    'dodging': bool(pawn.get_editor_property('Dodging')), 'decision': decision,
                    'enemies': [{'kind': row['kind'], 'id': row['id'], 'position': xyz(row['point']),
                                 'state': row['ai'], 'remaining': round(row['remaining'], 3), 'charge': row['charge']}
                                for row in living],
                    'pickups': [{'kind': int(actor.get_editor_property('WeaponKind')),
                                 'position': xyz(actor.get_actor_location()),
                                 'returning': bool(actor.get_editor_property('Returning'))} for actor in pickups],
                })
                write()
        except Exception as error:
            finish(error)

    try:
        enemy = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
        pickup = unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
        assert enemy and pickup, 'Existing combat assets are unavailable'
        enemy_class = enemy.generated_class()
        pickup_class = pickup.generated_class()
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
