from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

import pygame

from .catalog import ATTACK_MODELS, CURRENCY, DEFENSE_MODELS
from .entities import (
    AttackProjectile, Base, DefenseProjectile, DefenseWeapon, Explosion,
    RadarSystem, TrajectoryType, WeaponRole,
)
from .settings import (
    ATTACK, BACKGROUND, BASE_POSITION, DANGER, DEFENSE, FPS, GRID, GROUND,
    GROUND_Y, HEIGHT, MUTED_TEXT, PANEL, PANEL_BORDER, SKY_BOTTOM, SKY_TOP,
    SUCCESS, TEXT, TITLE, WARNING, WIDTH,
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
        self.font = pygame.font.SysFont("consolas", 18, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.tiny_font = pygame.font.SysFont("consolas", 12)
        self.large_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.running = True
        self.reset()

    def reset(self) -> None:
        self.base = Base(Vector(BASE_POSITION))
        self.radar = RadarSystem(Vector(WIDTH * .5, GROUND_Y - 18))
        self.attack_projectiles: list[AttackProjectile] = []
        self.defense_projectiles: list[DefenseProjectile] = []
        self.explosions: list[Explosion] = []
        self.weapons = [
            DefenseWeapon("PRECISION", DEFENSE_MODELS["PRECISION"]["name"], Vector(WIDTH*.16, GROUND_Y),
                          900, 38, .994, .32, 1570, 170, DEFENSE_MODELS["PRECISION"]["unit_cost"],
                          WeaponRole.PRECISION, 1, 1),
            DefenseWeapon("AREA", DEFENSE_MODELS["AREA"]["name"], Vector(WIDTH*.34, GROUND_Y),
                          520, 118, .92, .70, 1320, 125, DEFENSE_MODELS["AREA"]["unit_cost"],
                          WeaponRole.AREA, 1, 1),
            DefenseWeapon("RAPID_A", DEFENSE_MODELS["RAPID_A"]["name"], Vector(WIDTH*.68, GROUND_Y),
                          760, 44, .958, .14, 1260, 360, DEFENSE_MODELS["RAPID_A"]["unit_cost"],
                          WeaponRole.RAPID, 1, 1),
            DefenseWeapon("RAPID_B", DEFENSE_MODELS["RAPID_B"]["name"], Vector(WIDTH*.84, GROUND_Y),
                          800, 40, .966, .16, 1300, 320, DEFENSE_MODELS["RAPID_B"]["unit_cost"],
                          WeaponRole.RAPID, 1, 1),
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
                self.explosions.append(Explosion(Vector(projectile.position), projectile.explosion_radius*.72, defensive=False))
                continue
            if projectile.position.y >= GROUND_Y:
                projectile.alive = False
                distance = projectile.position.distance_to(self.base.position)
                if distance <= projectile.explosion_radius + 92:
                    falloff = max(.2, 1-distance/(projectile.explosion_radius+92))
                    self.base.take_damage(projectile.damage*falloff)
                self.target_owners.pop(projectile.uid, None)
                self.explosions.append(Explosion(Vector(projectile.position), projectile.explosion_radius, defensive=False))
        self.attack_projectiles.extend(children)
        self.current_tracks = self.radar.update(dt, self.attack_projectiles)
        self.cleanup_target_owners()

        for weapon in self.weapons:
            weapon.update(dt)
        if self.auto_defense:
            self.update_defense_ai()

        new_explosions: list[Explosion] = []
        for projectile in self.defense_projectiles:
            if projectile.update(dt):
                new_explosions.append(Explosion(Vector(projectile.position), projectile.explosion_radius))
                self.apply_defense_explosion(projectile.position, projectile.explosion_radius)
        self.explosions.extend(new_explosions)
        for explosion in self.explosions:
            explosion.update(dt)

        self.attack_projectiles = [p for p in self.attack_projectiles if p.alive and -150 < p.position.x < WIDTH+150 and p.position.y < HEIGHT+150]
        self.defense_projectiles = [p for p in self.defense_projectiles if p.alive]
        self.explosions = [e for e in self.explosions if e.alive]

    def schedule_wave(self, force: bool=False) -> None:
        if self.spawn_queue and not force:
            return
        self.wave += 1
        pattern = AttackPattern(
            min(2+self.wave//3, 8), min(2+self.wave//4, 7),
            max(.04, .145-self.wave*.004), max(.25, .70-self.wave*.018),
        )
        delay = 0.0
        for _ in range(pattern.burst_count):
            for shot in range(pattern.projectiles_per_burst):
                trajectory = self.random_trajectory()
                self.spawn_queue.append((delay+shot*pattern.projectile_interval, self.wave, trajectory))
            delay += pattern.burst_interval
        self.wave_timer = max(3.0, 6.5-self.wave*.08)

    def random_trajectory(self) -> TrajectoryType:
        choices = [
            TrajectoryType.LINEAR, TrajectoryType.CURVED, TrajectoryType.EVASIVE,
            TrajectoryType.WEAVE, TrajectoryType.DIVE, TrajectoryType.CRUISE,
            TrajectoryType.BOOST_GLIDE,
        ]
        weights = [5, 3, 3, max(1, self.wave//3), max(1, self.wave//4), max(1, self.wave//5), max(1, self.wave//6)]
        return random.choices(choices, weights=weights)[0]

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
        start = Vector(random.randint(110, WIDTH-110), random.randint(26, 90))
        direction = self.base.position + Vector(random.uniform(-190, 190), 0) - start
        mirv = random.random() < min(.64, max(0, (wave-2)*.06))
        jammer = random.random() < min(.52, max(0, (wave-3)*.048))
        if trajectory is TrajectoryType.CRUISE:
            key = "CRUISE"
        elif trajectory is TrajectoryType.BOOST_GLIDE:
            key = "BOOST_GLIDE"
        else:
            key = "MIRV_JAMMER" if mirv and jammer else "MIRV" if mirv else "JAMMER" if jammer else "STRIKER"
        model = ATTACK_MODELS[key]
        speed = min(430, 132+wave*10+random.uniform(-14, 24))*float(model["speed_factor"])
        velocity = direction.normalize()*speed
        velocity.rotate_ip(random.uniform(-max(2, 16-wave*.38), max(2, 16-wave*.38)))
        child_count = random.randint(3, min(10, 3+wave//2)) if mirv else 0
        projectile = AttackProjectile(
            start, velocity, (72+wave*8)*float(model["damage_factor"]),
            min(105, 32+wave*2.8), key, trajectory, min(.99, .76+wave*.012),
            child_count, random.uniform(260, 500), random.uniform(.20, .62) if jammer else 0.0,
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
        if solution is None or solution.position.y > GROUND_Y+20:
            return False
        tti = max(0.0, (GROUND_Y-target.position.y)/max(1.0, target.velocity.y))
        return owner.cooldown <= tti

    def select_owner(self, target: AttackProjectile, radar_accuracy: float) -> tuple[DefenseWeapon, object] | None:
        options: list[tuple[float, DefenseWeapon, object]] = []
        target_value = target.unit_cost + target.child_warheads*ATTACK_MODELS["CHILD"]["unit_cost"]
        distance_to_base = target.position.distance_to(self.base.position)
        urgency = 1.0 + max(0.0, 1.0-distance_to_base/1400.0)*2.6
        for weapon in self.weapons:
            if weapon.ammo <= 0:
                continue
            solution = weapon.find_intercept(target)
            if solution is None or solution.position.y > GROUND_Y+20:
                continue
            pk = weapon.estimated_pk(target, radar_accuracy)
            fit = self.weapon_fit(weapon, target)
            delay_penalty = 1.0+weapon.cooldown*2.2
            economy = (target_value*pk*fit*urgency)/max(1, weapon.unit_cost*delay_penalty)
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
        tracks = sorted(self.current_tracks, key=self.nearest_target_priority)
        for target in tracks:
            if not target.alive:
                continue
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

    def nearest_target_priority(self, target: AttackProjectile) -> tuple[float, float, float]:
        distance = target.position.distance_to(self.base.position)
        tti = max(.02, (GROUND_Y-target.position.y)/max(1.0, target.velocity.y))
        return (tti, distance, -self.calculate_threat(target))

    def calculate_threat(self, target: AttackProjectile) -> float:
        tti = max(.05, (GROUND_Y-target.position.y)/max(1, target.velocity.y))
        return target.damage*.45 + 260/tti + target.speed*.22 + target.child_warheads*72 + target.jammer_strength*310

    @staticmethod
    def weapon_fit(weapon: DefenseWeapon, target: AttackProjectile) -> float:
        fit = 1.0
        if target.child_warheads >= 3:
            fit *= 1.7 if weapon.role is WeaponRole.PRECISION else .72
        if target.is_child:
            fit *= 1.95 if weapon.role is WeaponRole.RAPID else .70
        if target.jammer_strength > .25:
            fit *= 1.5 if weapon.role is WeaponRole.PRECISION else .82
        if weapon.role is WeaponRole.AREA and target.is_child:
            fit *= 1.30
        if target.speed > 340 and weapon.projectile_speed < 620:
            fit *= .52
        return fit

    def apply_defense_explosion(self, position: Vector, radius: float) -> None:
        for target in self.attack_projectiles:
            if target.alive and target.position.distance_to(position) <= radius+target.radius:
                target.alive = False
                self.target_owners.pop(target.uid, None)
                self.destroyed += 1
                self.score += int(120+target.speed*.55+target.damage+target.child_warheads*38+target.jammer_strength*210)

    def draw(self) -> None:
        self.draw_pixel_background()
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
            self.draw_center_message("RADAR COMMAND LOST", "Press R to restart")
        pygame.display.flip()

    def draw_pixel_background(self) -> None:
        self.screen.fill(BACKGROUND)
        bands = 18
        for index in range(bands):
            t = index/(bands-1)
            color = tuple(int(a+(b-a)*t) for a, b in zip(SKY_TOP, SKY_BOTTOM))
            y = int(index*GROUND_Y/bands)
            pygame.draw.rect(self.screen, color, (0, y, WIDTH, GROUND_Y//bands+2))
        for x in range(0, WIDTH, 64):
            pygame.draw.line(self.screen, GRID, (x, 0), (x, GROUND_Y), 1)
        for y in range(0, GROUND_Y, 64):
            pygame.draw.line(self.screen, GRID, (0, y), (WIDTH, y), 1)
        for x in range(0, WIDTH, 48):
            height = 10 + ((x//48)*13 % 44)
            pygame.draw.rect(self.screen, (25, 43, 54), (x, GROUND_Y-height, 38, height))
        pygame.draw.rect(self.screen, GROUND, (0, GROUND_Y, WIDTH, HEIGHT-GROUND_Y))
        pygame.draw.rect(self.screen, (56, 83, 78), (0, GROUND_Y, WIDTH, 6))

    def panel_box(self, rect: pygame.Rect, title: str, title_color: tuple[int, int, int]) -> None:
        pygame.draw.rect(self.screen, PANEL, rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, 2)
        pygame.draw.rect(self.screen, title_color, (rect.x, rect.y, rect.width, 28))
        self.screen.blit(self.small_font.render(title, True, (7, 15, 24)), (rect.x+10, rect.y+6))

    def draw_hud(self) -> None:
        health_ratio = self.base.health/self.base.max_health
        pygame.draw.rect(self.screen, (16, 29, 43), (20, 18, 390, 30))
        color = SUCCESS if health_ratio > .55 else WARNING if health_ratio > .25 else DANGER
        pygame.draw.rect(self.screen, color, (20, 18, int(390*health_ratio), 30))
        self.screen.blit(self.small_font.render(f"RADAR COMMAND {self.base.health:05.0f}/{self.base.max_health:.0f}", True, TEXT), (30, 25))

        total_attack = sum(self.attack_counts.values())
        total_defense = sum(self.defense_counts.values())
        info = [
            f"WAVE {self.wave:02d}  SCORE {self.score:07d}",
            f"ATTACK launched {total_attack:03d} airborne {len(self.attack_projectiles):03d}",
            f"DEFENSE fired {total_defense:03d} airborne {len(self.defense_projectiles):03d}",
            f"RADAR {self.radar.detected_count:02d}/{self.radar.tracking_channels}  JAM {self.radar.jam_level*100:04.1f}%",
            f"LOCKS {len(self.target_owners):02d}  TAKEOVERS {self.takeovers:02d}",
        ]
        for index, line in enumerate(info):
            self.screen.blit(self.font.render(line, True, TEXT), (20, 62+index*24))

        attack_rect = pygame.Rect(WIDTH-410, 18, 390, 244)
        defense_rect = pygame.Rect(WIDTH-410, 276, 390, 250)
        self.panel_box(attack_rect, "ATTACK ARSENAL / DAN TAN CONG", ATTACK)
        self.panel_box(defense_rect, "DEFENSE BATTERIES / DAN PHONG THU", DEFENSE)

        y = attack_rect.y+38
        for key, model in ATTACK_MODELS.items():
            count = self.attack_counts[key]
            line = f"{model['name']:<18} x{count:03d}  ${model['unit_cost']/1_000_000:4.2f}M"
            self.screen.blit(self.tiny_font.render(line, True, TEXT), (attack_rect.x+12, y))
            y += 27

        y = defense_rect.y+38
        for weapon in self.weapons:
            locks = sum(1 for owner in self.target_owners.values() if owner == weapon.key)
            status = "READY" if weapon.ready else f"{weapon.cooldown:.2f}s"
            line = f"{weapon.name:<16} ammo {weapon.ammo:03d} lock {locks:02d} {status}"
            self.screen.blit(self.tiny_font.render(line, True, TEXT), (defense_rect.x+12, y))
            y += 45
            details = f"spd {weapon.projectile_speed:.0f} pk {weapon.accuracy*100:.1f}% r {weapon.explosion_radius:.0f} ${weapon.unit_cost/1_000_000:.2f}M"
            self.screen.blit(self.tiny_font.render(details, True, MUTED_TEXT), (defense_rect.x+24, y-20))

        economy_rect = pygame.Rect(WIDTH-410, 540, 390, 112)
        self.panel_box(economy_rect, "BATTLE ECONOMY", WARNING)
        ratio = self.attack_cost/max(1, self.defense_cost)
        economy = [
            f"Attack cost  {CURRENCY}{self.attack_cost:,}",
            f"Defense cost {CURRENCY}{self.defense_cost:,}",
            f"A/D ratio    {ratio:.2f}x",
        ]
        for index, line in enumerate(economy):
            self.screen.blit(self.small_font.render(line, True, TEXT), (economy_rect.x+14, economy_rect.y+38+index*22))

        controls = "D DETAILS   SPACE PAUSE   A AUTO   N NEXT WAVE   R RESTART   ESC EXIT"
        self.screen.blit(self.small_font.render(controls, True, MUTED_TEXT), (20, HEIGHT-29))

    def draw_detail_panel(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((3, 8, 16, 238))
        self.screen.blit(overlay, (0, 0))
        self.screen.blit(self.large_font.render("PIXEL MISSILE COMMAND DATABASE", True, TEXT), (56, 38))
        x1, x2 = 56, WIDTH//2+18
        self.screen.blit(self.font.render("ATTACK MISSILES", True, ATTACK), (x1, 105))
        self.screen.blit(self.font.render("DEFENSE INTERCEPTORS", True, DEFENSE), (x2, 105))
        y = 138
        for key, model in ATTACK_MODELS.items():
            count = self.attack_counts[key]
            self.screen.blit(self.small_font.render(
                f"{model['name']:<18} qty {count:03d} unit ${model['unit_cost']/1_000_000:.2f}M", True, TEXT), (x1, y))
            y += 22
            self.screen.blit(self.tiny_font.render(str(model['description']), True, MUTED_TEXT), (x1+16, y))
            y += 34
        y = 138
        for weapon in self.weapons:
            self.screen.blit(self.small_font.render(
                f"{weapon.name:<18} fired {self.defense_counts[weapon.key]:03d} ammo {weapon.ammo:03d}", True, TEXT), (x2, y))
            y += 22
            self.screen.blit(self.tiny_font.render(
                f"speed {weapon.projectile_speed:.0f} accuracy {weapon.accuracy*100:.1f}% radius {weapon.explosion_radius:.0f} cost ${weapon.unit_cost/1_000_000:.2f}M", True, MUTED_TEXT), (x2+16, y))
            y += 44
        self.screen.blit(self.font.render("Press D to close", True, WARNING), (56, HEIGHT-60))

    def draw_center_message(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        a = self.large_font.render(title, True, ATTACK)
        b = self.font.render(subtitle, True, TEXT)
        self.screen.blit(a, a.get_rect(center=(WIDTH/2, HEIGHT/2-24)))
        self.screen.blit(b, b.get_rect(center=(WIDTH/2, HEIGHT/2+28)))
