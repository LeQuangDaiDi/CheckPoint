from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

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

    @property
    def total_projectiles(self) -> int:
        return self.projectiles_per_burst * self.burst_count


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.small_font = pygame.font.SysFont("consolas", 15)
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
                "Precision", Vector(WIDTH * 0.20, GROUND_Y), 720, 30, 0.992, 0.20,
                1250, 160, WeaponRole.PRECISION, fire_control_channels=2, salvo_size=1
            ),
            DefenseWeapon(
                "Flak", Vector(WIDTH * 0.38, GROUND_Y), 420, 92, 0.90, 0.62,
                1050, 105, WeaponRole.AREA, fire_control_channels=1, salvo_size=1
            ),
            DefenseWeapon(
                "Rapid-A", Vector(WIDTH * 0.64, GROUND_Y), 610, 38, 0.94, 0.105,
                1120, 300, WeaponRole.RAPID, fire_control_channels=4, salvo_size=2
            ),
            DefenseWeapon(
                "Rapid-B", Vector(WIDTH * 0.80, GROUND_Y), 640, 34, 0.955, 0.12,
                1150, 260, WeaponRole.RAPID, fire_control_channels=4, salvo_size=2
            ),
        ]
        self.wave = 0
        self.score = 0
        self.destroyed = 0
        self.spawned = 0
        self.children_spawned = 0
        self.wave_timer = 1.0
        self.spawn_queue: list[tuple[float, int, TrajectoryType]] = []
        self.elapsed = 0.0
        self.paused = False
        self.auto_defense = True
        self.current_tracks: list[AttackProjectile] = []

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
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
                    self.schedule_wave(force=True)

    def update(self, dt: float) -> None:
        self.elapsed += dt
        self.wave_timer -= dt
        if self.wave_timer <= 0 and not self.spawn_queue:
            self.schedule_wave()

        self.update_spawn_queue(dt)
        spawned_children: list[AttackProjectile] = []

        for projectile in self.attack_projectiles:
            projectile.update(dt)
            if projectile.should_split():
                children = projectile.create_child_warheads(GROUND_Y)
                spawned_children.extend(children)
                self.children_spawned += len(children)
                self.explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius * 0.65, defensive=False)
                )
                continue
            if projectile.position.y >= GROUND_Y:
                projectile.alive = False
                distance = projectile.position.distance_to(self.base.position)
                if distance <= projectile.explosion_radius + 76:
                    falloff = max(0.2, 1.0 - distance / (projectile.explosion_radius + 76))
                    self.base.take_damage(projectile.damage * falloff)
                self.explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius, defensive=False)
                )

        self.attack_projectiles.extend(spawned_children)
        self.current_tracks = self.radar.update(dt, self.attack_projectiles)

        if self.auto_defense:
            self.update_defense_ai(dt)
        else:
            for weapon in self.weapons:
                weapon.update(dt)

        new_explosions: list[Explosion] = []
        for projectile in self.defense_projectiles:
            if projectile.update(dt):
                new_explosions.append(Explosion(Vector(projectile.position), projectile.explosion_radius))
                self.apply_defense_explosion(projectile.position, projectile.explosion_radius)

        self.explosions.extend(new_explosions)
        for explosion in self.explosions:
            explosion.update(dt)

        self.attack_projectiles = [
            projectile for projectile in self.attack_projectiles
            if projectile.alive and projectile.position.y < HEIGHT + 100
        ]
        self.defense_projectiles = [projectile for projectile in self.defense_projectiles if projectile.alive]
        self.explosions = [explosion for explosion in self.explosions if explosion.alive]

    def schedule_wave(self, force: bool = False) -> None:
        if self.spawn_queue and not force:
            return
        self.wave += 1
        pattern = AttackPattern(
            projectiles_per_burst=min(2 + self.wave // 3, 7),
            burst_count=min(2 + self.wave // 4, 6),
            projectile_interval=max(0.045, 0.15 - self.wave * 0.004),
            burst_interval=max(0.28, 0.72 - self.wave * 0.018),
        )
        trajectory = random.choices(
            [TrajectoryType.LINEAR, TrajectoryType.CURVED, TrajectoryType.EVASIVE],
            weights=[max(2, 8 - self.wave), 3, max(1, self.wave // 2)],
        )[0]
        delay = 0.0
        for _burst in range(pattern.burst_count):
            for shot in range(pattern.projectiles_per_burst):
                self.spawn_queue.append((delay + shot * pattern.projectile_interval, self.wave, trajectory))
            delay += pattern.burst_interval
        self.wave_timer = max(2.8, 6.2 - self.wave * 0.08)

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
        target = self.base.position + Vector(random.uniform(-120, 120), 0)
        direction = target - start
        speed = min(340.0, 105.0 + wave * 8.0 + random.uniform(-12, 18))
        velocity = direction.normalize() * speed
        spread = max(2.0, 18.0 - wave * 0.45)
        velocity.rotate_ip(random.uniform(-spread, spread))

        mirv_chance = min(0.58, max(0.0, (wave - 2) * 0.055))
        child_warheads = random.randint(2, min(7, 2 + wave // 2)) if random.random() < mirv_chance else 0
        jammer_chance = min(0.48, max(0.0, (wave - 3) * 0.045))
        jammer_strength = random.uniform(0.18, 0.55) if random.random() < jammer_chance else 0.0

        self.attack_projectiles.append(
            AttackProjectile(
                position=start,
                velocity=velocity,
                damage=65 + wave * 7,
                explosion_radius=min(90, 28 + wave * 2.4),
                trajectory=trajectory,
                accuracy=min(0.98, 0.72 + wave * 0.012),
                child_warheads=child_warheads,
                split_altitude=random.uniform(230, 420),
                jammer_strength=jammer_strength,
            )
        )
        self.spawned += 1

    def update_defense_ai(self, dt: float) -> None:
        for weapon in self.weapons:
            weapon.update(dt)

        if not self.current_tracks:
            return

        reserved_shots: dict[int, int] = {}
        radar_accuracy = self.radar.accuracy_factor()

        for weapon in sorted(self.weapons, key=self.weapon_priority):
            if not weapon.ready:
                continue

            candidates: list[tuple[float, AttackProjectile, object, int]] = []
            for target in self.current_tracks:
                if not target.alive:
                    continue
                solution = weapon.find_intercept(target)
                if solution is None or solution.position.y > GROUND_Y + 20:
                    continue

                target_id = id(target)
                assigned = reserved_shots.get(target_id, 0)
                required = self.required_interceptors(target, weapon, radar_accuracy)
                if assigned >= required:
                    continue

                threat = self.calculate_threat(target)
                fit = self.weapon_fit(weapon, target)
                candidates.append((threat * fit / (1 + assigned * 0.8), target, solution, required))

            if not candidates:
                continue

            candidates.sort(key=lambda item: item[0], reverse=True)
            shot_budget = min(weapon.salvo_size, weapon.fire_control_channels, weapon.ammo)
            fired = 0
            last_target_id: int | None = None

            for _, target, solution, required in candidates:
                if fired >= shot_budget:
                    break
                target_id = id(target)
                available_need = required - reserved_shots.get(target_id, 0)
                if available_need <= 0:
                    continue

                self.defense_projectiles.append(weapon.fire(solution, radar_accuracy))
                reserved_shots[target_id] = reserved_shots.get(target_id, 0) + 1
                last_target_id = target_id
                fired += 1

                # Precision/area weapons concentrate fire; rapid weapons spread
                # their channels across separate child warheads.
                if weapon.role is not WeaponRole.RAPID:
                    break

            weapon.target_id = last_target_id

    @staticmethod
    def weapon_priority(weapon: DefenseWeapon) -> tuple[int, float]:
        role_order = {
            WeaponRole.PRECISION: 0,
            WeaponRole.AREA: 1,
            WeaponRole.RAPID: 2,
        }
        return role_order[weapon.role], weapon.reload_time

    def calculate_threat(self, target: AttackProjectile) -> float:
        time_to_impact = max(0.05, (GROUND_Y - target.position.y) / max(1.0, target.velocity.y))
        proximity = max(0.0, 1.0 - target.position.distance_to(self.base.position) / 1100.0)
        child_threat = target.child_warheads * 58.0
        jammer_threat = target.jammer_strength * 260.0
        maneuver = 1.35 if target.trajectory is TrajectoryType.EVASIVE else 1.0
        return (
            target.damage * 0.45
            + 190.0 / time_to_impact
            + target.speed * 0.18
            + proximity * 120.0
            + child_threat
            + jammer_threat
        ) * maneuver

    @staticmethod
    def weapon_fit(weapon: DefenseWeapon, target: AttackProjectile) -> float:
        fit = 1.0
        if target.child_warheads >= 3 and weapon.role is WeaponRole.PRECISION:
            fit *= 1.55
        if target.is_child and weapon.role is WeaponRole.RAPID:
            fit *= 1.75
        if target.jammer_strength > 0.25 and weapon.role is WeaponRole.PRECISION:
            fit *= 1.45
        if weapon.role is WeaponRole.AREA:
            fit *= 1.0 + min(1.2, weapon.explosion_radius / max(20.0, target.explosion_radius) * 0.18)
        if target.speed > 260 and weapon.projectile_speed < 500:
            fit *= 0.6
        return fit

    @staticmethod
    def required_interceptors(target: AttackProjectile, weapon: DefenseWeapon, radar_accuracy: float) -> int:
        effective_accuracy = max(0.1, weapon.accuracy * radar_accuracy)
        required = 1
        if effective_accuracy < 0.82:
            required += 1
        if target.trajectory is TrajectoryType.EVASIVE:
            required += 1
        if target.jammer_strength > 0.30:
            required += 1
        if target.child_warheads >= 4:
            required += 1
        if weapon.role is WeaponRole.AREA:
            required = max(1, required - 1)
        return min(3, required)

    def apply_defense_explosion(self, position: Vector, radius: float) -> None:
        for target in self.attack_projectiles:
            if target.alive and target.position.distance_to(position) <= radius + target.radius:
                target.alive = False
                self.destroyed += 1
                bonus = target.child_warheads * 30 + int(target.jammer_strength * 180)
                self.score += int(100 + target.speed * 0.5 + target.damage + bonus)

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self.draw_grid()
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
        if self.paused:
            self.draw_center_message("PAUSED", "SPACE to continue")
        elif not self.base.alive:
            self.draw_center_message("CHECKPOINT LOST", "Press R to restart")
        pygame.display.flip()

    def draw_grid(self) -> None:
        for x in range(0, WIDTH, 48):
            pygame.draw.line(self.screen, GRID, (x, 0), (x, GROUND_Y), 1)
        for y in range(0, GROUND_Y, 48):
            pygame.draw.line(self.screen, GRID, (0, y), (WIDTH, y), 1)

    def draw_hud(self) -> None:
        health_ratio = self.base.health / self.base.max_health
        pygame.draw.rect(self.screen, (28, 38, 52), (24, 22, 330, 25), border_radius=5)
        bar_color = SUCCESS if health_ratio > 0.55 else WARNING if health_ratio > 0.25 else DANGER
        pygame.draw.rect(
            self.screen, bar_color, (24, 22, int(330 * health_ratio), 25), border_radius=5
        )
        health_text = self.small_font.render(
            f"BASE {self.base.health:05.0f}/{self.base.max_health:.0f}", True, TEXT
        )
        self.screen.blit(health_text, (34, 26))

        lines = [
            f"Wave: {self.wave}",
            f"Score: {self.score}",
            f"Intercepted: {self.destroyed}/{self.spawned + self.children_spawned}",
            f"Hostiles: {len(self.attack_projectiles)}",
            f"Radar tracks: {self.radar.detected_count}/{self.radar.tracking_channels}",
            f"Jamming: {self.radar.jam_level * 100:04.1f}%",
            f"Auto defense: {'ON' if self.auto_defense else 'OFF'}",
        ]
        for index, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (24, 60 + index * 26))

        controls = "SPACE Pause   A Auto-defense   N Next wave   R Restart   ESC Exit"
        self.screen.blit(self.small_font.render(controls, True, MUTED_TEXT), (24, HEIGHT - 30))

        panel = pygame.Rect(WIDTH - 310, 15, 290, 112)
        pygame.draw.rect(self.screen, (14, 25, 42), panel, border_radius=7)
        pygame.draw.rect(self.screen, GRID, panel, 1, border_radius=7)
        for index, weapon in enumerate(self.weapons):
            status = "READY" if weapon.ready else f"{weapon.cooldown:.2f}s"
            text = f"{weapon.name:<10} {weapon.ammo:03d} {weapon.role.value:<9} {status}"
            self.screen.blit(
                self.small_font.render(text, True, TEXT),
                (WIDTH - 296, 24 + index * 23),
            )

    def draw_center_message(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        self.screen.blit(overlay, (0, 0))
        title_surface = self.large_font.render(title, True, ATTACK)
        subtitle_surface = self.font.render(subtitle, True, TEXT)
        self.screen.blit(title_surface, title_surface.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 24)))
        self.screen.blit(subtitle_surface, subtitle_surface.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 28)))
