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
    ATTACK, BACKGROUND, BASE_POSITION, DANGER, FPS, GRID, GROUND, GROUND_Y,
    HEIGHT, MUTED_TEXT, SUCCESS, TEXT, TITLE, WARNING, WIDTH,
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
            DefenseWeapon("PRECISION", DEFENSE_MODELS["PRECISION"]["name"], Vector(WIDTH*.20, GROUND_Y),
                          760, 34, .993, .28, 1280, 150, DEFENSE_MODELS["PRECISION"]["unit_cost"],
                          WeaponRole.PRECISION, 2, 1),
            DefenseWeapon("AREA", DEFENSE_MODELS["AREA"]["name"], Vector(WIDTH*.38, GROUND_Y),
                          430, 104, .91, .66, 1080, 110, DEFENSE_MODELS["AREA"]["unit_cost"],
                          WeaponRole.AREA, 1, 1),
            DefenseWeapon("RAPID_A", DEFENSE_MODELS["RAPID_A"]["name"], Vector(WIDTH*.64, GROUND_Y),
                          640, 40, .95, .12, 1140, 320, DEFENSE_MODELS["RAPID_A"]["unit_cost"],
                          WeaponRole.RAPID, 4, 2),
            DefenseWeapon("RAPID_B", DEFENSE_MODELS["RAPID_B"]["name"], Vector(WIDTH*.80, GROUND_Y),
                          670, 36, .96, .14, 1170, 280, DEFENSE_MODELS["RAPID_B"]["unit_cost"],
                          WeaponRole.RAPID, 4, 2),
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
                if event.key == pygame.K_ESCAPE: self.running = False
                elif event.key == pygame.K_SPACE: self.paused = not self.paused
                elif event.key == pygame.K_r: self.reset()
                elif event.key == pygame.K_a: self.auto_defense = not self.auto_defense
                elif event.key == pygame.K_n: self.schedule_wave(True)
                elif event.key == pygame.K_d: self.show_details = not self.show_details

    def update(self, dt: float) -> None:
        self.wave_timer -= dt
        if self.wave_timer <= 0 and not self.spawn_queue:
            self.schedule_wave()
        self.update_spawn_queue(dt)

        children: list[AttackProjectile] = []
        for p in self.attack_projectiles:
            p.update(dt)
            if p.should_split():
                spawned = p.create_child_warheads(GROUND_Y)
                children.extend(spawned)
                self.children_spawned += len(spawned)
                for child in spawned:
                    self.attack_counts[child.model_key] += 1
                    self.attack_cost += child.unit_cost
                self.explosions.append(Explosion(Vector(p.position), p.explosion_radius*.65, defensive=False))
                continue
            if p.position.y >= GROUND_Y:
                p.alive = False
                distance = p.position.distance_to(self.base.position)
                if distance <= p.explosion_radius + 76:
                    falloff = max(.2, 1 - distance/(p.explosion_radius+76))
                    self.base.take_damage(p.damage*falloff)
                self.explosions.append(Explosion(Vector(p.position), p.explosion_radius, defensive=False))
        self.attack_projectiles.extend(children)
        self.current_tracks = self.radar.update(dt, self.attack_projectiles)

        for w in self.weapons:
            w.update(dt)
        if self.auto_defense:
            self.update_defense_ai()

        new_explosions: list[Explosion] = []
        for p in self.defense_projectiles:
            if p.update(dt):
                new_explosions.append(Explosion(Vector(p.position), p.explosion_radius))
                self.apply_defense_explosion(p.position, p.explosion_radius)
        self.explosions.extend(new_explosions)
        for e in self.explosions: e.update(dt)

        self.attack_projectiles = [p for p in self.attack_projectiles if p.alive and p.position.y < HEIGHT+100]
        self.defense_projectiles = [p for p in self.defense_projectiles if p.alive]
        self.explosions = [e for e in self.explosions if e.alive]

    def schedule_wave(self, force: bool=False) -> None:
        if self.spawn_queue and not force: return
        self.wave += 1
        pattern = AttackPattern(min(2+self.wave//3, 7), min(2+self.wave//4, 6),
                                max(.045, .15-self.wave*.004), max(.28, .72-self.wave*.018))
        trajectory = random.choices(
            [TrajectoryType.LINEAR, TrajectoryType.CURVED, TrajectoryType.EVASIVE],
            weights=[max(2,8-self.wave),3,max(1,self.wave//2)])[0]
        delay = 0.0
        for _ in range(pattern.burst_count):
            for shot in range(pattern.projectiles_per_burst):
                self.spawn_queue.append((delay+shot*pattern.projectile_interval, self.wave, trajectory))
            delay += pattern.burst_interval
        self.wave_timer = max(2.8, 6.2-self.wave*.08)

    def update_spawn_queue(self, dt: float) -> None:
        remaining = []
        for delay, wave, trajectory in self.spawn_queue:
            delay -= dt
            if delay <= 0: self.spawn_attack_projectile(wave, trajectory)
            else: remaining.append((delay,wave,trajectory))
        self.spawn_queue = remaining

    def spawn_attack_projectile(self, wave: int, trajectory: TrajectoryType) -> None:
        start = Vector(random.randint(70, WIDTH-70), random.randint(25,80))
        direction = self.base.position + Vector(random.uniform(-120,120),0) - start
        mirv = random.random() < min(.58, max(0,(wave-2)*.055))
        jammer = random.random() < min(.48, max(0,(wave-3)*.045))
        key = "MIRV_JAMMER" if mirv and jammer else "MIRV" if mirv else "JAMMER" if jammer else "STRIKER"
        model = ATTACK_MODELS[key]
        speed = min(340, 105+wave*8+random.uniform(-12,18))*float(model["speed_factor"])
        velocity = direction.normalize()*speed
        velocity.rotate_ip(random.uniform(-max(2,18-wave*.45), max(2,18-wave*.45)))
        child_count = random.randint(2,min(7,2+wave//2)) if mirv else 0
        p = AttackProjectile(
            start, velocity, (65+wave*7)*float(model["damage_factor"]),
            min(90,28+wave*2.4), key, trajectory, min(.98,.72+wave*.012),
            child_count, random.uniform(230,420),
            random.uniform(.18,.55) if jammer else 0.0,
        )
        self.attack_projectiles.append(p)
        self.spawned += 1
        self.attack_counts[key] += 1
        self.attack_cost += p.unit_cost

    def active_commitments(self) -> dict[int, list[DefenseProjectile]]:
        result: dict[int, list[DefenseProjectile]] = {}
        for p in self.defense_projectiles:
            if p.alive:
                result.setdefault(p.target_uid, []).append(p)
        return result

    @staticmethod
    def cumulative_pk(projectiles: list[DefenseProjectile]) -> float:
        miss = 1.0
        for p in projectiles:
            miss *= 1.0 - p.estimated_pk
        return 1.0 - miss

    def desired_pk(self, target: AttackProjectile) -> float:
        value = target.unit_cost + target.child_warheads * ATTACK_MODELS["CHILD"]["unit_cost"]
        if target.jammer_strength > .25 or target.child_warheads >= 4:
            return .97
        if target.is_child or value < 700_000:
            return .82
        return .92

    def update_defense_ai(self) -> None:
        if not self.current_tracks: return
        commitments = self.active_commitments()
        radar_accuracy = self.radar.accuracy_factor()

        for weapon in sorted(self.weapons, key=lambda w: (w.unit_cost, self.weapon_priority(w))):
            if not weapon.ready: continue
            candidates = []
            for target in self.current_tracks:
                if not target.alive: continue
                solution = weapon.find_intercept(target)
                if solution is None or solution.position.y > GROUND_Y+20: continue
                existing = commitments.get(target.uid, [])
                current_pk = self.cumulative_pk(existing)
                desired = self.desired_pk(target)
                if current_pk >= desired: continue
                shot_pk = weapon.estimated_pk(target, radar_accuracy)
                projected = 1-(1-current_pk)*(1-shot_pk)
                marginal = projected-current_pk
                fit = self.weapon_fit(weapon,target)
                value_saved = target.unit_cost + target.child_warheads*ATTACK_MODELS["CHILD"]["unit_cost"]
                economy = (value_saved*marginal/max(1,weapon.unit_cost))*fit
                threat = self.calculate_threat(target)
                candidates.append((economy*100 + threat*.01, target, solution, shot_pk))
            candidates.sort(key=lambda x:x[0], reverse=True)
            budget = min(weapon.salvo_size, weapon.fire_control_channels, weapon.ammo)
            fired = 0
            for _, target, solution, shot_pk in candidates:
                if fired >= budget: break
                existing = commitments.get(target.uid, [])
                if self.cumulative_pk(existing) >= self.desired_pk(target): continue
                projectile = weapon.fire(solution, target, radar_accuracy)
                self.defense_projectiles.append(projectile)
                commitments.setdefault(target.uid, []).append(projectile)
                self.defense_counts[weapon.key] += 1
                self.defense_cost += weapon.unit_cost
                fired += 1
                if weapon.role is not WeaponRole.RAPID: break

    @staticmethod
    def weapon_priority(w: DefenseWeapon) -> int:
        return {WeaponRole.AREA:0, WeaponRole.RAPID:1, WeaponRole.PRECISION:2}[w.role]

    def calculate_threat(self, t: AttackProjectile) -> float:
        tti = max(.05,(GROUND_Y-t.position.y)/max(1,t.velocity.y))
        return t.damage*.45 + 190/tti + t.speed*.18 + t.child_warheads*58 + t.jammer_strength*260

    @staticmethod
    def weapon_fit(w: DefenseWeapon, t: AttackProjectile) -> float:
        fit = 1.0
        if t.child_warheads >= 3: fit *= 1.6 if w.role is WeaponRole.PRECISION else .75
        if t.is_child: fit *= 1.8 if w.role is WeaponRole.RAPID else .75
        if t.jammer_strength > .25: fit *= 1.45 if w.role is WeaponRole.PRECISION else .85
        if w.role is WeaponRole.AREA and t.is_child: fit *= 1.25
        if t.speed > 260 and w.projectile_speed < 500: fit *= .6
        return fit

    def apply_defense_explosion(self, position: Vector, radius: float) -> None:
        for t in self.attack_projectiles:
            if t.alive and t.position.distance_to(position) <= radius+t.radius:
                t.alive = False
                self.destroyed += 1
                self.score += int(100+t.speed*.5+t.damage+t.child_warheads*30+t.jammer_strength*180)

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        for x in range(0,WIDTH,48): pygame.draw.line(self.screen,GRID,(x,0),(x,GROUND_Y),1)
        for y in range(0,GROUND_Y,48): pygame.draw.line(self.screen,GRID,(0,y),(WIDTH,y),1)
        pygame.draw.rect(self.screen,GROUND,(0,GROUND_Y,WIDTH,HEIGHT-GROUND_Y))
        for e in self.explosions: e.draw(self.screen)
        for p in self.attack_projectiles: p.draw(self.screen)
        for p in self.defense_projectiles: p.draw(self.screen)
        for w in self.weapons: w.draw(self.screen)
        self.radar.draw(self.screen); self.base.draw(self.screen)
        self.draw_hud()
        if self.show_details: self.draw_detail_panel()
        if self.paused: self.draw_center_message("PAUSED","SPACE to continue")
        elif not self.base.alive: self.draw_center_message("CHECKPOINT LOST","Press R to restart")
        pygame.display.flip()

    def draw_hud(self) -> None:
        ratio = self.base.health/self.base.max_health
        pygame.draw.rect(self.screen,(28,38,52),(20,18,330,25),border_radius=5)
        color = SUCCESS if ratio>.55 else WARNING if ratio>.25 else DANGER
        pygame.draw.rect(self.screen,color,(20,18,int(330*ratio),25),border_radius=5)
        self.screen.blit(self.small_font.render(f"BASE {self.base.health:05.0f}/{self.base.max_health:.0f}",True,TEXT),(30,22))
        total_attack = sum(self.attack_counts.values())
        total_defense = sum(self.defense_counts.values())
        saved_ratio = self.attack_cost/max(1,self.defense_cost)
        lines = [
            f"Wave {self.wave}   Score {self.score}",
            f"Attack ammo: {total_attack}   Cost: {CURRENCY}{self.attack_cost:,}",
            f"Defense ammo: {total_defense}   Cost: {CURRENCY}{self.defense_cost:,}",
            f"Cost ratio A/D: {saved_ratio:.2f}x   Intercepted: {self.destroyed}/{self.spawned+self.children_spawned}",
            f"Hostiles: {len(self.attack_projectiles)}   Radar: {self.radar.detected_count}/{self.radar.tracking_channels}",
            f"Jamming: {self.radar.jam_level*100:.1f}%   Auto: {'ON' if self.auto_defense else 'OFF'}",
        ]
        for i,line in enumerate(lines): self.screen.blit(self.font.render(line,True,TEXT),(20,54+i*23))
        controls="D Details   SPACE Pause   A Auto   N Next wave   R Restart   ESC Exit"
        self.screen.blit(self.small_font.render(controls,True,MUTED_TEXT),(20,HEIGHT-28))
        panel=pygame.Rect(WIDTH-350,15,330,118)
        pygame.draw.rect(self.screen,(14,25,42),panel,border_radius=7); pygame.draw.rect(self.screen,GRID,panel,1,border_radius=7)
        for i,w in enumerate(self.weapons):
            status="READY" if w.ready else f"{w.cooldown:.2f}s"
            text=f"{w.name:<13} {w.ammo:03d} ${w.unit_cost/1_000_000:.2f}M {status}"
            self.screen.blit(self.small_font.render(text,True,TEXT),(WIDTH-338,24+i*23))

    def draw_detail_panel(self) -> None:
        overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); overlay.fill((4,9,17,232)); self.screen.blit(overlay,(0,0))
        self.screen.blit(self.large_font.render("MISSILE ECONOMY & INVENTORY",True,TEXT),(55,34))
        x1,x2=55,650
        self.screen.blit(self.font.render("ATTACK TYPES",True,ATTACK),(x1,100))
        y=130
        for key,m in ATTACK_MODELS.items():
            count=self.attack_counts[key]
            line=f"{m['name']:<16} qty {count:03d}  unit ${m['unit_cost']/1_000_000:.2f}M  total ${count*m['unit_cost']/1_000_000:.2f}M"
            self.screen.blit(self.small_font.render(line,True,TEXT),(x1,y)); y+=25
            self.screen.blit(self.small_font.render(str(m["description"]),True,MUTED_TEXT),(x1+16,y)); y+=30
        self.screen.blit(self.font.render("DEFENSE TYPES",True,DEFENSE),(x2,100))
        y=130
        for w in self.weapons:
            count=self.defense_counts[w.key]
            model=DEFENSE_MODELS[w.key]
            line=f"{w.name:<16} fired {count:03d}  unit ${w.unit_cost/1_000_000:.2f}M"
            self.screen.blit(self.small_font.render(line,True,TEXT),(x2,y)); y+=23
            stats=f"speed {w.projectile_speed:.0f}  accuracy {w.accuracy*100:.1f}%  radius {w.explosion_radius:.0f}  ammo {w.ammo}"
            self.screen.blit(self.small_font.render(stats,True,TEXT),(x2+16,y)); y+=22
            self.screen.blit(self.small_font.render(str(model["description"]),True,MUTED_TEXT),(x2+16,y)); y+=31
        cheaper="DEFENSE" if self.defense_cost < self.attack_cost else "ATTACK"
        delta=abs(self.attack_cost-self.defense_cost)
        summary=f"Cheaper side: {cheaper} | Cost difference: ${delta:,} | Press D to close"
        self.screen.blit(self.font.render(summary,True,WARNING),(55,HEIGHT-55))

    def draw_center_message(self,title:str,subtitle:str)->None:
        overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); overlay.fill((0,0,0,165)); self.screen.blit(overlay,(0,0))
        a=self.large_font.render(title,True,ATTACK); b=self.font.render(subtitle,True,TEXT)
        self.screen.blit(a,a.get_rect(center=(WIDTH/2,HEIGHT/2-24))); self.screen.blit(b,b.get_rect(center=(WIDTH/2,HEIGHT/2+28)))
