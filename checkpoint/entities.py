from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum

import pygame

from .algorithms import InterceptSolution, solve_linear_intercept
from .catalog import ATTACK_MODELS
from .settings import ATTACK, BASE_MAX_HEALTH, DEFENSE, DANGER, SUCCESS, WARNING

Vector = pygame.Vector2


class TrajectoryType(str, Enum):
    LINEAR = "linear"
    CURVED = "curved"
    EVASIVE = "evasive"


class WeaponRole(str, Enum):
    PRECISION = "precision"
    AREA = "area"
    RAPID = "rapid"


@dataclass(slots=True)
class AttackProjectile:
    position: Vector
    velocity: Vector
    damage: float
    explosion_radius: float
    model_key: str = "STRIKER"
    trajectory: TrajectoryType = TrajectoryType.LINEAR
    accuracy: float = 1.0
    child_warheads: int = 0
    split_altitude: float = 0.0
    jammer_strength: float = 0.0
    is_child: bool = False
    radius: int = 6
    alive: bool = True
    age: float = 0.0
    split_done: bool = False
    uid: int = field(default_factory=lambda: random.getrandbits(60))
    phase: float = field(default_factory=lambda: random.uniform(0.0, math.tau))

    @property
    def speed(self) -> float:
        return self.velocity.length()

    @property
    def model(self) -> dict:
        return ATTACK_MODELS[self.model_key]

    @property
    def name(self) -> str:
        return str(self.model["name"])

    @property
    def unit_cost(self) -> int:
        return int(self.model["unit_cost"])

    def predicted_velocity(self) -> Vector:
        return Vector(self.velocity)

    def should_split(self) -> bool:
        return self.alive and not self.split_done and self.child_warheads > 0 and self.position.y >= self.split_altitude

    def create_child_warheads(self, target_y: float) -> list["AttackProjectile"]:
        self.split_done = True
        self.alive = False
        children: list[AttackProjectile] = []
        base_direction = Vector(self.velocity) if self.velocity.length_squared() else Vector(0, 1)
        spread = min(42.0, 12.0 + self.child_warheads * 3.5)
        child_model = ATTACK_MODELS["CHILD"]
        for index in range(self.child_warheads):
            factor = 0.5 if self.child_warheads == 1 else index / (self.child_warheads - 1)
            angle = -spread / 2 + spread * factor + random.uniform(-3.5, 3.5)
            velocity = base_direction.rotate(angle)
            velocity.scale_to_length(self.speed * random.uniform(0.92, 1.12) * float(child_model["speed_factor"]))
            children.append(
                AttackProjectile(
                    position=Vector(self.position),
                    velocity=velocity,
                    damage=self.damage * float(child_model["damage_factor"]),
                    explosion_radius=max(18.0, self.explosion_radius * 0.55),
                    model_key="CHILD",
                    trajectory=random.choice((TrajectoryType.LINEAR, TrajectoryType.EVASIVE)),
                    accuracy=max(0.6, self.accuracy - 0.08),
                    split_altitude=target_y,
                    jammer_strength=self.jammer_strength * 0.25,
                    is_child=True,
                    radius=4,
                )
            )
        return children

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
        color = (255, 120, 70) if self.is_child else ATTACK
        pygame.draw.circle(surface, color, self.position, self.radius)
        if self.jammer_strength > 0.05:
            pulse = int(10 + 5 * (1 + math.sin(self.age * 8)))
            pygame.draw.circle(surface, (187, 105, 255), self.position, pulse, 1)
        tail = self.position - self.velocity.normalize() * 18 if self.velocity.length_squared() else self.position
        pygame.draw.line(surface, (255, 191, 160), tail, self.position, 2)


@dataclass(slots=True)
class DefenseProjectile:
    position: Vector
    target_point: Vector
    speed: float
    explosion_radius: float
    damage: float
    target_uid: int
    weapon_key: str
    unit_cost: int
    estimated_pk: float
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
        pygame.draw.circle(surface, SUCCESS if self.defensive else DANGER, self.position, int(self.current_radius), 3)


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
class RadarSystem:
    position: Vector
    range: float = 1250.0
    tracking_channels: int = 24
    processing_rate: float = 12.0
    eccm_strength: float = 0.72
    scan_phase: float = 0.0
    detected_count: int = 0
    jam_level: float = 0.0

    def update(self, dt: float, targets: list[AttackProjectile]) -> list[AttackProjectile]:
        self.scan_phase = (self.scan_phase + dt * self.processing_rate) % math.tau
        nearby = [t for t in targets if t.alive and self.position.distance_to(t.position) <= self.range]
        raw_jam = sum(t.jammer_strength * max(0.0, 1.0 - self.position.distance_to(t.position) / self.range) for t in nearby)
        self.jam_level = min(0.85, raw_jam * (1.0 - self.eccm_strength))
        capacity = max(1, int(self.tracking_channels * (1.0 - self.jam_level * 0.65)))
        nearby.sort(key=lambda t: t.position.y, reverse=True)
        tracks = nearby[:capacity]
        self.detected_count = len(tracks)
        return tracks

    def accuracy_factor(self) -> float:
        return max(0.55, 1.0 - self.jam_level)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.circle(surface, (73, 210, 255), self.position, 18, 2)
        end = self.position + Vector(0, -72).rotate_rad(self.scan_phase)
        pygame.draw.line(surface, (73, 210, 255), self.position, end, 2)
        pygame.draw.circle(surface, (73, 210, 255), self.position, 72, 1)


@dataclass(slots=True)
class DefenseWeapon:
    key: str
    name: str
    position: Vector
    projectile_speed: float
    explosion_radius: float
    accuracy: float
    reload_time: float
    detection_range: float
    ammo: int
    unit_cost: int
    role: WeaponRole = WeaponRole.PRECISION
    fire_control_channels: int = 1
    salvo_size: int = 1
    shot_damage: float = 9999
    cooldown: float = 0.0
    target_id: int | None = None
    fired_count: int = 0
    spent_cost: int = 0

    @property
    def ready(self) -> bool:
        return self.cooldown <= 0 and self.ammo > 0

    def update(self, dt: float) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)

    def find_intercept(self, target: AttackProjectile) -> InterceptSolution | None:
        if self.position.distance_to(target.position) > self.detection_range:
            return None
        return solve_linear_intercept(self.position, target.position, target.predicted_velocity(), self.projectile_speed)

    def estimated_pk(self, target: AttackProjectile, radar_accuracy: float) -> float:
        pk = self.accuracy * radar_accuracy
        if target.trajectory is TrajectoryType.EVASIVE:
            pk *= 0.78
        if target.jammer_strength > 0:
            pk *= max(0.65, 1.0 - target.jammer_strength * 0.35)
        if self.role is WeaponRole.AREA:
            pk += min(0.12, self.explosion_radius / 900.0)
        if self.role is WeaponRole.RAPID and target.is_child:
            pk += 0.08
        return max(0.20, min(0.995, pk))

    def fire(self, solution: InterceptSolution, target: AttackProjectile, radar_accuracy: float = 1.0) -> DefenseProjectile:
        pk = self.estimated_pk(target, radar_accuracy)
        error_limit = (1.0 - pk) * 55.0
        error = Vector(random.uniform(-error_limit, error_limit), random.uniform(-error_limit, error_limit))
        self.cooldown = self.reload_time
        self.ammo -= 1
        self.fired_count += 1
        self.spent_cost += self.unit_cost
        return DefenseProjectile(
            position=Vector(self.position),
            target_point=solution.position + error,
            speed=self.projectile_speed,
            explosion_radius=self.explosion_radius,
            damage=self.shot_damage,
            target_uid=target.uid,
            weapon_key=self.key,
            unit_cost=self.unit_cost,
            estimated_pk=pk,
        )

    def draw(self, surface: pygame.Surface) -> None:
        color = (82, 235, 197) if self.role is WeaponRole.RAPID else DEFENSE
        pygame.draw.circle(surface, (43, 73, 102), self.position, 23)
        pygame.draw.circle(surface, color, self.position, 16, 3)
        pygame.draw.line(surface, color, self.position, self.position + Vector(0, -34), 6)
