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
    TrajectoryType,
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
        self.attack_projectiles: list[AttackProjectile] = []
        self.defense_projectiles: list[DefenseProjectile] = []
        self.explosions: list[Explosion] = []
        self.weapons = [
            DefenseWeapon("Precision", Vector(WIDTH * 0.28, GROUND_Y), 460, 35, 0.97, 0.24, 980, 180),
            DefenseWeapon("Flak", Vector(WIDTH * 0.50, GROUND_Y), 330, 82, 0.88, 0.72, 900, 95),
            DefenseWeapon("Interceptor", Vector(WIDTH * 0.72, GROUND_Y), 560, 50, 0.93, 0.48, 1100, 120),
        ]
        self.wave = 0
        self.score = 0
        self.destroyed = 0
        self.spawned = 0
        self.wave_timer = 1.0
        self.spawn_queue: list[tuple[float, int, TrajectoryType]] = []
        self.elapsed = 0.0
        self.paused = False
        self.auto_defense = True

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

        for projectile in self.attack_projectiles:
            projectile.update(dt)
            if projectile.position.y >= GROUND_Y:
                projectile.alive = False
                distance = projectile.position.distance_to(self.base.position)
                if distance <= projectile.explosion_radius + 76:
                    falloff = max(0.2, 1.0 - distance / (projectile.explosion_radius + 76))
                    self.base.take_damage(projectile.damage * falloff)
                self.explosions.append(
                    Explosion(Vector(projectile.position), projectile.explosion_radius, defensive=False)
                )

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
            projectile
            for projectile in self.attack_projectiles
            if projectile.alive and projectile.position.y < HEIGHT + 100
        ]
        self.defense_projectiles = [projectile for projectile in self.defense_projectiles if projectile.alive]
        self.explosions = [explosion for explosion in self.explosions if explosion.alive]

    def schedule_wave(self, force: bool = False) -> None:
        if self.spawn_queue and not force:
            return
        self.wave += 1
        pattern = AttackPattern(
            projectiles_per_burst=min(2 + self.wave // 3, 6),
            burst_count=min(2 + self.wave // 4, 5),
            projectile_interval=max(0.06, 0.15 - self.wave * 0.004),
            burst_interval=max(0.32, 0.72 - self.wave * 0.018),
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
        speed = min(300.0, 105.0 + wave * 8.0 + random.uniform(-12, 18))
        velocity = direction.normalize() * speed
        spread = max(2.0, 18.0 - wave * 0.45)
        velocity.rotate_ip(random.uniform(-spread, spread))
        self.attack_projectiles.append(
            AttackProjectile(
                position=start,
                velocity=velocity,
                damage=65 + wave * 7,
                explosion_radius=min(90, 28 + wave * 2.4),
                trajectory=trajectory,
                accuracy=min(0.98, 0.72 + wave * 0.012),
            )
        )
        self.spawned += 1

    def update_defense_ai(self, dt: float) -> None:
        reserved_targets = {
            weapon.target_id
            for weapon in self.weapons
            if weapon.target_id is not None and weapon.cooldown > 0
        }
        for weapon in self.weapons:
            weapon.update(dt)
            if not weapon.ready:
                continue

            candidates: list[tuple[float, AttackProjectile, object]] = []
            for target in self.attack_projectiles:
                target_id = id(target)
                solution = weapon.find_intercept(target)
                if solution is None or solution.position.y > GROUND_Y + 20:
                    continue
                time_to_impact = max(
                    0.05,
                    (GROUND_Y - target.position.y) / max(1.0, target.velocity.y),
                )
                proximity = max(
                    0.0,
                    1.0 - target.position.distance_to(self.base.position) / 1100.0,
                )
                trajectory_bonus = 1.35 if target.trajectory is TrajectoryType.EVASIVE else 1.0
                reservation_penalty = 0.38 if target_id in reserved_targets else 1.0
                threat = (
                    target.damage * 0.45
                    + 180.0 / time_to_impact
                    + target.speed * 0.18
                    + proximity * 120.0
                ) * trajectory_bonus * reservation_penalty
                radius_fit = 1.0 + min(
                    1.2,
                    weapon.explosion_radius / max(20.0, target.explosion_radius) * 0.18,
                )
                candidates.append((threat * radius_fit, target, solution))

            if not candidates:
                continue
            _, target, solution = max(candidates, key=lambda item: item[0])
            self.defense_projectiles.append(weapon.fire(solution))
            weapon.target_id = id(target)
            reserved_targets.add(id(target))

    def apply_defense_explosion(self, position: Vector, radius: float) -> None:
        for target in self.attack_projectiles:
            if target.alive and target.position.distance_to(position) <= radius + target.radius:
                target.alive = False
                self.destroyed += 1
                self.score += int(100 + target.speed * 0.5 + target.damage)

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
            self.screen,
            bar_color,
            (24, 22, int(330 * health_ratio), 25),
            border_radius=5,
        )
        health_text = self.small_font.render(
            f"BASE {self.base.health:05.0f}/{self.base.max_health:.0f}",
            True,
            TEXT,
        )
        self.screen.blit(health_text, (34, 26))

        lines = [
            f"Wave: {self.wave}",
            f"Score: {self.score}",
            f"Intercepted: {self.destroyed}/{self.spawned}",
            f"Hostiles: {len(self.attack_projectiles)}",
            f"Auto defense: {'ON' if self.auto_defense else 'OFF'}",
        ]
        for index, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (24, 60 + index * 26))

        controls = "SPACE Pause   A Auto-defense   N Next wave   R Restart   ESC Exit"
        self.screen.blit(
            self.small_font.render(controls, True, MUTED_TEXT),
            (24, HEIGHT - 30),
        )

        panel = pygame.Rect(WIDTH - 275, 15, 255, 86)
        pygame.draw.rect(self.screen, (14, 25, 42), panel, border_radius=7)
        pygame.draw.rect(self.screen, GRID, panel, 1, border_radius=7)
        for index, weapon in enumerate(self.weapons):
            status = "READY" if weapon.ready else f"{weapon.cooldown:.1f}s"
            text = f"{weapon.name:<11} {weapon.ammo:03d}  {status}"
            self.screen.blit(
                self.small_font.render(text, True, TEXT),
                (WIDTH - 260, 24 + index * 23),
            )

    def draw_center_message(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 155))
        self.screen.blit(overlay, (0, 0))
        title_image = self.large_font.render(title, True, ATTACK)
        subtitle_image = self.font.render(subtitle, True, TEXT)
        self.screen.blit(
            title_image,
            title_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 25)),
        )
        self.screen.blit(
            subtitle_image,
            subtitle_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 28)),
        )
