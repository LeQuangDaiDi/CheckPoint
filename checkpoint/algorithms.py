from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import pygame

Vector = pygame.Vector2


@dataclass(frozen=True, slots=True)
class InterceptSolution:
    time: float
    position: Vector


def solve_linear_intercept(
    shooter_position: Vector,
    target_position: Vector,
    target_velocity: Vector,
    interceptor_speed: float,
) -> InterceptSolution | None:
    """Find the earliest positive interception point for linear target motion."""
    relative = target_position - shooter_position
    a = target_velocity.dot(target_velocity) - interceptor_speed**2
    b = 2.0 * relative.dot(target_velocity)
    c = relative.dot(relative)

    if abs(a) < 1e-8:
        if abs(b) < 1e-8:
            return None
        time = -c / b
        if time <= 0:
            return None
        return InterceptSolution(time, target_position + target_velocity * time)

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None

    root = math.sqrt(discriminant)
    candidates = [
        value
        for value in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a))
        if value > 0
    ]
    if not candidates:
        return None

    time = min(candidates)
    return InterceptSolution(time, target_position + target_velocity * time)


def distance_to_segment(point: Vector, start: Vector, end: Vector) -> float:
    segment = end - start
    if segment.length_squared() == 0:
        return point.distance_to(start)
    ratio = max(0.0, min(1.0, (point - start).dot(segment) / segment.length_squared()))
    closest = start + segment * ratio
    return point.distance_to(closest)


def cluster_center(points: Iterable[Vector]) -> Vector:
    values = list(points)
    if not values:
        return Vector()
    total = Vector()
    for point in values:
        total += point
    return total / len(values)
