from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

import pygame

from .catalog import ATTACK_MODELS, CURRENCY, DEFENSE_MODELS
from .entities import (
    AttackProjectile,
    Base,
    DefenseProjectile,
    DefenseWeapon,
    Explosion,
    RadarSystem,
    TrajectoryType,
    WeaponRole,
)
from .settings import (
    ATTACK,
    BACKGROUND,
    BASE_POSITION,
    DANGER,
    FPS,
    GRID,
    GROUND,
    GROUND_Y,
    HEIGHT,
    MUTED_TEXT,
    SUCCESS,
    TEXT,
    TITLE,
    WARNING,
    WIDTH,
)

Vector = pygame.Vector2


@dataclass(slots=True)
class AttackPattern:
    projectiles_per_burst: int = 2
    burst_count: int = 2
    projectile_interval: float = 0.12
    burst_interval: float = 0.65


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.large_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.running = True
        self.reset()

    def reset(self) -> None:
        self.base = Base(Vector(BASE_POSITION))
        self.radar = RadarSystem(Vector(WIDTH * 0.5, GROUND_Y - 12))
        self.attack_projectiles: list[AttackProjectile] = []
        self.defense_projectiles: list[DefenseProjectile] = []
        self.explosions: list[Explosion] = []
        self.weapons = [
            DefenseWeapon(
                "PRECISION", DEFENSE_MODELS["PRECISION"]["name"], Vector(WIDTH * .20, GROUND_Y),
                760, 34, .993, .28, 1280, 150, DEFENSE_MODELS["PRECISION"]["unit_cost"],
                WeaponRole.PRECISION, 2, 1,
            ),
            DefenseWeapon(
                "AREA", DEFENSE_MODELS["AREA"]["name"], Vector(WIDTH * .38, GROUND_Y),
                430, 104, .91, .66, 1080, 110, DEFENSE_MODELS["AREA"]["unit_cost"],
                WeaponRole.AREA, 1, 1,
            ),
            DefenseWeapon(
                "RAPID_A", DEFENSE_MODELS["RAPID_A"]["name"], Vector(WIDTH * .64, GROUND_Y),
                640, 40, .95, .12, 1140, 320, DEFENSE_MODELS["RAPID_A"]["unit_cost"],
                WeaponRole.RAPID, 4, 2,
            ),
            DefenseWeapon(
                "RAPID_B", DEFENSE_MODELS["RAPID_B"]["name"], Vector(WIDTH * .80, GROUND_Y),
                670, 36, .96, .14, 1170, 280, DEFENSE_MODELS["RAPID_B"]["unit_cost"],
                WeaponRole.RAPID, 4, 2,
            ),
        ]
        self.wave = self.score = self.destroyed = self.spawned = self.children_spawned = 0
        self.attack_cost = self.defense_cost = 0
        self.attack_counts: Counter[str] = Counter()
        self.defense_counts: Counter[str] = Counter()
        self.wave_timer = 1.0
        self.spawn_queue: list[tuple[float, int, TrajectoryType]] = []
        self.paused = False
        self.auto_defense = True
        self.show_details = False
        self.current_tracks: list[AttackProjectile] = []
        self.target_owners: dict[int, str] = {}
        self.takeovers = 0
        self.prevented_duplicate_shots = 0

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, .05)
            self.handle_events()
            if not self.paused and self.base.alive:
                self.update(dt)
            self.draw()
        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    self.reset()
                elif event.key == pygame.K_a:
                    self.auto_defense = not self.auto_defense
                elif event.key == pygame.K_n:
                    self.schedule_wave(True)
                elif event.key == pygame.K_d:
                    self.show_details = not self.show_details

    def update(self, dt: float) -> None:
        self.wave_timer -= dt
        if self.wave_timer <= 0 and not self.spawn_queue:
            self.schedule_wave()
        self.update_spawn_queue(dt)

        children: list[AttackProjectile] = []
        for projectile in self.attack_projectiles:
            projectile.update(dt)
            if projectile.should_split():
                spawned = projectile.create_child_warheads(GROUND_Y)
                children.extend(spawned)
                self.children_spawned += len(spawned)
                for child in spawned:
                    self.attack_counts[child.model_key] += 1
                    self.attack_cost += child.unit_cost
                self.explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius * .65, defensive=False)
                )
                self.target_owners.pop(projectile.uid, None)
                continue
            if projectile.position.y >= GROUND_Y:
                projectile.alive = False
                distance = projectile.position.distance_to(self.base.position)
                if distance <= projectile.explosion_radius + 76:
                    falloff = max(.2, 1 - distance / (projectile.explosion_radius + 76))
                    self.base.take_damage(projectile.damage * falloff)
                self.explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius, defensive=False)
                )
                self.target_owners.pop(projectile.uid, None)

        self.attack_projectiles.extend(children)
        self.current_tracks = self.radar.update(dt, self.attack_projectiles)

        for weapon in self.weapons:
            weapon.update(dt)
        if self.auto_defense:
            self.update_defense_ai()

        new_explosions: list[Explosion] = []
        for projectile in self.defense_projectiles:
            if projectile.update(dt):
                new_explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius)
                )
                self.apply_defense_explosion(projectile.position, projectile.explosion_radius)
        self.explosions.extend(new_explosions)
        for explosion in self.explosions:
            explosion.update(dt)

        self.attack_projectiles = [
            p for p in self.attack_projectiles if p.alive and p.position.y < HEIGHT + 100
        ]
        self.defense_projectiles = [p for p in self.defense_projectiles if p.alive]
        self.explosions = [e for e in self.explosions if e.alive]
        self.cleanup_target_owners()

    def schedule_wave(self, force: bool = False) -> None:
        if self.spawn_queue and not force:
            return
        self.wave += 1
        pattern = AttackPattern(
            min(2 + self.wave // 3, 7),
            min(2 + self.wave // 4, 6),
            max(.045, .15 - self.wave * .004),
            max(.28, .72 - self.wave * .018),
        )
        trajectory = random.choices(
            [TrajectoryType.LINEAR, TrajectoryType.CURVED, TrajectoryType.EVASIVE],
            weights=[max(2, 8 - self.wave), 3, max(1, self.wave // 2)],
        )[0]
        delay = 0.0
        for _ in range(pattern.burst_count):
            for shot in range(pattern.projectiles_per_burst):
                self.spawn_queue.append(
                    (delay + shot * pattern.projectile_interval, self.wave, trajectory)
                )
            delay += pattern.burst_interval
        self.wave_timer = max(2.8, 6.2 - self.wave * .08)

    def update_spawn_queue(self, dt: float) -> None:
        remaining: list[tuple[float, int, TrajectoryType]] = []
        for delay, wave, trajectory in self.spawn_queue:
            delay -= dt
            if delay <= 0:
                self.spawn_attack_projectile(wave, trajectory)
            else:
                remaining.append((delay, wave, trajectory))
        self.spawn_queue = remaining

    def spawn_attack_projectile(self, wave: int, trajectory: TrajectoryType) -> None:
        start = Vector(random.randint(70, WIDTH - 70), random.randint(25, 80))
        direction = self.base.position + Vector(random.uniform(-120, 120), 0) - start
        mirv = random.random() < min(.58, max(0, (wave - 2) * .055))
        jammer = random.random() < min(.48, max(0, (wave - 3) * .045))
        key = "MIRV_JAMMER" if mirv and jammer else "MIRV" if mirv else "JAMMER" if jammer else "STRIKER"
        model = ATTACK_MODELS[key]
        speed = min(340, 105 + wave * 8 + random.uniform(-12, 18)) * float(model["speed_factor"])
        velocity = direction.normalize() * speed
        spread = max(2, 18 - wave * .45)
        velocity.rotate_ip(random.uniform(-spread, spread))
        child_count = random.randint(2, min(7, 2 + wave // 2)) if mirv else 0
        projectile = AttackProjectile(
            start,
            velocity,
            (65 + wave * 7) * float(model["damage_factor"]),
            min(90, 28 + wave * 2.4),
            key,
            trajectory,
            min(.98, .72 + wave * .012),
            child_count,
            random.uniform(230, 420),
            random.uniform(.18, .55) if jammer else 0.0,
        )
        self.attack_projectiles.append(projectile)
        self.spawned += 1
        self.attack_counts[key] += 1
        self.attack_cost += projectile.unit_cost

    def active_commitments(self) -> dict[int, list[DefenseProjectile]]:
        result: dict[int, list[DefenseProjectile]] = {}
        for projectile in self.defense_projectiles:
            if projectile.alive:
                result.setdefault(projectile.target_uid, []).append(projectile)
        return result

    def weapon_by_key(self, key: str) -> DefenseWeapon | None:
        return next((weapon for weapon in self.weapons if weapon.key == key), None)

    def cleanup_target_owners(self) -> None:
        alive_uids = {target.uid for target in self.attack_projectiles if target.alive}
        for uid in list(self.target_owners):
            if uid not in alive_uids:
                self.target_owners.pop(uid, None)

    def owner_can_defend(self, owner_key: str, target: AttackProjectile) -> bool:
        owner = self.weapon_by_key(owner_key)
        if owner is None or owner.ammo <= 0:
            return False
        solution = owner.find_intercept(target)
        if solution is None or solution.position.y > GROUND_Y + 20:
            return False
        time_to_impact = max(.0, (GROUND_Y - target.position.y) / max(1.0, target.velocity.y))
        return owner.cooldown <= time_to_impact

    def select_owner(self, target: AttackProjectile, radar_accuracy: float) -> tuple[DefenseWeapon, object] | None:
        options: list[tuple[float, DefenseWeapon, object]] = []
        target_value = target.unit_cost + target.child_warheads * ATTACK_MODELS["CHILD"]["unit_cost"]
        for weapon in self.weapons:
            if weapon.ammo <= 0:
                continue
            solution = weapon.find_intercept(target)
            if solution is None or solution.position.y > GROUND_Y + 20:
                continue
            pk = weapon.estimated_pk(target, radar_accuracy)
            fit = self.weapon_fit(weapon, target)
            delay_penalty = 1.0 + weapon.cooldown * 2.0
            economy = (target_value * pk * fit) / max(1, weapon.unit_cost * delay_penalty)
            options.append((economy, weapon, solution))
        if not options:
            return None
        _, weapon, solution = max(options, key=lambda item: item[0])
        return weapon, solution

    def update_defense_ai(self) -> None:
        if not self.current_tracks:
            return

        commitments = self.active_commitments()
        radar_accuracy = self.radar.accuracy_factor()
        tracks = sorted(self.current_tracks, key=self.calculate_threat, reverse=True)

        for target in tracks:
            if not target.alive:
                continue

            active = commitments.get(target.uid, [])
            if active:
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
                    self.takeovers += 1
                    owner_key = None

            if owner_key is None:
                selected = self.select_owner(target, radar_accuracy)
                if selected is None:
                    continue
                owner, solution = selected
                self.target_owners[target.uid] = owner.key

            if owner is None or solution is None or not owner.ready:
                continue

            projectile = owner.fire(solution, target, radar_accuracy)
            self.defense_projectiles.append(projectile)
            commitments[target.uid] = [projectile]
            self.defense_counts[owner.key] += 1
            self.defense_cost += owner.unit_cost
            owner.target_id = target.uid

    def calculate_threat(self, target: AttackProjectile) -> float:
        time_to_impact = max(.05, (GROUND_Y - target.position.y) / max(1, target.velocity.y))
        return (
            target.damage * .45
            + 190 / time_to_impact
            + target.speed * .18
            + target.child_warheads * 58
            + target.jammer_strength * 260
        )

    @staticmethod
    def weapon_fit(weapon: DefenseWeapon, target: AttackProjectile) -> float:
        fit = 1.0
        if target.child_warheads >= 3:
            fit *= 1.6 if weapon.role is WeaponRole.PRECISION else .75
        if target.is_child:
            fit *= 1.8 if weapon.role is WeaponRole.RAPID else .75
        if target.jammer_strength > .25:
            fit *= 1.45 if weapon.role is WeaponRole.PRECISION else .85
        if weapon.role is WeaponRole.AREA and target.is_child:
            fit *= 1.25
        if target.speed > 260 and weapon.projectile_speed < 500:
            fit *= .6
        return fit

    def apply_defense_explosion(self, position: Vector, radius: float) -> None:
        for target in self.attack_projectiles:
            if target.alive and target.position.distance_to(position) <= radius + target.radius:
                target.alive = False
                self.target_owners.pop(target.uid, None)
                self.destroyed += 1
                self.score += int(
                    100
                    + target.speed * .5
                    + target.damage
                    + target.child_warheads * 30
                    + target.jammer_strength * 180
                )

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        for x in range(0, WIDTH, 48):
            pygame.draw.line(self.screen, GRID, (x, 0), (x, GROUND_Y), 1)
        for y in range(0, GROUND_Y, 48):
            pygame.draw.line(self.screen, GRID, (0, y), (WIDTH, y), 1)
        pygame.draw.rect(self.screen, GROUND, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        for explosion in self.explosions:
            explosion.draw(self.screen)
        for projectile in self.attack_projectiles:
            projectile.draw(self.screen)
        for projectile in self.defense_projectiles:
            projectile.draw(self.screen)
        for weapon in self.weapons:
            weapon.draw(self.screen)
        self.radar.draw(self.screen)
        self.base.draw(self.screen)
        self.draw_hud()
        if self.show_details:
            self.draw_detail_panel()
        if self.paused:
            self.draw_center_message("PAUSED", "SPACE to continue")
        elif not self.base.alive:
            self.draw_center_message("CHECKPOINT LOST", "Press R to restart")
        pygame.display.flip()

    def draw_hud(self) -> None:
        ratio = self.base.health / self.base.max_health
        pygame.draw.rect(self.screen, (28, 38, 52), (20, 18, 330, 25), border_radius=5)
        color = SUCCESS if ratio > .55 else WARNING if ratio > .25 else DANGER
        pygame.draw.rect(self.screen, color, (20, 18, int(330 * ratio), 25), border_radius=5)
        self.screen.blit(
            self.small_font.render(
                f"BASE {self.base.health:05.0f}/{self.base.max_health:.0f}", True, TEXT
            ),
            (30, 22),
        )

        total_attack = sum(self.attack_counts.values())
        total_defense = sum(self.defense_counts.values())
        saved_ratio = self.attack_cost / max(1, self.defense_cost)
        active_attack = len(self.attack_projectiles)
        active_defense = len(self.defense_projectiles)

        lines = [
            f"Wave {self.wave}   Score {self.score}",
            f"ATTACK MISSILES: launched {total_attack} | airborne {active_attack} | cost {CURRENCY}{self.attack_cost:,}",
            f"DEFENSE INTERCEPTORS: fired {total_defense} | airborne {active_defense} | cost {CURRENCY}{self.defense_cost:,}",
            f"Cost ratio A/D: {saved_ratio:.2f}x   Intercepted: {self.destroyed}/{self.spawned + self.children_spawned}",
            f"Radar: {self.radar.detected_count}/{self.radar.tracking_channels}   Jamming: {self.radar.jam_level * 100:.1f}%",
            f"Exclusive locks: {len(self.target_owners)}   Takeovers: {self.takeovers}   Auto: {'ON' if self.auto_defense else 'OFF'}",
        ]
        for index, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (20, 54 + index * 23))

        legend_y = 202
        pygame.draw.polygon(
            self.screen,
            ATTACK,
            [(25, legend_y - 6), (17, legend_y + 6), (33, legend_y + 6)],
        )
        self.screen.blit(
            self.small_font.render("ATTACK missile / warhead", True, ATTACK),
            (42, legend_y - 8),
        )
        pygame.draw.circle(self.screen, (89, 173, 255), (225, legend_y), 5)
        self.screen.blit(
            self.small_font.render("DEFENSE interceptor", True, (89, 173, 255)),
            (238, legend_y - 8),
        )

        controls = "D Details   SPACE Pause   A Auto   N Next wave   R Restart   ESC Exit"
        self.screen.blit(
            self.small_font.render(controls, True, MUTED_TEXT),
            (20, HEIGHT - 28),
        )

        panel = pygame.Rect(WIDTH - 390, 15, 370, 118)
        pygame.draw.rect(self.screen, (14, 25, 42), panel, border_radius=7)
        pygame.draw.rect(self.screen, GRID, panel, 1, border_radius=7)
        for index, weapon in enumerate(self.weapons):
            status = "READY" if weapon.ready else f"{weapon.cooldown:.2f}s"
            owned = sum(1 for key in self.target_owners.values() if key == weapon.key)
            text = (
                f"{weapon.name:<13} ammo {weapon.ammo:03d} "
                f"locks {owned:02d} ${weapon.unit_cost / 1_000_000:.2f}M {status}"
            )
            self.screen.blit(
                self.small_font.render(text, True, TEXT),
                (WIDTH - 378, 24 + index * 23),
            )

    def draw_detail_panel(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 9, 17, 232))
        self.screen.blit(overlay, (0, 0))
        self.screen.blit(
            self.large_font.render("MISSILE CLASSIFICATION & ECONOMY", True, TEXT),
            (55, 34),
        )
        x1, x2 = 55, 650
        self.screen.blit(self.font.render("ATTACK MISSILES / WARHEADS", True, ATTACK), (x1, 100))
        y = 130
        for key, model in ATTACK_MODELS.items():
            count = self.attack_counts[key]
            line = (
                f"{model['name']:<16} qty {count:03d}  "
                f"unit ${model['unit_cost'] / 1_000_000:.2f}M  "
                f"total ${count * model['unit_cost'] / 1_000_000:.2f}M"
            )
            self.screen.blit(self.small_font.render(line, True, TEXT), (x1, y))
            y += 25
            self.screen.blit(
                self.small_font.render(str(model["description"]), True, MUTED_TEXT),
                (x1 + 16, y),
            )
            y += 30

        self.screen.blit(self.font.render("DEFENSE INTERCEPTORS", True, (89, 173, 255)), (x2, 100))
        y = 130
        for weapon in self.weapons:
            count = self.defense_counts[weapon.key]
            model = DEFENSE_MODELS[weapon.key]
            owned = sum(1 for key in self.target_owners.values() if key == weapon.key)
            line = (
                f"{weapon.name:<16} fired {count:03d}  "
                f"unit ${weapon.unit_cost / 1_000_000:.2f}M  locks {owned:02d}"
            )
            self.screen.blit(self.small_font.render(line, True, TEXT), (x2, y))
            y += 23
            stats = (
                f"speed {weapon.projectile_speed:.0f}  accuracy {weapon.accuracy * 100:.1f}%  "
                f"radius {weapon.explosion_radius:.0f}  ammo {weapon.ammo}"
            )
            self.screen.blit(self.small_font.render(stats, True, TEXT), (x2 + 16, y))
            y += 22
            self.screen.blit(
                self.small_font.render(str(model["description"]), True, MUTED_TEXT),
                (x2 + 16, y),
            )
            y += 31

        cheaper = "DEFENSE" if self.defense_cost < self.attack_cost else "ATTACK"
        delta = abs(self.attack_cost - self.defense_cost)
        summary = (
            f"Cheaper side: {cheaper} | Difference: ${delta:,} | "
            f"Rule: one target = one launcher = one interceptor in flight | D to close"
        )
        self.screen.blit(self.font.render(summary, True, WARNING), (55, HEIGHT - 55))

    def draw_center_message(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        self.screen.blit(overlay, (0, 0))
        title_surface = self.large_font.render(title, True, ATTACK)
        subtitle_surface = self.font.render(subtitle, True, TEXT)
        self.screen.blit(
            title_surface,
            title_surface.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 24)),
        )
        self.screen.blit(
            subtitle_surface,
            subtitle_surface.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 28)),
        )
