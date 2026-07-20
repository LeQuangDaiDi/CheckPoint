from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum

import pygame

from .algorithms import InterceptSolution, solve_linear_intercept
from .settings import ATTACK, BASE_MAX_HEALTH, DEFENSE, DANGER, SUCCESS, WARNING

Vector = pygame.Vector2


class TrajectoryType(str, Enum):
    LINEAR = "linear"
    CURVED = "curved"
    EVASIVE = "evasive"


@dataclass(slots=True)
class AttackProjectile:
    position: Vector
    velocity: Vector
    damage: float
    explosion_radius: float
    trajectory: TrajectoryType = TrajectoryType.LINEAR
    accuracy: float = 1.0
    radius: int = 6
    alive: bool = True
    age: float = 0.0
    phase: float = field(default_factory=lambda: random.uniform(0.0, math.tau))

    @property
    def speed(self) -> float:
        return self.velocity.length()

    def predicted_velocity(self) -> Vector:
        return Vector(self.velocity)

    def update(self, dt: float) -> None:
        self.age += dt
        if self.trajectory is TrajectoryType.LINEAR:
            self.position += self.velocity * dt
        elif self.trajectory is TrajectoryType.CURVED:
            self.velocity.y += 18.0 * dt
            self.position += self.velocity * dt
        else:
            sideways = Vector(-self.velocity.y, self.velocity.x)
            if sideways.length_squared() > 0:
                sideways.scale_to_length(math.sin(self.age * 5.5 + self.phase) * 32.0)
            self.position += (self.velocity + sideways) * dt

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.circle(surface, ATTACK, self.position, self.radius)
        tail = self.position - self.velocity.normalize() * 18 if self.velocity.length_squared() else self.position
        pygame.draw.line(surface, (255, 191, 160), tail, self.position, 2)


@dataclass(slots=True)
class DefenseProjectile:
    position: Vector
    target_point: Vector
    speed: float
    explosion_radius: float
    damage: float
    radius: int = 4
    alive: bool = True

    def update(self, dt: float) -> bool:
        delta = self.target_point - self.position
        distance = delta.length()
        step = self.speed * dt
        if distance <= step or distance <= 4:
            self.position = Vector(self.target_point)
            self.alive = False
            return True
        self.position += delta.normalize() * step
        return False

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.line(surface, DEFENSE, self.position, self.target_point, 1)
        pygame.draw.circle(surface, DEFENSE, self.position, self.radius)


@dataclass(slots=True)
class Explosion:
    position: Vector
    max_radius: float
    duration: float = 0.35
    age: float = 0.0
    defensive: bool = True

    @property
    def alive(self) -> bool:
        return self.age < self.duration

    @property
    def current_radius(self) -> float:
        progress = min(1.0, self.age / self.duration)
        return self.max_radius * math.sin(progress * math.pi / 2)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:
        color = SUCCESS if self.defensive else DANGER
        pygame.draw.circle(surface, color, self.position, int(self.current_radius), 3)


@dataclass(slots=True)
class Base:
    position: Vector
    max_health: float = BASE_MAX_HEALTH
    health: float = BASE_MAX_HEALTH

    @property
    def alive(self) -> bool:
        return self.health > 0

    def take_damage(self, damage: float) -> None:
        self.health = max(0.0, self.health - damage)

    def draw(self, surface: pygame.Surface) -> None:
        x, y = int(self.position.x), int(self.position.y)
        pygame.draw.rect(surface, (84, 112, 139), (x - 58, y - 28, 116, 42), border_radius=6)
        pygame.draw.polygon(surface, WARNING, [(x - 68, y - 28), (x, y - 58), (x + 68, y - 28)])
        pygame.draw.rect(surface, (12, 20, 31), (x - 46, y - 20, 92, 24), border_radius=4)


@dataclass(slots=True)
class DefenseWeapon:
    name: str
    position: Vector
    projectile_speed: float
    explosion_radius: float
    accuracy: float
    reload_time: float
    detection_range: float
    ammo: int
    shot_damage: float = 9999
    cooldown: float = 0.0
    target_id: int | None = None

    @property
    def ready(self) -> bool:
        return self.cooldown <= 0 and self.ammo > 0

    def update(self, dt: float) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)

    def find_intercept(self, target: AttackProjectile) -> InterceptSolution | None:
        if self.position.distance_to(target.position) > self.detection_range:
            return None
        return solve_linear_intercept(
            self.position,
            target.position,
            target.predicted_velocity(),
            self.projectile_speed,
        )

    def fire(self, solution: InterceptSolution) -> DefenseProjectile:
        error_limit = (1.0 - self.accuracy) * 55.0
        error = Vector(random.uniform(-error_limit, error_limit), random.uniform(-error_limit, error_limit))
        self.cooldown = self.reload_time
        self.ammo -= 1
        return DefenseProjectile(
            position=Vector(self.position),
            target_point=solution.position + error,
            speed=self.projectile_speed,
            explosion_radius=self.explosion_radius,
            damage=self.shot_damage,
        )

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.circle(surface, (43, 73, 102), self.position, 23)
        pygame.draw.circle(surface, DEFENSE, self.position, 16, 3)
        pygame.draw.line(surface, DEFENSE, self.position, self.position + Vector(0, -34), 6)
