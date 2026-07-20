from __future__ import annotations

from collections import Counter

from .catalog import ATTACK_MODELS
from .entities import AttackProjectile, DefenseProjectile, DefenseWeapon
from .game import Game
from .settings import GROUND_Y


class BalancedGame(Game):
    """Fire-control variant that distributes separate targets across batteries.

    Rules:
    - One target still belongs to only one launcher.
    - A launcher cannot own more targets than its fire-control channels.
    - A cooling launcher cannot receive a new target.
    - Underused suitable launchers receive a strong load-balancing bonus.
    """

    def owner_loads(self) -> Counter[str]:
        return Counter(self.target_owners.values())

    def select_owner(
        self,
        target: AttackProjectile,
        radar_accuracy: float,
        owner_loads: Counter[str] | None = None,
    ) -> tuple[DefenseWeapon, object] | None:
        loads = owner_loads if owner_loads is not None else self.owner_loads()
        options: list[tuple[float, DefenseWeapon, object]] = []
        target_value = (
            target.unit_cost
            + target.child_warheads * ATTACK_MODELS["CHILD"]["unit_cost"]
        )
        distance_to_base = target.position.distance_to(self.base.position)
        urgency = 1.0 + max(0.0, 1.0 - distance_to_base / 1400.0) * 2.6

        for weapon in self.weapons:
            # Do not reserve a target for a launcher that cannot fire now.
            if not weapon.ready:
                continue

            active_locks = loads.get(weapon.key, 0)
            channel_limit = max(1, weapon.fire_control_channels)
            if active_locks >= channel_limit:
                continue

            solution = weapon.find_intercept(target)
            if solution is None or solution.position.y > GROUND_Y + 20:
                continue

            probability = weapon.estimated_pk(target, radar_accuracy)
            fit = self.weapon_fit(weapon, target)
            utilization = active_locks / channel_limit

            # Price still matters, but utilization is more important. This prevents
            # the two cheap CIWS batteries from winning every target assignment.
            load_penalty = 1.0 + utilization * 10.0
            history_penalty = 1.0 + weapon.fired_count * 0.004
            score = (
                target_value * probability * fit * urgency
                / max(1.0, weapon.unit_cost * load_penalty * history_penalty)
            )
            options.append((score, weapon, solution))

        if not options:
            return None
        _, weapon, solution = max(options, key=lambda item: item[0])
        return weapon, solution

    def update_defense_ai(self) -> None:
        if not self.current_tracks:
            return

        commitments = self.active_commitments()
        radar_accuracy = self.radar.accuracy_factor()
        owner_loads = self.owner_loads()
        tracks = sorted(self.current_tracks, key=self.nearest_target_priority)

        for target in tracks:
            if not target.alive:
                continue

            # A missile already in flight is the only active commitment allowed.
            if commitments.get(target.uid):
                self.prevented_duplicate_shots += 1
                continue

            owner_key = self.target_owners.get(target.uid)
            owner: DefenseWeapon | None = None
            solution = None

            if owner_key is not None:
                if self.owner_can_defend(owner_key, target):
                    owner = self.weapon_by_key(owner_key)
                    if owner is not None:
                        solution = owner.find_intercept(target)
                else:
                    self.target_owners.pop(target.uid, None)
                    owner_loads[owner_key] = max(
                        0, owner_loads.get(owner_key, 0) - 1
                    )
                    self.takeovers += 1
                    owner_key = None

            if owner_key is None:
                selected = self.select_owner(target, radar_accuracy, owner_loads)
                if selected is None:
                    continue
                owner, solution = selected
                self.target_owners[target.uid] = owner.key
                owner_loads[owner.key] += 1

            if owner is None or solution is None:
                continue

            # Existing ownership is retained during reload, but that battery's
            # channel remains occupied and other batteries receive other targets.
            if not owner.ready:
                continue

            projectile: DefenseProjectile = owner.fire(
                solution, target, radar_accuracy
            )
            self.defense_projectiles.append(projectile)
            commitments[target.uid] = [projectile]
            self.defense_counts[owner.key] += 1
            self.defense_cost += owner.unit_cost
            owner.target_id = target.uid
