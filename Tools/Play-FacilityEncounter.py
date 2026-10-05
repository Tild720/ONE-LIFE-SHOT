"""Observe the saved facility through production movement, mouse aim and actions.

This is a playback policy, not a pass/fail gameplay test. It never spawns actors,
writes inventory/AI state, injects damage, calls Die/FailRun, hides actors, or
freezes gameplay. It holds a Sniper for a Heavy and an RPG for a nearby group,
and reacts after warning aim commits. A poor run is not proof of a gameplay bug.
It observes current + FIFO reserve and marks deliberate promotion shots as drains.

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
        'complete_reached': False,
        'inventory_contract': 'EquippedPistol + QueuedWeaponKind(-1 empty), maximum two one-shot weapons',
        'inventory_issues': [],
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
        'last_reserve': None, 'max_carried': 0, 'drained_after_clear': False,
        'last_fire': -10.0, 'aim_key': None, 'aim_started': 0.0,
        'previous_move': (0.0, 1.0), 'last_positions': {}, 'max_y': 0.0,
        'last_policy': None,
        'intentionally_missed': False,
        'miss_recovered': False, 'bait_y': None,
        'bait_wall_x': None, 'bait_wall_limits': None,
        'bait_escape_goal': None, 'bait_escape_until': -1.0, 'bait_escape_actor': None,
        'progress_manager': None, 'advance_stop_y': None,
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

    def inventory(player):
        weapon = player.get_editor_property('EquippedPistol')
        has_current = valid(weapon)
        loaded = int(weapon.get_editor_property('Ammo')) if has_current else 0
        reserve = int(player.get_editor_property('QueuedWeaponKind'))
        current_kind = int(weapon.get_editor_property('WeaponKind')) if has_current else None
        fields = {'weapon_actor': weapon.get_path_name() if has_current else None,
                  'weapon': current_kind,
                  'ammo': loaded, 'queued_kind': reserve,
                  'carried_count': int(has_current) + int(reserve >= 0)}
        state['max_carried'] = max(state['max_carried'], fields['carried_count'])
        if ((has_current and (loaded != 1 or current_kind not in (0, 1, 2, 3)))
                or reserve not in (-1, 0, 1, 2, 3) or fields['carried_count'] > 2
                or (not has_current and reserve >= 0)):
            if not report['inventory_issues'] or report['inventory_issues'][-1]['state'] != fields:
                report['inventory_issues'].append({'at': round(elapsed(), 3), 'state': fields})
        return weapon, fields

    def projectiles(world):
        return {actor.get_path_name(): actor for actor in
                unreal.GameplayStatics.get_all_actors_of_class(world, bullet_class) if valid(actor)}

    def projectile_evidence(actor):
        rotation = actor.get_actor_rotation()
        return {'actor': actor.get_path_name(), 'kind': int(actor.get_editor_property('WeaponKind')),
                'origin': xyz(actor.get_actor_location()),
                'rotation': [round(rotation.pitch, 2), round(rotation.yaw, 2), round(rotation.roll, 2)],
                'velocity': xyz(actor.get_velocity())}

    def choose_solid_bait(world, pawn, preferred_y):
        panels = []
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor.static_class()):
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            if not valid(component) or component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
                continue
            mesh = component.get_editor_property('static_mesh')
            if not valid(mesh) or mesh.get_name() not in ('SM_Wall', 'SM_Wall_Decorated'):
                continue
            origin, extent = actor.get_actor_bounds(True)
            if origin.x > 550.0 and 500.0 <= origin.y <= 1700.0:
                panels.append((abs(origin.y - preferred_y), actor, mesh, origin, extent))
        assert panels, 'No existing solid right-wall panel is available for the miss observation'
        _, actor, mesh, origin, extent = min(panels, key=lambda row: row[0])
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        radius = float(capsule.call_method('GetScaledCapsuleRadius'))
        state['bait_wall_x'] = origin.x - extent.x - radius - 13.0
        state['bait_y'] = origin.y
        state['bait_wall_limits'] = (origin.y - extent.y + 60.0, origin.y + extent.y - 60.0)
        return {'wall': actor.get_path_name(), 'mesh': mesh.get_path_name(),
                'wall_x': round(state['bait_wall_x'], 2), 'y': round(state['bait_y'], 2),
                'wall_bounds_y': [round(origin.y - extent.y, 2), round(origin.y + extent.y, 2)]}

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
        report['drains_by_kind'] = {str(kind): sum(
            row['name'] == 'fire' and row.get('kind') == kind and row.get('intended_drain', False)
            for row in report['events']) for kind in range(4)}
        report['reserve_promotions'] = sum(row['name'] == 'promoted_weapon' for row in report['events'])
        report['max_weapons_observed'] = state['max_carried']
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
                state['last_reserve'] = None
                state['drained_after_clear'] = False
                state['aim_key'] = None
                state['last_positions'] = {}
                managers = list(unreal.GameplayStatics.get_all_actors_of_class(world, progress_class))
                assert len(managers) == 1, 'Expected the existing saved-map progress manager'
                manager = managers[0]
                start_point = manager.get_editor_property('StartPoint')
                end_point = manager.get_editor_property('EndPoint')
                assert valid(start_point) and valid(end_point), 'Saved route points are unavailable'
                start_location = start_point.get_actor_location()
                end_location = end_point.get_actor_location()
                # The saved final bay spans Y2700..4200. Cross its actual end
                # point, then coast within the floor rather than stopping short.
                assert 2700.0 <= end_location.y <= 4110.0 and end_location.y > start_location.y
                state['progress_manager'] = manager
                state['advance_stop_y'] = min(end_location.y + 40.0, 4110.0)
                event('spawn_or_restart', pawn=pawn.get_path_name())
                event('route_observed', start=xyz(start_location), end=xyz(end_location),
                      advance_stop_y=round(state['advance_stop_y'], 2))

            manager = state['progress_manager']
            progress_value = float(manager.get_editor_property('Progress'))
            current_stage = str(manager.get_editor_property('CurrentStage'))
            complete = 'COMPLETE' in current_stage.upper()
            if complete and not report['complete_reached']:
                report['complete_reached'] = True
                event('progress_complete', progress=round(progress_value, 4), stage=current_stage,
                      player=xyz(pawn.get_actor_location()))
            report['final_progress'] = round(progress_value, 4)
            report['final_stage'] = current_stage

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
            current_gun, slots = inventory(pawn)
            ammo, kind, reserve = slots['ammo'], slots['weapon'], slots['queued_kind']
            if valid(current_gun) and state['last_gun'] != current_gun.get_path_name():
                state['last_gun'] = current_gun.get_path_name()
                event('acquired_weapon', kind=kind, ammo=ammo, player=xyz(location))
                if (policy == 'miss' and state['epoch'] == 0 and state['intentionally_missed']
                        and kind == 1 and ammo == 1 and not state['miss_recovered']):
                    state['miss_recovered'] = True
                    event('empty_weapon_acquisition', kind=kind, ammo=ammo, player=xyz(location))
                state['aim_key'] = None
            if state['last_reserve'] != reserve:
                if reserve >= 0:
                    event('stored_reserve', kind=reserve, current_kind=kind, ammo=ammo,
                          previous=state['last_reserve'], player=xyz(location))
                elif state['last_reserve'] is not None:
                    event('reserve_changed', kind=reserve, previous=state['last_reserve'], current_kind=kind)
                state['last_reserve'] = reserve
            dead = bool(pawn.get_editor_property('Dead'))
            decision = 'advance'
            target = None
            drain_reason = None
            move = (0.0, 0.0)
            threat = None
            bait_active = (policy == 'miss' and state['epoch'] == 0
                           and state['intentionally_missed'] and not state['miss_recovered'] and ammo == 0)
            if not dead:
                nearest = living[0] if living else None
                # Carry the penetrating shot on the left of the route so the
                # Heavy and the Basic behind it are not accidentally collinear.
                preferred_x = -230.0 if kind == 2 and ammo else 0.0
                move = normal(max(-0.65, min(0.65, (preferred_x - location.x) / 240.0)),
                              1.0 if location.y < state['advance_stop_y'] else 0.0)
                if location.y >= state['advance_stop_y'] and abs(preferred_x - location.x) < 25.0:
                    move = (0.0, 0.0)
                if bait_active:
                    # A visible permanent wall is the bait, rather than a test
                    # obstacle. Stay close enough for the committed charge to
                    # reach it, then use the same late perpendicular escape.
                    # Pass the slow Basic while there is lateral space, then
                    # hold beside the first Assault. Marching along the wall
                    # would enter the Sniper/Heavy rooms without a next shot.
                    bait_y = state['bait_y']
                    wall_x = state['bait_wall_x']
                    horizontal = max(-1.0, min(1.0, (wall_x - location.x) / 140.0))
                    vertical = max(-1.0, min(1.0, (bait_y - location.y) / 180.0))
                    move = ((0.0, 0.0) if abs(wall_x - location.x) < 18.0 and abs(bait_y - location.y) < 25.0
                            else normal(horizontal, vertical))
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

                # A queued role cannot be selected directly. Spend the current
                # one-shot weapon through Fire when its successor is needed.
                # These floor-aimed shots are explicit policy drains, not kills.
                if ammo and reserve >= 0 and (nearest is None or nearest['distance'] >= 210.0):
                    if reserve == 2 and kind in (0, 1):
                        sniper_range = float(current_gun.get_editor_property('SniperRange')) - 90.0
                        heavy_ahead = [row for row in living if row['kind'] == 3
                                       and row['point'].y > location.y and row['distance'] < sniper_range]
                        if heavy_ahead:
                            target = None
                            drain_reason = 'promote_queued_sniper_for_heavy'
                            decision = drain_reason
                            move = (0.0, 0.0)
                    elif reserve == 3 and kind != 3:
                        radius = float(current_gun.get_editor_property('BlastRadius'))
                        rocket_range = float(current_gun.get_editor_property('RocketRange')) - 90.0
                        core_groups = [row for row in living if row['point'].y > 2700.0
                                       and row['distance'] < rocket_range and sum(
                                           (other['point'] - row['point']).length() <= radius - 25.0
                                           for other in living) >= 2]
                        if core_groups:
                            target = None
                            drain_reason = 'promote_queued_rpg_for_group'
                            decision = drain_reason
                            move = (0.0, 0.0)
                    if complete and not living and not state['drained_after_clear']:
                        target = None
                        drain_reason = 'after_clear'
                        decision = 'observe_fifo_promotion_after_clear'
                        move = (0.0, 0.0)

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
                        if bait_active and row['kind'] == 1 and location.x > 485.0:
                            # At the right wall, an inward/backward dodge would
                            # run into the pursuing Basic. Escape along the wall
                            # after the charge locks instead of abandoning bait.
                            basics = [other for other in living if other['kind'] == 0]
                            wall_sides = [normal(-0.08, 1.0), normal(-0.08, -1.0)]
                            def bait_escape_score(side):
                                end_y = location.y + side[1] * 190.0
                                end_x = location.x + side[0] * 190.0
                                contact_space = min((math.hypot(end_x - other['point'].x,
                                                               end_y - other['point'].y) for other in basics), default=500.0)
                                bay_penalty = max(900.0 - end_y, end_y - 1330.0, 0.0) * 2.0
                                lateral_exit = abs(lateral + (side[0] * -direction.y + side[1] * direction.x) * 190.0)
                                return min(contact_space, 500.0) + lateral_exit - bay_penalty
                            evade = max(wall_sides, key=bait_escape_score)
                            if (state['bait_escape_actor'] != row['id']
                                    or state['bait_escape_until'] <= game_time):
                                min_y, max_y = state['bait_wall_limits']
                                goal_y = max(min_y, min(max_y, location.y + evade[1] * 190.0))
                                state['bait_escape_goal'] = (state['bait_wall_x'], goal_y)
                                state['bait_escape_actor'] = row['id']
                                deadline = float(actor.get_editor_property('StateEndTime'))
                                if row['ai'] == 1:
                                    deadline += float(actor.get_editor_property('ChargeDuration'))
                                state['bait_escape_until'] = deadline + 0.2
                                event('committed_bait_escape', enemy=row['id'], goal=[round(state['bait_wall_x'], 2), round(goal_y, 2)],
                                      until_game_time=round(state['bait_escape_until'], 3))
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
                if (bait_active and state['bait_escape_goal'] is not None
                        and game_time < state['bait_escape_until']
                        and (threat is None or threat['reason'] == 'committed_charge')):
                    goal_x, goal_y = state['bait_escape_goal']
                    dx, dy = goal_x - location.x, goal_y - location.y
                    move = (0.0, 0.0) if abs(dx) < 18.0 and abs(dy) < 20.0 else normal(dx / 140.0, dy / 140.0)
                    decision = 'persist_committed_bait_escape'
                # Keep the controller inside the central walkable lane. Cover
                # can still physically stop movement; the policy never moves
                # the actor through it or deletes the obstacle.
                boundary = state['bait_wall_x'] if bait_active else 490.0
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

                if ammo and (target or drain_reason) and not pawn.get_editor_property('Dodging') and wall_time - state['last_fire'] > 0.7:
                    if target:
                        point = target['point']
                        speed = 2200.0 if kind in (0, 1) else float(current_gun.get_editor_property('RocketSpeed')) if kind == 3 else 0.0
                        travel = min(target['distance'] / speed, 1.5) if speed else 0.0
                        lead = target['velocity'] * travel
                        point = unreal.Vector(point.x + lead.x, point.y + lead.y, 50.0)
                    else:
                        point = unreal.Vector(-350.0 if location.x >= 0.0 else 350.0, location.y + 40.0, 50.0)
                    intended_miss = policy == 'miss' and not state['intentionally_missed'] and target is not None
                    if intended_miss:
                        point = location + unreal.Vector(-450.0, 150.0, -92.0)
                    pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
                    viewport = controller.get_viewport_size()
                    if (pixel is not None and 0 <= pixel.x < viewport[0] and 0 <= pixel.y < viewport[1]):
                        controller.set_mouse_location(round(pixel.x), round(pixel.y))
                        aim_key = (state['epoch'], slots['weapon_actor'], target['id'] if target else drain_reason)
                        if state['aim_key'] != aim_key:
                            state['aim_key'] = aim_key
                            state['aim_started'] = game_time
                        elif game_time - state['aim_started'] >= 0.12 and controller.deproject_mouse_position_to_world() is not None:
                            # Cache identities and target collision before Fire:
                            # successful Fire destroys this actor and may kill
                            # the Sniper target synchronously.
                            fired_kind, fired_actor = kind, slots['weapon_actor']
                            inventory_before = dict(slots)
                            projectiles_before = set(projectiles(world))
                            evidence = {'kind': fired_kind, 'fired_weapon': fired_actor,
                                        'inventory_before': inventory_before,
                                        'target_kind': target['kind'] if target else None,
                                        'target': target['id'] if target else None,
                                        'target_position': xyz(target['point']) if target else None,
                                        'aim_point': xyz(point),
                                        'target_velocity': xyz(target['velocity']) if target else None,
                                        'distance': round(target['distance'], 1) if target else None,
                                        'player': xyz(location), 'decision': decision,
                                        'intended_miss': intended_miss,
                                        'intended_drain': drain_reason is not None, 'drain_reason': drain_reason}
                            if fired_kind == 2 and target:
                                evidence['target_visibility_components'] = [{
                                    'component': component.get_name(),
                                    'enabled': str(component.get_collision_enabled()),
                                    'visibility': str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)),
                                } for component in target['actor'].get_components_by_class(unreal.PrimitiveComponent)]
                            current_gun.call_method('Fire')
                            discarded = not valid(current_gun)
                            _, after = inventory(pawn)
                            # A live reference is only read on a rejected Fire;
                            # promotion is read from the Character, never from
                            # the old weapon after its destruction.
                            old_ammo = 0 if discarded else int(current_gun.get_editor_property('Ammo'))
                            consumed = discarded or old_ammo == 0
                            evidence.update({'spent_weapon_destroyed': discarded,
                                             'ammo_after': old_ammo,
                                             'ammo_after_source': 'discarded actor' if discarded else 'live fired actor',
                                             'inventory_after': after,
                                             'current_after_kind': after['weapon'],
                                             'reserve_before': inventory_before['queued_kind'],
                                             'reserve_after': after['queued_kind']})
                            state['last_fire'] = wall_time
                            state['aim_key'] = None
                            try:
                                spawned = [actor for identity, actor in projectiles(world).items()
                                           if identity not in projectiles_before]
                                evidence['spawned_projectiles'] = [projectile_evidence(actor) for actor in spawned]
                                primary = next((actor for actor in spawned
                                                if int(actor.get_editor_property('WeaponKind')) == fired_kind), None)
                                if primary:
                                    origin = primary.get_actor_location()
                                    rotation = primary.get_actor_rotation()
                                    yaw, pitch = math.radians(rotation.yaw), math.radians(rotation.pitch)
                                    shot_direction = unreal.Vector(math.cos(pitch) * math.cos(yaw),
                                                                   math.cos(pitch) * math.sin(yaw), math.sin(pitch))
                                    evidence['shot_origin'] = xyz(origin)
                                    evidence['shot_rotation'] = [round(rotation.pitch, 2), round(rotation.yaw, 2), round(rotation.roll, 2)]
                                    evidence['shot_geometry_source'] = 'new live production projectile'
                                    if target:
                                        target_delta = target['point'] - origin
                                        along = target_delta.x * shot_direction.x + target_delta.y * shot_direction.y + target_delta.z * shot_direction.z
                                        evidence['target_distance_from_shot_line'] = round(math.sqrt(max(target_delta.length() ** 2 - along ** 2, 0.0)), 2)
                                evidence['synchronous_defeats'] = [row['id'] for row in living
                                                                 if valid(row['actor']) and row['actor'].get_editor_property('Dead')]
                            except Exception as diagnostic_error:
                                evidence['shot_diagnostic_error'] = str(diagnostic_error)
                            event('fire' if consumed else 'fire_rejected', **evidence)
                            if consumed:
                                state['last_gun'] = after['weapon_actor']
                                state['last_reserve'] = after['queued_kind']
                                if inventory_before['queued_kind'] >= 0 and after['weapon_actor'] != fired_actor and after['weapon_actor']:
                                    event('promoted_weapon', kind=after['weapon'], ammo=after['ammo'],
                                          expected_kind=inventory_before['queued_kind'],
                                          from_kind=fired_kind, weapon_actor=after['weapon_actor'],
                                          queued_kind=after['queued_kind'], player=xyz(location))
                                if drain_reason == 'after_clear':
                                    state['drained_after_clear'] = True
                                if intended_miss:
                                    state['intentionally_missed'] = True
                                    bait = choose_solid_bait(world, pawn, target['point'].y - 450.0)
                                    event('miss_bait_goal', **bait,
                                          aimed_target=target['id'], aimed_target_kind=target['kind'])
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
                _, sample_inventory = inventory(pawn)
                report['samples'].append({
                    'at': round(wall_time, 3), 'game_time': round(game_time, 3), 'epoch': state['epoch'],
                    'player': xyz(location), 'dead': dead, **sample_inventory,
                    'progress': round(progress_value, 4), 'stage': current_stage, 'complete': complete,
                    'dodging': bool(pawn.get_editor_property('Dodging')), 'decision': decision,
                    'enemies': [{'kind': row['kind'], 'id': row['id'], 'position': xyz(row['point']),
                                 'state': row['ai'], 'remaining': round(row['remaining'], 3), 'charge': row['charge']}
                                for row in living if valid(row['actor']) and not row['actor'].get_editor_property('Dead')],
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
        progress = unreal.load_asset('/Game/Runner/BP_RunnerProgress')
        bullet = unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile')
        assert enemy and pickup and progress and bullet, 'Existing combat assets are unavailable'
        enemy_class = enemy.generated_class()
        pickup_class = pickup.generated_class()
        progress_class = progress.generated_class()
        bullet_class = bullet.generated_class()
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
