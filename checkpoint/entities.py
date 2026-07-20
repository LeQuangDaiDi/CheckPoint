from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum

import pygame

from .algorithms import InterceptSolution, solve_linear_intercept
from .catalog import ATTACK_MODELS
from .settings import ATTACK, BASE_MAX_HEALTH, DEFENSE, DANGER, PIXEL, SUCCESS, WARNING

Vector = pygame.Vector2


class TrajectoryType(str, Enum):
    LINEAR = "linear"
    CURVED = "curved"
    EVASIVE = "evasive"
    WEAVE = "weave"
    DIVE = "dive"
    CRUISE = "cruise"
    BOOST_GLIDE = "boost_glide"


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
    radius: int = 7
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
        base = Vector(self.velocity) if self.velocity.length_squared() else Vector(0, 1)
        spread = min(56.0, 16.0 + self.child_warheads * 4.2)
        child_model = ATTACK_MODELS["CHILD"]
        for index in range(self.child_warheads):
            factor = 0.5 if self.child_warheads == 1 else index / (self.child_warheads - 1)
            angle = -spread / 2 + spread * factor + random.uniform(-4.0, 4.0)
            velocity = base.rotate(angle)
            velocity.scale_to_length(self.speed * random.uniform(1.05, 1.24) * float(child_model["speed_factor"]))
            children.append(
                AttackProjectile(
                    position=Vector(self.position),
                    velocity=velocity,
                    damage=self.damage * float(child_model["damage_factor"]),
                    explosion_radius=max(20.0, self.explosion_radius * 0.54),
                    model_key="CHILD",
                    trajectory=random.choice((TrajectoryType.EVASIVE, TrajectoryType.WEAVE, TrajectoryType.DIVE)),
                    accuracy=max(0.65, self.accuracy - 0.05),
                    split_altitude=target_y,
                    jammer_strength=self.jammer_strength * 0.22,
                    is_child=True,
                    radius=5,
                )
            )
        return children

    def update(self, dt: float) -> None:
        self.age += dt
        if self.trajectory is TrajectoryType.LINEAR:
            self.position += self.velocity * dt
        elif self.trajectory is TrajectoryType.CURVED:
            self.velocity.y += 24.0 * dt
            self.position += self.velocity * dt
        elif self.trajectory is TrajectoryType.EVASIVE:
            side = Vector(-self.velocity.y, self.velocity.x)
            if side.length_squared():
                side.scale_to_length(math.sin(self.age * 6.8 + self.phase) * 45.0)
            self.position += (self.velocity + side) * dt
        elif self.trajectory is TrajectoryType.WEAVE:
            side = Vector(-self.velocity.y, self.velocity.x)
            if side.length_squared():
                side.scale_to_length(math.sin(self.age * 10.5 + self.phase) * 72.0)
            self.position += (self.velocity + side) * dt
        elif self.trajectory is TrajectoryType.DIVE:
            self.velocity.y += 55.0 * dt
            self.velocity *= 1.0 + 0.07 * dt
            self.position += self.velocity * dt
        elif self.trajectory is TrajectoryType.CRUISE:
            desired_y = 145 + math.sin(self.age * 1.8 + self.phase) * 42
            self.velocity.y += (desired_y - self.position.y) * 0.95 * dt
            self.position += self.velocity * dt
        else:
            self.velocity *= 1.0 + 0.14 * dt
            self.velocity.rotate_ip(math.sin(self.age * 2.7 + self.phase) * 0.42)
            self.position += self.velocity * dt

    def draw(self, surface: pygame.Surface) -> None:
        color = (255, 173, 65) if self.is_child else ATTACK
        direction = self.velocity.normalize() if self.velocity.length_squared() else Vector(0, 1)
        side = Vector(-direction.y, direction.x)
        tip = self.position + direction * (self.radius + 5)
        rear = self.position - direction * self.radius
        points = [tip, rear + side * self.radius, rear - side * self.radius]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.rect(surface, (255, 221, 128), (int(rear.x)-2, int(rear.y)-2, PIXEL, PIXEL))
        if self.jammer_strength > 0.05:
            pulse = int(14 + 6 * (1 + math.sin(self.age * 8)))
            pygame.draw.circle(surface, (194, 106, 255), self.position, pulse, 2)


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
    radius: int = 5
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
        pygame.draw.line(surface, (56, 116, 156), self.position, self.target_point, 1)
        x, y = int(self.position.x), int(self.position.y)
        pygame.draw.rect(surface, DEFENSE, (x-4, y-4, 8, 8))
        pygame.draw.rect(surface, (207, 247, 255), (x-2, y-2, 4, 4))


@dataclass(slots=True)
class Explosion:
    position: Vector
    max_radius: float
    duration: float = 0.42
    age: float = 0.0
    defensive: bool = True

    @property
    def alive(self) -> bool:
        return self.age < self.duration

    @property
    def current_radius(self) -> float:
        return self.max_radius * min(1.0, self.age / self.duration)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:
        color = SUCCESS if self.defensive else DANGER
        radius = int(self.current_radius)
        pygame.draw.circle(surface, color, self.position, radius, 3)
        if radius > 10:
            pygame.draw.circle(surface, WARNING, self.position, max(2, radius // 3), 2)


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
        dark = (21, 43, 52)
        metal = (70, 112, 119)
        glow = (78, 230, 210)
        pygame.draw.rect(surface, dark, (x-70, y-34, 140, 44))
        pygame.draw.rect(surface, metal, (x-58, y-25, 116, 26))
        pygame.draw.rect(surface, glow, (x-8, y-58, 16, 34))
        pygame.draw.rect(surface, metal, (x-36, y-66, 72, 8))
        pygame.draw.arc(surface, glow, (x-46, y-88, 92, 48), math.pi, math.tau, 5)
        pygame.draw.line(surface, glow, (x, y-64), (x+34, y-86), 4)
        pygame.draw.rect(surface, WARNING, (x+30, y-90, 8, 8))


@dataclass(slots=True)
class RadarSystem:
    position: Vector
    range: float = 1560.0
    tracking_channels: int = 32
    processing_rate: float = 15.0
    eccm_strength: float = 0.76
    scan_phase: float = 0.0
    detected_count: int = 0
    jam_level: float = 0.0

    def update(self, dt: float, targets: list[AttackProjectile]) -> list[AttackProjectile]:
        self.scan_phase = (self.scan_phase + dt * self.processing_rate) % math.tau
        nearby = [t for t in targets if t.alive and self.position.distance_to(t.position) <= self.range]
        raw_jam = sum(t.jammer_strength * max(0.0, 1.0-self.position.distance_to(t.position)/self.range) for t in nearby)
        self.jam_level = min(0.85, raw_jam * (1.0-self.eccm_strength))
        capacity = max(1, int(self.tracking_channels * (1.0-self.jam_level*0.65)))
        nearby.sort(key=lambda t: (t.position.y, -t.speed), reverse=True)
        tracks = nearby[:capacity]
        self.detected_count = len(tracks)
        return tracks

    def accuracy_factor(self) -> float:
        return max(0.58, 1.0-self.jam_level)

    def draw(self, surface: pygame.Surface) -> None:
        end = self.position + Vector(0, -98).rotate_rad(self.scan_phase)
        pygame.draw.line(surface, (72, 238, 216), self.position, end, 3)
        pygame.draw.circle(surface, (72, 238, 216), self.position, 98, 2)
        pygame.draw.circle(surface, (72, 238, 216), self.position, 52, 1)


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
        self.cooldown = max(0.0, self.cooldown-dt)

    def find_intercept(self, target: AttackProjectile) -> InterceptSolution | None:
        if self.position.distance_to(target.position) > self.detection_range:
            return None
        return solve_linear_intercept(self.position, target.position, target.predicted_velocity(), self.projectile_speed)

    def estimated_pk(self, target: AttackProjectile, radar_accuracy: float) -> float:
        pk = self.accuracy * radar_accuracy
        if target.trajectory in (TrajectoryType.EVASIVE, TrajectoryType.WEAVE, TrajectoryType.BOOST_GLIDE):
            pk *= 0.76
        if target.jammer_strength > 0:
            pk *= max(0.64, 1.0-target.jammer_strength*0.35)
        if self.role is WeaponRole.AREA:
            pk += min(0.13, self.explosion_radius/850.0)
        if self.role is WeaponRole.RAPID and target.is_child:
            pk += 0.10
        return max(0.20, min(0.995, pk))

    def fire(self, solution: InterceptSolution, target: AttackProjectile, radar_accuracy: float=1.0) -> DefenseProjectile:
        pk = self.estimated_pk(target, radar_accuracy)
        error_limit = (1.0-pk)*58.0
        error = Vector(random.uniform(-error_limit, error_limit), random.uniform(-error_limit, error_limit))
        self.cooldown = self.reload_time
        self.ammo -= 1
        self.fired_count += 1
        self.spent_cost += self.unit_cost
        return DefenseProjectile(Vector(self.position), solution.position+error, self.projectile_speed,
                                 self.explosion_radius, self.shot_damage, target.uid, self.key,
                                 self.unit_cost, pk)

    def draw(self, surface: pygame.Surface) -> None:
        x, y = int(self.position.x), int(self.position.y)
        color = (86, 237, 196) if self.role is WeaponRole.RAPID else DEFENSE
        pygame.draw.rect(surface, (25, 48, 64), (x-24, y-18, 48, 26))
        pygame.draw.rect(surface, color, (x-14, y-26, 28, 16))
        pygame.draw.rect(surface, (213, 248, 255), (x-4, y-42, 8, 22))
