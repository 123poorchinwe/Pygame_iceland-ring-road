import pygame
import math
import json
import os
import random
import glob
from pathlib import Path

# =========================
# Basic Settings
# =========================

pygame.init()

WIDTH, HEIGHT = 1200, 760
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iceland Ring Road Challenge - Spatial Game")

CLOCK = pygame.time.Clock()
FPS = 60

BASE_DIR = Path(__file__).resolve().parent

# Files
RESTAURANT_FILE = BASE_DIR / "restaurants_iceland.json"
GAS_FILE = BASE_DIR / "gas_stations_iceland.json"
MAP_IMAGE_FILE = BASE_DIR / "assets" / "iceland_map.png"
PHOTO_FOLDER = BASE_DIR / "assets" / "photos"
TITLE_IMAGE_FILE = BASE_DIR / "assets" / "ui" / "iceland_driving_exploration_title.png"

# Icelandic future-minimal palette
WHITE = (245, 249, 250)
BLACK = (12, 16, 18)
GLACIER_WHITE = (239, 247, 249)
POLAR_GRAY = (177, 193, 198)
LAVA_BLACK = (12, 18, 22)
AURORA_CYAN = (78, 238, 220)
GLACIER_BLUE = (85, 169, 230)
TUNDRA_GREEN = (111, 172, 132)
WARNING_RED = (245, 88, 96)
YELLOW = (250, 210, 80)
ORANGE = (240, 150, 60)
BLUE = GLACIER_BLUE
DARK_BLUE = (15, 34, 45)
GREEN = TUNDRA_GREEN
RED = WARNING_RED
GRAY = POLAR_GRAY
DARK_GRAY = (55, 65, 68)
ICE = (190, 230, 240)
SNOW_COLOR = (250, 250, 255)
GLASS = (225, 242, 246, 178)
GLASS_DARK = (15, 27, 34, 190)

def make_font(size, bold=False):
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except (TypeError, OSError, pygame.error):
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        return font


FONT = make_font(18)
SMALL_FONT = make_font(14)
BIG_FONT = make_font(30, bold=True)
TITLE_FONT = make_font(48, bold=True)

# Iceland bounding box
LAT_MIN, LAT_MAX = 63.0, 66.8
LON_MIN, LON_MAX = -24.8, -13.0
# Segment driving view
# Follow-camera world view
FOLLOW_CAMERA = True

# 地图放大倍数，越大越近
CAMERA_ZOOM = 2.15

# UI 顶部高度，避免地图盖住状态栏
UI_TOP_HEIGHT = 76

# Make in-game time pass faster
TIME_SPEED_MULTIPLIER = 2.2

# Make displayed speed readable while keeping physical steering gentle
SPEED_DISPLAY_FACTOR = 0.82
CURRENT_CAMERA = None

# =========================
# Geo Conversion
# =========================

def geo_to_screen(lat, lon):
    x = int((lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH)
    y = int((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT)
    return x, y

def get_follow_camera(player):
    """
    Camera follows the player while still using the full Iceland map.
    The world is zoomed in, and the camera scrolls around the player.
    """

    world_width = WIDTH
    world_height = HEIGHT

    view_width = WIDTH / CAMERA_ZOOM
    view_height = (HEIGHT - UI_TOP_HEIGHT) / CAMERA_ZOOM

    cam_x = player.x - view_width / 2
    cam_y = player.y - view_height / 2

    # Clamp camera inside the full map
    cam_x = max(0, min(cam_x, world_width - view_width))
    cam_y = max(0, min(cam_y, world_height - view_height))

    return {
        "x": cam_x,
        "y": cam_y,
        "zoom": CAMERA_ZOOM
    }


def world_to_view(x, y, camera):
    """
    Convert full-map world coordinate to screen coordinate under follow camera.
    """
    if not FOLLOW_CAMERA or camera is None:
        return int(x), int(y)

    view_x = int((x - camera["x"]) * camera["zoom"])
    view_y = int((y - camera["y"]) * camera["zoom"] + UI_TOP_HEIGHT)

    return view_x, view_y

def geo_to_view(lat, lon, camera):
    """
    Convert geo coordinates directly into segment-view screen coordinates.
    """
    x, y = geo_to_screen(lat, lon)
    return world_to_view(x, y, camera)

def geo_to_minimap(lat, lon, rect):
    x = rect.x + int((lon - LON_MIN) / (LON_MAX - LON_MIN) * rect.width)
    y = rect.y + int((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * rect.height)
    return x, y


def screen_distance(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

def point_in_polygon(point, polygon):
    """
    Ray casting algorithm.
    Return True if point is inside polygon.
    """
    x, y = point
    inside = False

    j = len(polygon) - 1

    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 0.000001) + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside

def point_to_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        return screen_distance(p, a)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    nearest = (ax + t * dx, ay + t * dy)
    return screen_distance(p, nearest)


def is_land_position(x, y, margin=8):
    samples = [
        (x, y),
        (x - margin, y),
        (x + margin, y),
        (x, y - margin),
        (x, y + margin),
    ]

    return all(point_in_polygon(sample, ICELAND_LAND_POLYGON) for sample in samples)


def route_points_to_screen(route, camera=None):
    points = []
    for lat, lon in route["points"]:
        if FOLLOW_CAMERA and camera is not None:
            points.append(geo_to_view(lat, lon, camera))
        else:
            points.append(geo_to_screen(lat, lon))
    return points


def iter_route_segments():
    for route in ROUTE_NETWORK:
        points = [geo_to_screen(lat, lon) for lat, lon in route["points"]]
        for i in range(len(points) - 1):
            yield route, points[i], points[i + 1]
        if route.get("closed") and len(points) > 2:
            yield route, points[-1], points[0]


# =========================
# Game Data
# =========================

CHECKPOINTS = [
    {"name": "Reykjavik", "lat": 64.1466, "lon": -21.9426, "visited": False},
    {"name": "Thingvellir", "lat": 64.2559, "lon": -21.1295, "visited": False},
    {"name": "Geysir", "lat": 64.3104, "lon": -20.3024, "visited": False},
    {"name": "Gullfoss", "lat": 64.3271, "lon": -20.1199, "visited": False},
    {"name": "Seljalandsfoss", "lat": 63.6156, "lon": -19.9886, "visited": False},
    {"name": "Skogafoss", "lat": 63.5321, "lon": -19.5114, "visited": False},
    {"name": "Vik", "lat": 63.4186, "lon": -19.0060, "visited": False},
    {"name": "Jokulsarlon", "lat": 64.0481, "lon": -16.1794, "visited": False},
    {"name": "Hofn", "lat": 64.2497, "lon": -15.2020, "visited": False},
    {"name": "Egilsstadir", "lat": 65.2669, "lon": -14.3948, "visited": False},
    {"name": "Myvatn", "lat": 65.6039, "lon": -16.9961, "visited": False},
    {"name": "Akureyri", "lat": 65.6885, "lon": -18.1262, "visited": False},
    {"name": "Kirkjufell", "lat": 64.9417, "lon": -23.3069, "visited": False},
]

HOME = {
    "name": "Home - Reykjavik",
    "lat": 64.1466,
    "lon": -21.9426
}
# =========================
# Iceland Land Boundary
# =========================
# A simplified playable land polygon.
# The player is not allowed to drive outside this boundary.

ICELAND_LAND_POLYGON_GEO = [
    (66.45, -24.05),
    (66.55, -22.70),
    (66.42, -21.15),
    (66.30, -19.35),
    (66.18, -17.35),
    (65.85, -14.55),
    (65.20, -13.55),
    (64.55, -13.70),
    (63.98, -14.35),
    (63.55, -16.20),
    (63.30, -18.15),
    (63.35, -20.30),
    (63.62, -21.75),
    (64.05, -22.75),
    (64.70, -24.00),
    (65.35, -24.55),
    (65.95, -24.35),
]

ICELAND_LAND_POLYGON = [
    geo_to_screen(lat, lon) for lat, lon in ICELAND_LAND_POLYGON_GEO
]

ROUTE_NETWORK = [
    {
        "name": "Ring Road",
        "kind": "main",
        "closed": True,
        "color": (86, 103, 106),
        "points": [(cp["lat"], cp["lon"]) for cp in CHECKPOINTS],
    },
    {
        "name": "Kjolur Highland Route",
        "kind": "highland",
        "closed": False,
        "color": (92, 142, 128),
        "points": [
            (64.3271, -20.1199),
            (64.58, -19.70),
            (64.86, -19.45),
            (65.12, -19.36),
            (65.43, -19.10),
            (65.6885, -18.1262),
        ],
    },
    {
        "name": "Sprengisandur Highland Route",
        "kind": "highland",
        "closed": False,
        "color": (80, 133, 154),
        "points": [
            (64.2559, -21.1295),
            (64.55, -20.15),
            (64.95, -19.12),
            (65.25, -18.25),
            (65.6039, -16.9961),
        ],
    },
    {
        "name": "Landmannalaugar Spur",
        "kind": "scenic",
        "closed": False,
        "color": (111, 172, 132),
        "points": [
            (63.6156, -19.9886),
            (63.88, -19.35),
            (64.02, -19.05),
            (64.08, -18.65),
            (63.5321, -19.5114),
        ],
    },
    {
        "name": "Snaefellsnes Coastal Road",
        "kind": "scenic",
        "closed": False,
        "color": (85, 169, 230),
        "points": [
            (64.1466, -21.9426),
            (64.45, -22.30),
            (64.74, -22.84),
            (64.9417, -23.3069),
        ],
    },
]

# =========================
# Fixed Mountains
# =========================

random.seed(7)
MOUNTAINS = []

for _ in range(35):
    x = random.randint(120, WIDTH - 120)
    y = random.randint(130, HEIGHT - 120)
    MOUNTAINS.append((x, y))


# =========================
# Data Loading
# =========================

def load_restaurants():
    if RESTAURANT_FILE.exists():
        try:
            with open(RESTAURANT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return [
        {"name": "Reykjavik Food Hall", "lat": 64.1475, "lon": -21.9330},
        {"name": "Vik Local Restaurant", "lat": 63.4190, "lon": -19.0050},
        {"name": "Akureyri Diner", "lat": 65.6900, "lon": -18.1200},
        {"name": "Hofn Seafood House", "lat": 64.2500, "lon": -15.2100},
        {"name": "Egilsstadir Cafe", "lat": 65.2650, "lon": -14.3900},
        {"name": "Geysir Restaurant", "lat": 64.3090, "lon": -20.3010},
        {"name": "Gullfoss Cafe", "lat": 64.3260, "lon": -20.1200},
        {"name": "Myvatn Bistro", "lat": 65.6040, "lon": -16.9960},
    ]


def load_gas_stations():
    """
    Generate gas stations along the Ring Road.
    No external JSON file needed.
    Gas stations are placed between major checkpoints.
    """

    gas_stations = []

    gas_id = 1

    # 每两个相邻景点之间放 1 个加油站
    for i in range(len(CHECKPOINTS)):
        start = CHECKPOINTS[i]
        end = CHECKPOINTS[(i + 1) % len(CHECKPOINTS)]

        # 不是放在正中间，而是稍微随机一点，更自然
        t = random.uniform(0.35, 0.65)

        lat = start["lat"] + (end["lat"] - start["lat"]) * t
        lon = start["lon"] + (end["lon"] - start["lon"]) * t

        # 小范围偏移，避免完全压在线上
        lat += random.uniform(-0.035, 0.035)
        lon += random.uniform(-0.055, 0.055)

        gas_stations.append({
            "name": f"Ring Road Gas Station {gas_id}",
            "lat": lat,
            "lon": lon
        })

        gas_id += 1

    # 重要城市附近额外加几个，更符合自驾逻辑
    extra_gas = [
        {"name": "Reykjavik Main Gas Station", "lat": 64.1450, "lon": -21.9200},
        {"name": "Vik Gas Station", "lat": 63.4200, "lon": -19.0100},
        {"name": "Hofn Gas Station", "lat": 64.2520, "lon": -15.2050},
        {"name": "Egilsstadir Gas Station", "lat": 65.2670, "lon": -14.3980},
        {"name": "Akureyri Gas Station", "lat": 65.6900, "lon": -18.1300},
        {"name": "Myvatn Fuel Stop", "lat": 65.6045, "lon": -16.9950},
        {"name": "Kirkjufell Fuel Stop", "lat": 64.9405, "lon": -23.3050},
    ]

    gas_stations.extend(extra_gas)

    return gas_stations


def load_speed_cameras():
    """
    Randomly generate speed cameras near the Ring Road.
    No real CSV data needed.
    """
    random.seed(42)

    cameras = []

    for i in range(35):
        index = random.randint(0, len(CHECKPOINTS) - 1)
        start = CHECKPOINTS[index]
        end = CHECKPOINTS[(index + 1) % len(CHECKPOINTS)]

        t = random.uniform(0.15, 0.85)

        lat = start["lat"] + (end["lat"] - start["lat"]) * t
        lon = start["lon"] + (end["lon"] - start["lon"]) * t

        lat += random.uniform(-0.08, 0.08)
        lon += random.uniform(-0.12, 0.12)

        speed_limit = random.choice([50, 60, 70, 80, 90])

        cameras.append({
            "name": f"Ring Road Camera {i + 1}",
            "lat": lat,
            "lon": lon,
            "speed_limit": speed_limit
        })

    return cameras


def load_map_background():
    """
    If assets/iceland_map.png exists and is a valid image, use it.
    Otherwise the game uses a simple pixel Iceland background.
    """
    if MAP_IMAGE_FILE.exists():
        try:
            image = pygame.image.load(str(MAP_IMAGE_FILE)).convert()
            image = pygame.transform.scale(image, (WIDTH, HEIGHT))
            return image
        except Exception as e:
            print("Map image could not be loaded. Using default pixel map.")
            print(e)

    return None


def load_title_logo():
    if not TITLE_IMAGE_FILE.exists():
        return None

    try:
        logo = pygame.image.load(str(TITLE_IMAGE_FILE)).convert_alpha()
        for y in range(logo.get_height()):
            for x in range(logo.get_width()):
                r, g, b, a = logo.get_at((x, y))
                if r > 232 and g > 232 and b > 232:
                    logo.set_at((x, y), (r, g, b, 0))
        max_w = 820
        scale = min(max_w / logo.get_width(), 1.0)
        return pygame.transform.smoothscale(
            logo,
            (int(logo.get_width() * scale), int(logo.get_height() * scale))
        )
    except Exception as e:
        print("Title image could not be loaded.")
        print(e)
        return None


# =========================
# Animation Classes
# =========================

class FloatingText:
    def __init__(self, text, x, y, color):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.life = 90

    def update(self):
        self.y -= 0.8
        self.life -= 1

    def draw(self):
        alpha = max(0, min(255, int(self.life / 90 * 255)))
        surface = FONT.render(self.text, True, self.color)
        surface.set_alpha(alpha)
        SCREEN.blit(surface, (self.x, self.y))


class SnowParticle:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(-HEIGHT, 0)
        self.speed = random.uniform(1.5, 4.5)
        self.size = random.randint(2, 4)

    def update(self):
        self.y += self.speed
        self.x += random.uniform(-0.8, 0.8)

        if self.y > HEIGHT:
            self.y = random.randint(-120, -10)
            self.x = random.randint(0, WIDTH)

    def draw(self):
        pygame.draw.circle(SCREEN, SNOW_COLOR, (int(self.x), int(self.y)), self.size)


# =========================
# Player Class
# =========================

class Player:
    def __init__(self):
        self.x, self.y = geo_to_screen(HOME["lat"], HOME["lon"])
        self.speed = 0
        self.angle = 90

        self.base_max_speed = 5.35
        self.max_speed = self.base_max_speed
        self.acceleration = 0.075
        self.brake_force = 0.105
        self.friction = 0.055
        self.turn_rate = 1.75

        self.money = 1000
        self.life = 5
        self.fuel = 100
        self.score = 0
        self.stability = 100

        self.has_eaten_today = False
        self.day = 1
        self.game_minutes = 8 * 60

        self.message = "Welcome to Iceland Ring Road Challenge!"
        self.message_timer = 240

        self.camera_cooldown = {}
        self.route_score_cooldown = 0
        self.total_refuel_cost = 0
        self.total_lodging_cost = 0
        self.total_fine_cost = 0
        self.fine_count = 0
        self.refuel_count = 0
        self.lodging_count = 0
        self.total_distance = 0.0
        self.last_violation = None
        self.violation_timer = 0

    def update(self, keys, weather):
        if weather == "blizzard":
            self.max_speed = self.base_max_speed * 0.55
        elif weather == "snow":
            self.max_speed = self.base_max_speed * 0.75
        else:
            self.max_speed = self.base_max_speed

        if self.fuel <= 0:
            self.speed = 0
            self.stability = max(0, self.stability - 0.02)
            self.show_message("Out of fuel. Refuel now if you are at a gas station.")
            return

        if keys[pygame.K_UP]:
            self.speed += self.acceleration
        elif keys[pygame.K_DOWN]:
            self.speed -= self.brake_force
        else:
            if self.speed > 0:
                self.speed = max(0, self.speed - self.friction)
            elif self.speed < 0:
                self.speed = min(0, self.speed + self.friction)

        self.speed = max(-1.35, min(self.speed, self.max_speed))

        speed_ratio = min(1.0, abs(self.speed) / max(0.1, self.max_speed))
        steering = self.turn_rate * (1.0 - speed_ratio * 0.32)
        if keys[pygame.K_LEFT]:
            self.angle -= steering
        if keys[pygame.K_RIGHT]:
            self.angle += steering

        # Save previous legal position
        old_x, old_y = self.x, self.y

        rad = math.radians(self.angle)
        dx = math.cos(rad) * self.speed
        dy = math.sin(rad) * self.speed
        self.x += dx
        self.y += dy
        self.total_distance += math.sqrt(dx * dx + dy * dy)

        # Basic screen boundary
        self.x = max(0, min(WIDTH, self.x))
        self.y = max(75, min(HEIGHT, self.y))

        # Land boundary: prevent the car body from entering the ocean.
        if not is_land_position(self.x, self.y, 9):
            self.x, self.y = old_x, old_y
            self.speed *= -0.18
            self.stability = max(0, self.stability - 0.4)
            self.show_message("Ocean boundary: stay on Iceland's land roads.")

        # Faster fuel consumption: higher speed burns much more fuel
        self.fuel -= 0.018 + abs(self.speed) * 0.027
        self.fuel = max(0, self.fuel)
        self.stability = max(0, self.stability - abs(self.speed) * 0.0012)

        # Time passes according to driving speed.
        # Faster driving means more distance covered, so game time advances faster.
        distance_factor = abs(self.speed)
        time_factor = (0.03 + distance_factor * 0.16) * TIME_SPEED_MULTIPLIER
        self.game_minutes += time_factor

        if self.game_minutes >= 24 * 60:
           self.game_minutes -= 24 * 60
           self.day += 1

           if not self.has_eaten_today:
                self.life -= 1
                self.money -= 60
                self.show_message("You did not eat yesterday! -1 life and -€60")

           self.has_eaten_today = False

        hour = int(self.game_minutes // 60)

        if 2 <= hour < 8:
            home_pos = geo_to_screen(HOME["lat"], HOME["lon"])
            if screen_distance((self.x, self.y), home_pos) > 55:
                self.life -= 1
                self.show_message("You were not home before 02:00! -1 life")
                self.x, self.y = home_pos
                self.game_minutes = 8 * 60
                self.day += 1
                self.has_eaten_today = False

        if self.message_timer > 0:
            self.message_timer -= 1

        if self.route_score_cooldown > 0:
            self.route_score_cooldown -= 1
        if self.violation_timer > 0:
            self.violation_timer -= 1

    def show_message(self, text):
        self.message = text
        self.message_timer = 240

    def current_time_text(self):
        h = int(self.game_minutes // 60)
        m = int(self.game_minutes % 60)
        return f"Day {self.day}  {h:02d}:{m:02d}"

    def hour(self):
        return int(self.game_minutes // 60)

    def current_speed_kmh(self):
        return int(abs(self.speed) * 25 * SPEED_DISPLAY_FACTOR)

    def total_km(self):
        return int(self.total_distance * 1.7)

    def total_spend(self):
        return self.total_refuel_cost + self.total_lodging_cost + self.total_fine_cost


# =========================
# Drawing Background
# =========================

def draw_background(map_image, player, camera=None):
    """
    Draw the full Iceland map with a follow camera.
    If there is no real map image, draw a pixel-style full Iceland map.
    """

    if FOLLOW_CAMERA and camera is not None:
        SCREEN.fill((95, 160, 200))

        if map_image:
            # Crop the visible part from the full map image, then scale it to screen
            crop_rect = pygame.Rect(
                int(camera["x"]),
                int(camera["y"]),
                int(WIDTH / camera["zoom"]),
                int((HEIGHT - UI_TOP_HEIGHT) / camera["zoom"])
            )

            crop_rect.clamp_ip(map_image.get_rect())

            cropped = map_image.subsurface(crop_rect).copy()
            cropped = pygame.transform.scale(cropped, (WIDTH, HEIGHT - UI_TOP_HEIGHT))
            SCREEN.blit(cropped, (0, UI_TOP_HEIGHT))

        else:
            # Draw pixel map in world coordinates, then transform each element
            SCREEN.fill((95, 160, 200))

            island_points_world = [
                geo_to_screen(66.3, -24.0),
                geo_to_screen(66.5, -20.5),
                geo_to_screen(66.2, -16.0),
                geo_to_screen(65.2, -13.8),
                geo_to_screen(64.0, -14.2),
                geo_to_screen(63.3, -18.0),
                geo_to_screen(63.5, -22.0),
                geo_to_screen(64.5, -24.3),
            ]

            island_points_view = [
                world_to_view(x, y, camera) for x, y in island_points_world
            ]

            pygame.draw.polygon(SCREEN, (170, 210, 165), island_points_view)
            pygame.draw.polygon(SCREEN, (80, 120, 90), island_points_view, 4)

            for x, y in MOUNTAINS:
                vx, vy = world_to_view(x, y, camera)
                if -50 < vx < WIDTH + 50 and UI_TOP_HEIGHT - 50 < vy < HEIGHT + 50:
                    pygame.draw.polygon(
                        SCREEN,
                        (130, 150, 135),
                        [(vx, vy), (vx - 14, vy + 28), (vx + 14, vy + 28)]
                    )

    else:
        if map_image:
            SCREEN.blit(map_image, (0, 0))
        else:
            SCREEN.fill((95, 160, 200))

            island_points = [
                geo_to_screen(66.3, -24.0),
                geo_to_screen(66.5, -20.5),
                geo_to_screen(66.2, -16.0),
                geo_to_screen(66.2, -16.0),
                geo_to_screen(65.2, -13.8),
                geo_to_screen(64.0, -14.2),
                geo_to_screen(63.3, -18.0),
                geo_to_screen(63.5, -22.0),
                geo_to_screen(64.5, -24.3),
            ]

            pygame.draw.polygon(SCREEN, (170, 210, 165), island_points)
            pygame.draw.polygon(SCREEN, (80, 120, 90), island_points, 4)

            for x, y in MOUNTAINS:
                pygame.draw.polygon(
                    SCREEN,
                    (130, 150, 135),
                    [(x, y), (x - 8, y + 16), (x + 8, y + 16)]
                )

    draw_day_night_overlay(player)


def draw_day_night_overlay(player):
    hour = player.hour()

    if 20 <= hour or hour < 6:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 45, 120))
        SCREEN.blit(overlay, (0, 0))
    elif 18 <= hour < 20 or 6 <= hour < 8:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 150, 50, 45))
        SCREEN.blit(overlay, (0, 0))


def draw_ring_road(camera=None):
    for route in ROUTE_NETWORK:
        points = route_points_to_screen(route, camera)
        if len(points) < 2:
            continue

        closed = route.get("closed", False)
        is_highland = route["kind"] == "highland"
        outer_width = 15 if route["kind"] == "main" else 10
        inner_width = 7 if route["kind"] == "main" else 4

        if FOLLOW_CAMERA:
            outer_width = int(outer_width * 1.05)
            inner_width = int(inner_width * 1.05)

        pygame.draw.lines(SCREEN, LAVA_BLACK, closed, points, outer_width)
        pygame.draw.lines(SCREEN, route["color"], closed, points, inner_width)

        # dashed center line
        for i in range(len(points)):
            if not closed and i == len(points) - 1:
                continue
            a = points[i]
            b = points[(i + 1) % len(points)]

            steps = 10 if is_highland else 12
            for j in range(steps):
                if j % 2 == 0:
                    t1 = j / steps
                    t2 = (j + 0.5) / steps

                    x1 = a[0] + (b[0] - a[0]) * t1
                    y1 = a[1] + (b[1] - a[1]) * t1
                    x2 = a[0] + (b[0] - a[0]) * t2
                    y2 = a[1] + (b[1] - a[1]) * t2

                    dash_color = AURORA_CYAN if is_highland else WHITE
                    pygame.draw.line(SCREEN, dash_color, (x1, y1), (x2, y2), 2)


def draw_checkpoints(camera=None):
    for cp in CHECKPOINTS:
        if FOLLOW_CAMERA and camera is not None:
            x, y = geo_to_view(cp["lat"], cp["lon"], camera)
        else:
            x, y = geo_to_screen(cp["lat"], cp["lon"])

        if x < -80 or x > WIDTH + 80 or y < UI_TOP_HEIGHT - 80 or y > HEIGHT + 80:
            continue

        color = AURORA_CYAN if cp["visited"] else POLAR_GRAY

        pygame.draw.circle(SCREEN, (10, 18, 22), (x, y), 17)
        pygame.draw.circle(SCREEN, color, (x, y), 13)
        pygame.draw.circle(SCREEN, GLACIER_WHITE, (x, y), 5)

        label = SMALL_FONT.render(cp["name"], True, GLACIER_WHITE)
        bg = pygame.Rect(x + 15, y - 12, label.get_width() + 12, 22)
        panel = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 16, 20, 150), panel.get_rect(), border_radius=5)
        SCREEN.blit(panel, bg.topleft)
        SCREEN.blit(label, (x + 16, y - 10))


def draw_restaurants(restaurants, camera=None):
    for r in restaurants:
        if FOLLOW_CAMERA and camera is not None:
            x, y = geo_to_view(r["lat"], r["lon"], camera)
        else:
            x, y = geo_to_screen(r["lat"], r["lon"])

        if x < -60 or x > WIDTH + 60 or y < UI_TOP_HEIGHT - 60 or y > HEIGHT + 60:
            continue

        pygame.draw.rect(SCREEN, (226, 245, 238), (x - 14, y - 14, 28, 28), border_radius=4)
        pygame.draw.rect(SCREEN, TUNDRA_GREEN, (x - 14, y - 14, 28, 28), 2, border_radius=4)

        pygame.draw.circle(SCREEN, WHITE, (x, y + 2), 7)
        pygame.draw.circle(SCREEN, BLACK, (x, y + 2), 7, 1)

        pygame.draw.line(SCREEN, BLACK, (x - 9, y - 9), (x - 9, y + 9), 2)
        pygame.draw.line(SCREEN, BLACK, (x - 12, y - 9), (x - 12, y - 3), 1)
        pygame.draw.line(SCREEN, BLACK, (x - 6, y - 9), (x - 6, y - 3), 1)

        pygame.draw.line(SCREEN, BLACK, (x + 10, y - 9), (x + 10, y + 9), 2)
        pygame.draw.polygon(SCREEN, BLACK, [(x + 8, y - 9), (x + 12, y - 9), (x + 10, y - 3)])

def draw_gas_stations(gas_stations, camera=None):
    for g in gas_stations:
        if FOLLOW_CAMERA and camera is not None:
            x, y = geo_to_view(g["lat"], g["lon"], camera)
        else:
            x, y = geo_to_screen(g["lat"], g["lon"])

        if x < -60 or x > WIDTH + 60 or y < UI_TOP_HEIGHT - 60 or y > HEIGHT + 60:
            continue

        pygame.draw.rect(SCREEN, GLACIER_BLUE, (x - 12, y - 16, 22, 32), border_radius=3)
        pygame.draw.rect(SCREEN, AURORA_CYAN, (x - 12, y - 16, 22, 32), 2, border_radius=3)

        pygame.draw.rect(SCREEN, WHITE, (x - 7, y - 11, 12, 8))
        pygame.draw.rect(SCREEN, BLACK, (x - 7, y - 11, 12, 8), 1)

        pygame.draw.line(SCREEN, BLACK, (x + 10, y - 5), (x + 18, y + 3), 2)
        pygame.draw.line(SCREEN, BLACK, (x + 18, y + 3), (x + 15, y + 12), 2)

        label = SMALL_FONT.render("F", True, WHITE)
        SCREEN.blit(label, (x - 5, y + 1))


def draw_speed_cameras(cameras, camera=None):
    for cam in cameras:
        if FOLLOW_CAMERA and camera is not None:
            x, y = geo_to_view(cam["lat"], cam["lon"], camera)
        else:
            x, y = geo_to_screen(cam["lat"], cam["lon"])

        if x < -60 or x > WIDTH + 60 or y < UI_TOP_HEIGHT - 60 or y > HEIGHT + 60:
            continue

        pygame.draw.rect(SCREEN, LAVA_BLACK, (x - 8, y - 8, 16, 16), border_radius=3)
        pygame.draw.rect(SCREEN, WARNING_RED, (x - 4, y - 4, 8, 8), border_radius=2)


def draw_car(player):
    """
    Pixel-style car with clear front and back.
    Front = yellow headlights + pointed nose.
    Back = red tail lights.
    """

    car_surface = pygame.Surface((46, 30), pygame.SRCALPHA)

    # car body
    pygame.draw.rect(car_surface, RED, (8, 6, 28, 18))

    # front nose, points to the RIGHT before rotation
    pygame.draw.polygon(
        car_surface,
        ORANGE,
        [(36, 6), (45, 15), (36, 24)]
    )

    # windshield
    pygame.draw.rect(car_surface, (120, 210, 240), (24, 9, 9, 12))

    # side window
    pygame.draw.rect(car_surface, (160, 230, 250), (14, 9, 8, 12))

    # wheels
    pygame.draw.circle(car_surface, BLACK, (13, 5), 4)
    pygame.draw.circle(car_surface, BLACK, (31, 5), 4)
    pygame.draw.circle(car_surface, BLACK, (13, 25), 4)
    pygame.draw.circle(car_surface, BLACK, (31, 25), 4)

    # headlights and light beams
    pygame.draw.circle(car_surface, YELLOW, (42, 11), 3)
    pygame.draw.circle(car_surface, YELLOW, (42, 19), 3)

    pygame.draw.polygon(car_surface, (255, 240, 120, 90), [(44, 10), (46, 6), (46, 14)])
    pygame.draw.polygon(car_surface, (255, 240, 120, 90), [(44, 20), (46, 16), (46, 24)])

    # tail lights at back
    pygame.draw.rect(car_surface, (120, 0, 0), (5, 9, 4, 5))
    pygame.draw.rect(car_surface, (120, 0, 0), (5, 17, 4, 5))

    # black outline
    pygame.draw.rect(car_surface, BLACK, (8, 6, 28, 18), 2)
    pygame.draw.polygon(
        car_surface,
        BLACK,
        [(36, 6), (45, 15), (36, 24)],
        2
    )

    rotated = pygame.transform.rotate(car_surface, -player.angle)

    if FOLLOW_CAMERA and CURRENT_CAMERA is not None:
        draw_x, draw_y = world_to_view(player.x, player.y, CURRENT_CAMERA)
    else:
        draw_x, draw_y = player.x, player.y

    rect = rotated.get_rect(center=(draw_x, draw_y))
    SCREEN.blit(rotated, rect)

# =========================
# UI Drawing
# =========================

def draw_soft_shadow(rect, radius=8, alpha=75, offset=(0, 8)):
    shadow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow,
        (0, 8, 14, alpha),
        (9 + offset[0], 9 + offset[1], rect.width, rect.height),
        border_radius=radius
    )
    SCREEN.blit(shadow, (rect.x - 9, rect.y - 9))


def draw_glass_panel(rect, fill=GLASS_DARK, border=AURORA_CYAN, radius=8, glow=True):
    draw_soft_shadow(rect, radius)
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, (255, 255, 255, 45), panel.get_rect(), 1, border_radius=radius)
    SCREEN.blit(panel, rect.topleft)
    if glow:
        pygame.draw.rect(SCREEN, border, rect, 2, border_radius=radius)


def draw_progress_bar(rect, value, max_value, color, bg=(42, 55, 60), label=None):
    pygame.draw.rect(SCREEN, bg, rect, border_radius=5)
    ratio = 0 if max_value <= 0 else max(0, min(1, value / max_value))
    fill = pygame.Rect(rect.x, rect.y, int(rect.width * ratio), rect.height)
    if fill.width > 0:
        pygame.draw.rect(SCREEN, color, fill, border_radius=5)
    pygame.draw.rect(SCREEN, (218, 245, 248), rect, 1, border_radius=5)
    if label:
        text = SMALL_FONT.render(label, True, WHITE)
        SCREEN.blit(text, (rect.x + 8, rect.y + rect.height // 2 - text.get_height() // 2))


def draw_metric_card(rect, label, value, color=AURORA_CYAN):
    draw_glass_panel(rect, (18, 31, 38, 178), color, 7, True)
    label_surf = SMALL_FONT.render(label.upper(), True, POLAR_GRAY)
    value_surf = FONT.render(value, True, WHITE)
    SCREEN.blit(label_surf, (rect.x + 12, rect.y + 8))
    SCREEN.blit(value_surf, (rect.x + 12, rect.y + 29))


def draw_top_ui(player, weather):
    bar = pygame.Rect(0, 0, WIDTH, UI_TOP_HEIGHT)
    pygame.draw.rect(SCREEN, (9, 18, 24), bar)
    pygame.draw.line(SCREEN, AURORA_CYAN, (0, UI_TOP_HEIGHT - 2), (WIDTH, UI_TOP_HEIGHT - 2), 2)

    draw_metric_card(pygame.Rect(14, 10, 132, 54), "Funds", f"€{player.money}", AURORA_CYAN if player.money >= 180 else WARNING_RED)
    draw_metric_card(pygame.Rect(158, 10, 122, 54), "Day", player.current_time_text(), GLACIER_BLUE)
    draw_metric_card(pygame.Rect(292, 10, 106, 54), "Life", f"{player.life}/5", TUNDRA_GREEN)
    draw_metric_card(pygame.Rect(410, 10, 110, 54), "Score", str(player.score), AURORA_CYAN)
    draw_metric_card(pygame.Rect(532, 10, 128, 54), "Weather", weather.upper(), GLACIER_BLUE)

    fuel_rect = pygame.Rect(684, 18, 210, 18)
    draw_progress_bar(
        fuel_rect,
        player.fuel,
        100,
        AURORA_CYAN if player.fuel > 25 else WARNING_RED,
        label=f"Fuel {int(player.fuel)}%"
    )
    stability_rect = pygame.Rect(684, 44, 210, 14)
    draw_progress_bar(
        stability_rect,
        player.stability,
        100,
        TUNDRA_GREEN if player.stability > 45 else WARNING_RED,
        label=f"Stability {int(player.stability)}%"
    )

    visited = sum(1 for cp in CHECKPOINTS if cp["visited"])
    progress_rect = pygame.Rect(918, 18, 164, 18)
    draw_progress_bar(progress_rect, visited, len(CHECKPOINTS), GLACIER_BLUE, label=f"Checkpoints {visited}/{len(CHECKPOINTS)}")

    if player.message_timer > 0:
        msg = SMALL_FONT.render(player.message, True, (236, 252, 252))
        SCREEN.blit(msg, (918, 44))

    for i, icon in enumerate(["!", "⚙", "?"]):
        center = (1128 + i * 24, 27)
        pygame.draw.circle(SCREEN, (23, 42, 50), center, 10)
        pygame.draw.circle(SCREEN, AURORA_CYAN, center, 10, 1)
        txt = SMALL_FONT.render(icon, True, WHITE)
        SCREEN.blit(txt, (center[0] - txt.get_width() // 2, center[1] - txt.get_height() // 2))


def draw_speedometer(player):
    center = (WIDTH - 105, HEIGHT - 105)
    radius = 72

    pygame.draw.circle(SCREEN, (17, 28, 34), center, radius)
    pygame.draw.circle(SCREEN, AURORA_CYAN, center, radius, 3)
    pygame.draw.circle(SCREEN, (230, 248, 250), center, radius - 16, 1)

    speed = player.current_speed_kmh()
    max_display = 180
    angle = math.radians(210 + min(speed, max_display) / max_display * 300)

    end_x = center[0] + math.cos(angle) * 52
    end_y = center[1] + math.sin(angle) * 52

    pygame.draw.line(SCREEN, WARNING_RED if speed > 85 else AURORA_CYAN, center, (end_x, end_y), 5)
    pygame.draw.circle(SCREEN, GLACIER_WHITE, center, 6)

    txt = BIG_FONT.render(str(speed), True, WHITE)
    SCREEN.blit(txt, (center[0] - txt.get_width() // 2, center[1] + 12))

    unit = SMALL_FONT.render("km/h", True, POLAR_GRAY)
    SCREEN.blit(unit, (center[0] - unit.get_width() // 2, center[1] + 42))


def draw_task_list(player):
    panel = pygame.Rect(15, 95, 310, 245)
    draw_glass_panel(panel, (226, 242, 246, 188), GLACIER_BLUE, 8)

    title = BIG_FONT.render("Ring Road Tasks", True, LAVA_BLACK)
    SCREEN.blit(title, (30, 105))

    tasks = [
        ("Visit all checkpoints", all(cp["visited"] for cp in CHECKPOINTS)),
        ("Eat at least once per day", player.has_eaten_today),
        ("Rest overnight or return home", True),
        ("Avoid speeding fines", True),
        ("Refuel before fuel runs out", player.fuel > 20),
        ("Keep vehicle stability", player.stability > 35),
    ]

    y = 150
    for text, done in tasks:
        mark = "✓" if done else "•"
        color = TUNDRA_GREEN if done else LAVA_BLACK
        line = FONT.render(f"{mark} {text}", True, color)
        SCREEN.blit(line, (30, y))
        y += 30


def draw_help_box():
    box = pygame.Rect(15, HEIGHT - 105, 500, 90)
    draw_glass_panel(box, (18, 31, 38, 175), AURORA_CYAN, 8)

    lines = [
        "Arrow Keys: Drive / Turn",
        "E near Restaurant: Eat     F near Gas Station: Refuel €40",
        "H: Rest & Accommodate €100     R: Overnight Risk Mode",
        "Highland roads give extra route score; ocean boundary blocks the car",
    ]

    for i, line in enumerate(lines):
        txt = SMALL_FONT.render(line, True, WHITE)
        SCREEN.blit(txt, (30, HEIGHT - 95 + i * 20))


def draw_minimap(player):
    rect = pygame.Rect(WIDTH - 245, 95, 220, 150)
    draw_glass_panel(rect, (225, 242, 246, 188), AURORA_CYAN, 8)

    title = SMALL_FONT.render("Iceland Route", True, LAVA_BLACK)
    SCREEN.blit(title, (rect.x + 8, rect.y + 5))

    for route in ROUTE_NETWORK:
        road_points = [geo_to_minimap(lat, lon, rect) for lat, lon in route["points"]]
        if len(road_points) > 1:
            width = 2 if route["kind"] == "main" else 1
            pygame.draw.lines(SCREEN, route["color"], route.get("closed", False), road_points, width)

    for cp in CHECKPOINTS:
        x, y = geo_to_minimap(cp["lat"], cp["lon"], rect)
        color = AURORA_CYAN if cp["visited"] else POLAR_GRAY
        pygame.draw.circle(SCREEN, color, (x, y), 3)

    px = rect.x + int(player.x / WIDTH * rect.width)
    py = rect.y + int(player.y / HEIGHT * rect.height)
    pygame.draw.circle(SCREEN, WARNING_RED, (px, py), 5)


def draw_floating_texts(floating_texts):
    for ft in floating_texts[:]:
        ft.update()
        ft.draw()
        if ft.life <= 0:
            floating_texts.remove(ft)


# =========================
# Weather System
# =========================

def get_weather(player):
    hour = player.hour()
    day = player.day

    value = (day * 37 + hour * 11) % 100

    if value < 12:
        return "blizzard"
    elif value < 35:
        return "snow"
    else:
        return "clear"


def draw_weather_effect(weather, snow_particles):
    if weather in ["snow", "blizzard"]:
        count = 45 if weather == "snow" else 110

        for i in range(count):
            snow_particles[i].update()
            snow_particles[i].draw()

        if weather == "blizzard":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((230, 240, 255, 45))
            SCREEN.blit(overlay, (0, 0))


# =========================
# Popups
# =========================

def draw_popup_base(title):
    box = pygame.Rect(250, 120, 700, 500)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((3, 10, 14, 112))
    SCREEN.blit(overlay, (0, 0))
    draw_glass_panel(box, (231, 245, 248, 232), AURORA_CYAN, 8)

    t = BIG_FONT.render(title, True, LAVA_BLACK)
    SCREEN.blit(t, (box.x + 35, box.y + 25))
    return box


def restaurant_popup(restaurant, player):
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    if player.money >= 45:
                        player.money -= 45
                        player.has_eaten_today = True
                        player.show_message(f"You ate at {restaurant['name']}! -€45")
                    else:
                        player.show_message("Not enough money to eat.")
                    running = False

                if event.key in [pygame.K_n, pygame.K_ESCAPE]:
                    running = False

        draw_popup_base("Restaurant")

        name = BIG_FONT.render(restaurant["name"], True, LAVA_BLACK)
        SCREEN.blit(name, (300, 210))

        desc = FONT.render("A warm meal helps you survive the Iceland road trip.", True, LAVA_BLACK)
        SCREEN.blit(desc, (300, 265))

        price = FONT.render("Meal Price: €45", True, DARK_GRAY)
        SCREEN.blit(price, (300, 305))

        hint = FONT.render("Y Eat / N Leave", True, WARNING_RED)
        SCREEN.blit(hint, (300, 380))

        pygame.display.flip()
        CLOCK.tick(FPS)


def gas_popup(gas_station, player):
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    cost = 40
                    if player.money >= cost:
                        player.money -= cost
                        player.fuel = 100
                        player.total_refuel_cost += cost
                        player.refuel_count += 1
                        player.show_message(f"Refueled at {gas_station['name']}! -€{cost}")
                    else:
                        player.show_message("Not enough money to refuel.")
                    running = False

                if event.key in [pygame.K_n, pygame.K_ESCAPE]:
                    running = False

        draw_popup_base("Gas Station")

        name = BIG_FONT.render(gas_station["name"], True, LAVA_BLACK)
        SCREEN.blit(name, (300, 210))

        cost = 40
        info = FONT.render(f"Current fuel: {int(player.fuel)}%    Fixed refuel cost: €{cost}", True, LAVA_BLACK)
        SCREEN.blit(info, (300, 270))

        hint = FONT.render("Y Refuel / N Leave", True, WARNING_RED)
        SCREEN.blit(hint, (300, 360))

        pygame.display.flip()
        CLOCK.tick(FPS)


def rest_accommodate(player):
    cost = 100
    if player.money < cost:
        player.show_message("Not enough money for accommodation.")
        return

    player.money -= cost
    player.total_lodging_cost += cost
    player.lodging_count += 1
    player.day += 1
    player.game_minutes = 8 * 60
    player.has_eaten_today = False
    player.stability = min(100, player.stability + 18)
    player.speed = 0
    player.show_message("Rested overnight. New day started. -€100")


def overnight_risk_mode(player):
    player.day += 1
    player.game_minutes = 8 * 60
    player.has_eaten_today = False
    player.life -= 1
    player.stability = max(0, player.stability - 24)
    player.speed = 0
    player.show_message("Overnight drive risk taken. -1 life, vehicle stability reduced.")


def lodging_popup(player):
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    rest_accommodate(player)
                    running = False

                if event.key == pygame.K_r:
                    overnight_risk_mode(player)
                    running = False

                if event.key in [pygame.K_n, pygame.K_ESCAPE]:
                    running = False

        box = draw_popup_base("End-of-Day Travel Choice")
        summary = [
            "Rest & Accommodate: fixed €100, starts the next day at 08:00.",
            "Overnight Drive (Risk Mode): no lodging cost, but loses 1 life and stability.",
            f"Remaining funds: €{player.money}",
            f"Vehicle stability: {int(player.stability)}%"
        ]
        y = box.y + 110
        for line in summary:
            color = WARNING_RED if player.money < 100 and "Remaining" in line else LAVA_BLACK
            txt = FONT.render(line, True, color)
            SCREEN.blit(txt, (box.x + 55, y))
            y += 42

        hint = FONT.render("Y Rest & Accommodate / R Overnight Risk / N Cancel", True, WARNING_RED)
        SCREEN.blit(hint, (box.x + 55, box.y + 385))

        pygame.display.flip()
        CLOCK.tick(FPS)


def load_checkpoint_photos(name):
    """
    Load checkpoint photos without forcing them into a fixed size.
    Photos keep their original aspect ratio.
    """
    if not PHOTO_FOLDER.exists():
        return []

    patterns = [
        str(PHOTO_FOLDER / f"{name}*.jpg"),
        str(PHOTO_FOLDER / f"{name}*.png"),
        str(PHOTO_FOLDER / f"{name}*.jpeg"),
    ]

    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    images = []

    for f in files:
        try:
            img = pygame.image.load(f).convert()
            images.append(img)
        except Exception as e:
            print(f"Could not load photo: {f}")
            print(e)

    return images


def fit_image_keep_ratio(image, max_width, max_height):
    """
    Keep original image ratio.
    If the image is smaller than the display area, keep original size.
    If it is too large, scale it down proportionally.
    """
    original_width = image.get_width()
    original_height = image.get_height()

    if original_width <= max_width and original_height <= max_height:
        return image

    scale = min(max_width / original_width, max_height / original_height)

    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    return pygame.transform.smoothscale(image, (new_width, new_height))


def checkpoint_photo_carousel(cp, player):
    images = load_checkpoint_photos(cp["name"])
    index = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT and images:
                    index = (index + 1) % len(images)

                if event.key == pygame.K_LEFT and images:
                    index = (index - 1) % len(images)

                if event.key in [pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE]:
                    running = False

        draw_popup_base(f"Checkpoint: {cp['name']}")

        # Photo display area
        photo_area = pygame.Rect(300, 190, 600, 360)
        pygame.draw.rect(SCREEN, (230, 240, 245), photo_area)
        pygame.draw.rect(SCREEN, BLACK, photo_area, 3)

        if images:
            original_img = images[index]

            # Keep original ratio, only shrink if too large
            display_img = fit_image_keep_ratio(
                original_img,
                photo_area.width - 20,
                photo_area.height - 20
            )

            img_x = photo_area.centerx - display_img.get_width() // 2
            img_y = photo_area.centery - display_img.get_height() // 2

            SCREEN.blit(display_img, (img_x, img_y))

            size_text = FONT.render(
                f"Photo {index + 1}/{len(images)}  Original: {original_img.get_width()}x{original_img.get_height()}",
                True,
                BLACK
            )
            SCREEN.blit(size_text, (330, 560))

        else:
            text1 = FONT.render("No photo found.", True, BLACK)
            text2 = FONT.render(f"Add photos like: assets/photos/{cp['name']}_1.jpg", True, BLACK)

            SCREEN.blit(text1, (520, 330))
            SCREEN.blit(text2, (390, 370))

        hint = FONT.render("LEFT/RIGHT: switch photo    SPACE: continue", True, RED)
        SCREEN.blit(hint, (390, 600))

        pygame.display.flip()
        CLOCK.tick(FPS)


# =========================
# Menu
# =========================
# =========================
# Stardew-style Main Menu Art
# =========================

class Puffin:
    def __init__(self):
        self.x = random.randint(-200, WIDTH)
        self.y = random.randint(105, 350)
        self.speed = random.uniform(1.8, 3.6)
        self.size = random.randint(16, 26)
        self.phase = random.uniform(0, math.pi * 2)
        self.tilt = random.uniform(-0.18, 0.18)

    def update(self):
        self.x += self.speed
        self.y += math.sin(pygame.time.get_ticks() * 0.0048 + self.phase) * 0.62

        if self.x > WIDTH + 120:
            self.x = random.randint(-260, -80)
            self.y = random.randint(105, 350)
            self.speed = random.uniform(1.8, 3.6)
            self.tilt = random.uniform(-0.18, 0.18)

    def draw(self, surface):
        wing = math.sin(pygame.time.get_ticks() * 0.024 + self.phase)
        x, y, s = self.x, self.y, self.size

        trail = pygame.Surface((int(s * 3), int(s * 1.4)), pygame.SRCALPHA)
        pygame.draw.ellipse(trail, (100, 235, 222, 38), (0, s * 0.45, s * 2.5, s * 0.34))
        surface.blit(trail, (x - s * 2.3, y - s * 0.28))

        # wings
        pygame.draw.polygon(
            surface,
            (11, 16, 19),
            [
                (x - s * 0.15, y),
                (x - s * 1.45, y - wing * s * 0.72),
                (x - s * 0.42, y + s * 0.42)
            ]
        )

        pygame.draw.polygon(
            surface,
            (20, 27, 30),
            [
                (x + s * 0.18, y),
                (x + s * 1.2, y + wing * s * 0.46),
                (x + s * 0.42, y + s * 0.36)
            ]
        )

        # body
        pygame.draw.ellipse(surface, (10, 14, 17), (x - s * 0.58, y - s * 0.43, s * 1.16, s * 1.14))
        pygame.draw.ellipse(surface, GLACIER_WHITE, (x - s * 0.34, y - s * 0.16, s * 0.72, s * 0.72))

        # head
        pygame.draw.circle(surface, (10, 14, 17), (int(x + s * 0.36), int(y - s * 0.43)), int(s * 0.38))
        pygame.draw.circle(surface, GLACIER_WHITE, (int(x + s * 0.47), int(y - s * 0.48)), int(s * 0.17))

        # beak
        pygame.draw.polygon(
            surface,
            (255, 125, 62),
            [
                (x + s * 0.68, y - s * 0.45),
                (x + s * 1.13, y - s * 0.34),
                (x + s * 0.68, y - s * 0.25)
            ]
        )

        # eye
        pygame.draw.circle(surface, BLACK, (int(x + s * 0.48), int(y - s * 0.54)), 2)


def draw_pixel_rect(surface, color, rect, border_color=BLACK, border=4):
    pygame.draw.rect(surface, color, rect)
    pygame.draw.rect(surface, border_color, rect, border)


def draw_sky_gradient(surface):
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(10 + 125 * t)
        g = int(32 + 158 * t)
        b = int(45 + 172 * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))


def draw_pixel_sun(surface):
    t = pygame.time.get_ticks() * 0.001
    sun_x = WIDTH - 158
    sun_y = 115 + math.sin(t) * 6

    for radius, alpha in [(76, 28), (52, 38), (32, 75)]:
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (180, 242, 248, alpha), (radius, radius), radius)
        surface.blit(glow, (sun_x - radius, sun_y - radius))
    pygame.draw.circle(surface, (226, 248, 250), (int(sun_x), int(sun_y)), 24)


def draw_dynamic_mountains(surface):
    t = pygame.time.get_ticks() * 0.001
    aurora = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(4):
        points = []
        for x in range(-60, WIDTH + 80, 60):
            y = 115 + i * 24 + math.sin(x * 0.012 + t * (0.8 + i * 0.2)) * (24 + i * 7)
            points.append((x, y))
        pygame.draw.lines(aurora, (60, 235, 210, 46 - i * 7), False, points, 18 - i * 3)
    surface.blit(aurora, (0, 0))

    # far glacier mountains
    far = [
        (0, 430), (120, 250), (240, 430),
        (360, 238), (540, 430),
        (700, 260), (880, 430),
        (1040, 246), (1200, 430)
    ]
    pygame.draw.polygon(surface, (120, 153, 164), far)
    pygame.draw.lines(surface, (225, 246, 248), False, far, 3)

    # lava-black volcanoes with glacier caps
    volcanoes = [
        {"x": 220, "base": 600, "w": 340, "h": 300, "crater": 48},
        {"x": 600, "base": 610, "w": 430, "h": 360, "crater": 60},
        {"x": 970, "base": 600, "w": 360, "h": 310, "crater": 52},
    ]

    for i, v in enumerate(volcanoes):
        x = v["x"]
        base = v["base"]
        w = v["w"]
        h = v["h"]

        left = x - w // 2
        right = x + w // 2
        top = base - h

        # mountain body
        pygame.draw.polygon(
            surface,
            (35, 49, 50),
            [(left, base), (x - 55, top + 45), (x, top), (x + 55, top + 45), (right, base)]
        )

        # highlight side
        pygame.draw.polygon(
            surface,
            (92, 124, 128),
            [(left + 40, base), (x, top + 8), (x - 20, base)]
        )

        # shadow side
        pygame.draw.polygon(
            surface,
            (13, 20, 21),
            [(x + 15, top + 20), (right - 40, base), (x - 10, base)]
        )

        pygame.draw.polygon(
            surface,
            GLACIER_WHITE,
            [(x - 55, top + 46), (x, top), (x + 55, top + 46), (x + 24, top + 36), (x, top + 18), (x - 25, top + 40)]
        )

        # crater
        crater_y = top + 38 + math.sin(t + i) * 3
        pygame.draw.ellipse(
            surface,
            (10, 14, 15),
            (x - v["crater"], crater_y, v["crater"] * 2, 24)
        )
        pygame.draw.ellipse(
            surface,
            (76, 122, 118),
            (x - v["crater"] + 8, crater_y + 4, v["crater"] * 2 - 16, 12)
        )

        # smoke / steam
        for j in range(4):
            smoke_x = x + math.sin(t * 1.3 + j * 1.8 + i) * 18
            smoke_y = top - 5 - j * 28 - (t * 12 % 28)
            alpha_size = 18 + j * 4
            pygame.draw.circle(
                surface,
                (216, 239, 238),
                (int(smoke_x), int(smoke_y)),
                alpha_size
            )

    # black sand foreground and Ring Road
    pygame.draw.rect(surface, (18, 24, 25), (0, 600, WIDTH, 160))
    pygame.draw.rect(surface, (90, 128, 118), (0, 600, WIDTH, 20))
    road = [(0, 742), (260, 672), (545, 695), (850, 642), (1200, 674)]
    pygame.draw.lines(surface, (7, 10, 11), False, road, 58)
    pygame.draw.lines(surface, (74, 87, 89), False, road, 7)

    for i in range(90):
        gx = (i * 37) % WIDTH
        gy = 620 + (i * 19) % 110
        color = TUNDRA_GREEN if i % 3 == 0 else (63, 91, 83)
        pygame.draw.line(surface, color, (gx, gy), (gx + 4, gy - 8), 2)


def draw_wooden_title(surface, title_logo=None):
    if title_logo:
        logo_rect = title_logo.get_rect(center=(WIDTH // 2, 145))
        glow = pygame.Surface((logo_rect.width + 80, logo_rect.height + 60), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (67, 232, 218, 48), glow.get_rect())
        surface.blit(glow, (logo_rect.x - 40, logo_rect.y - 22))
        surface.blit(title_logo, logo_rect)
        return

    panel = pygame.Rect(WIDTH // 2 - 310, 76, 620, 148)
    draw_soft_shadow(panel, 8, 90)
    pygame.draw.rect(surface, (229, 245, 248, 190), panel, border_radius=8)
    pygame.draw.rect(surface, AURORA_CYAN, panel, 2, border_radius=8)
    title = TITLE_FONT.render("Iceland Driving", True, LAVA_BLACK)
    title2 = BIG_FONT.render("Exploration", True, GLACIER_BLUE)
    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, panel.y + 34))
    surface.blit(title2, (WIDTH // 2 - title2.get_width() // 2, panel.y + 92))


def draw_menu_button(surface, text, rect, selected=False):
    draw_soft_shadow(rect, 8, 72)
    color = (232, 248, 250, 214) if selected else (20, 34, 42, 188)
    border = AURORA_CYAN if selected else (117, 151, 158)
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, color, panel.get_rect(), border_radius=8)
    surface.blit(panel, rect.topleft)
    pygame.draw.rect(surface, border, rect, 2, border_radius=8)
    pygame.draw.line(surface, (255, 255, 255, 88), (rect.x + 12, rect.y + 10), (rect.right - 12, rect.y + 10), 1)

    pygame.draw.circle(surface, border, (rect.x + 30, rect.centery), 7)
    pygame.draw.circle(surface, (17, 28, 34), (rect.x + 30, rect.centery), 3)

    label_color = LAVA_BLACK if selected else WHITE
    label = FONT.render(text, True, label_color)
    surface.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))


def draw_start_menu_background(puffins, title_logo=None):
    draw_sky_gradient(SCREEN)
    draw_pixel_sun(SCREEN)
    draw_dynamic_mountains(SCREEN)

    for puffin in puffins:
        puffin.update()
        puffin.draw(SCREEN)

    # soft overlay for readability
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 8))
    SCREEN.blit(overlay, (0, 0))

    draw_wooden_title(SCREEN, title_logo)

def start_menu():
    selected = 0
    options = ["Story Mode (Single Player)", "Free Roam", "Travel Gallery", "How to Play", "Quit"]
    show_help = False

    puffins = [Puffin() for _ in range(8)]
    title_logo = load_title_logo()

    button_width = 310
    button_height = 54
    start_y = 355

    while True:
        draw_start_menu_background(puffins, title_logo)

        mouse_pos = pygame.mouse.get_pos()

        if show_help:
            panel = pygame.Rect(WIDTH // 2 - 390, 305, 780, 310)
            draw_glass_panel(panel, (229, 245, 248, 228), AURORA_CYAN, 8)

            help_title = BIG_FONT.render("How to Play", True, LAVA_BLACK)
            SCREEN.blit(help_title, (WIDTH // 2 - help_title.get_width() // 2, panel.y + 24))

            help_lines = [
                "Goal: Drive around Iceland and visit all famous checkpoints.",
                "Manage €1000, fuel, vehicle stability, food, lodging and fines.",
                "Refuel at gas stations for a fixed €40.",
                "Rest & Accommodate costs €100 and advances to the next day.",
                "Speed cameras deduct fines and record violations.",
                "Complete every checkpoint to unlock the final trip settlement."
            ]

            y = panel.y + 80
            for line in help_lines:
                txt = FONT.render(line, True, LAVA_BLACK)
                SCREEN.blit(txt, (panel.x + 55, y))
                y += 34

            back_rect = pygame.Rect(WIDTH // 2 - 120, panel.y + 250, 240, 44)
            draw_menu_button(SCREEN, "Back", back_rect, True)

        else:
            button_rects = []

            for i, opt in enumerate(options):
                rect = pygame.Rect(
                    WIDTH // 2 - button_width // 2,
                    start_y + i * 66,
                    button_width,
                    button_height
                )

                button_rects.append(rect)

                # 鼠标悬停时自动选中
                if rect.collidepoint(mouse_pos):
                    selected = i

                draw_menu_button(SCREEN, opt, rect, selected == i)

            hint = FONT.render("Use mouse click or UP / DOWN and ENTER", True, GLACIER_WHITE)
            SCREEN.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 55))

        # small animated caption
        t = pygame.time.get_ticks() * 0.004
        caption_y = 286 + math.sin(t) * 4
        caption = FONT.render(
            "Glacier roads, aurora nights, careful budgets",
            True,
            GLACIER_WHITE
        )
        SCREEN.blit(caption, (WIDTH // 2 - caption.get_width() // 2, caption_y))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            # 鼠标点击事件
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键
                    mouse_pos = pygame.mouse.get_pos()

                    if show_help:
                        if back_rect.collidepoint(mouse_pos):
                            show_help = False
                    else:
                        for i, rect in enumerate(button_rects):
                            if rect.collidepoint(mouse_pos):
                                if i in [0, 1, 2]:
                                    return
                                elif i == 3:
                                    show_help = True
                                elif i == 4:
                                    pygame.quit()
                                    raise SystemExit

            # 键盘事件仍然保留
            if event.type == pygame.KEYDOWN:
                if show_help:
                    if event.key in [pygame.K_BACKSPACE, pygame.K_ESCAPE]:
                        show_help = False
                else:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(options)

                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(options)

                    elif event.key == pygame.K_RETURN:
                        if selected in [0, 1, 2]:
                            return
                        elif selected == 3:
                            show_help = True
                        elif selected == 4:
                            pygame.quit()
                            raise SystemExit

        pygame.display.flip()
        CLOCK.tick(FPS)
# =========================
# Interaction Logic
# =========================

def check_checkpoint_visit(player, floating_texts):
    for cp in CHECKPOINTS:
        if cp["visited"]:
            continue

        cp_pos = geo_to_screen(cp["lat"], cp["lon"])
        if screen_distance((player.x, player.y), cp_pos) < 36:
            cp["visited"] = True
            player.money += 35
            player.score += 120
            player.show_message(f"Visited {cp['name']}! +€35 +120 score")
            floating_texts.append(FloatingText("+€35", player.x, player.y - 30, GREEN))
            floating_texts.append(FloatingText("+120 SCORE", player.x, player.y - 55, YELLOW))
            checkpoint_photo_carousel(cp, player)
            break


def check_restaurant_interaction(player, restaurants):
    for r in restaurants:
        r_pos = geo_to_screen(r["lat"], r["lon"])
        if screen_distance((player.x, player.y), r_pos) < 38:
            restaurant_popup(r, player)
            return


def check_gas_interaction(player, gas_stations):
    for g in gas_stations:
        g_pos = geo_to_screen(g["lat"], g["lon"])
        if screen_distance((player.x, player.y), g_pos) < 45:
            gas_popup(g, player)
            return


def is_near_gas_station(player, gas_stations, radius=45):
    for g in gas_stations:
        g_pos = geo_to_screen(g["lat"], g["lon"])
        if screen_distance((player.x, player.y), g_pos) < radius:
            return True
    return False


def check_speed_camera(player, cameras, floating_texts):
    for i, cam in enumerate(cameras):
        cam_pos = geo_to_screen(cam["lat"], cam["lon"])
        dist = screen_distance((player.x, player.y), cam_pos)

        if i not in player.camera_cooldown:
            player.camera_cooldown[i] = 0

        if dist < 36 and player.camera_cooldown[i] <= 0:
            current_speed = player.current_speed_kmh()
            limit = cam["speed_limit"]

            if current_speed > limit:
                fine = min(350, 50 + (current_speed - limit) * 5)
                player.money -= fine
                player.score -= 80
                player.total_fine_cost += fine
                player.fine_count += 1
                player.stability = max(0, player.stability - 5)
                player.last_violation = {
                    "speed": current_speed,
                    "limit": limit,
                    "fine": fine,
                    "road": cam["name"],
                    "count": player.fine_count
                }
                player.violation_timer = 210
                player.show_message(f"Speeding fine! {current_speed} km/h in {limit} zone. -€{fine}")
                floating_texts.append(FloatingText(f"-€{fine}", player.x, player.y - 40, RED))
                player.camera_cooldown[i] = 260
            else:
                player.show_message(f"Camera passed safely. Limit {limit} km/h")
                floating_texts.append(FloatingText("SAFE", player.x, player.y - 40, GREEN))
                player.camera_cooldown[i] = 150

        if player.camera_cooldown[i] > 0:
            player.camera_cooldown[i] -= 1


def check_ring_road_bonus(player, floating_texts):
    if player.route_score_cooldown > 0:
        return

    p = (player.x, player.y)

    min_dist = 99999
    nearest_route = None
    for route, a, b in iter_route_segments():
        dist = point_to_segment_distance(p, a, b)
        if dist < min_dist:
            min_dist = dist
            nearest_route = route

    if min_dist < 35 and abs(player.speed) > 1.5:
        bonus = 14 if nearest_route and nearest_route["kind"] == "highland" else 10
        player.score += bonus
        player.route_score_cooldown = 90
        label = "+14 HIGHLAND" if bonus > 10 else "+10 ROUTE"
        floating_texts.append(FloatingText(label, player.x, player.y - 25, YELLOW))


def draw_violation_alert(player):
    if not player.last_violation or player.violation_timer <= 0:
        return

    alpha = min(230, 80 + player.violation_timer)
    rect = pygame.Rect(WIDTH // 2 - 230, 94, 460, 132)
    draw_glass_panel(rect, (42, 16, 22, alpha), WARNING_RED, 8)

    v = player.last_violation
    title = BIG_FONT.render("Speeding Penalty", True, WHITE)
    SCREEN.blit(title, (rect.x + 24, rect.y + 18))
    lines = [
        f"{v['speed']} km/h in a {v['limit']} km/h zone",
        f"Road section: {v['road']}",
        f"Fine deducted: €{v['fine']}   Violations this trip: {v['count']}"
    ]
    for i, line in enumerate(lines):
        txt = SMALL_FONT.render(line, True, GLACIER_WHITE)
        SCREEN.blit(txt, (rect.x + 26, rect.y + 58 + i * 22))


def check_game_end(player, gas_stations):
    if player.life <= 0:
        return "lose_life"

    if player.money <= 0:
        return "lose_money"

    if player.fuel <= 0 and not is_near_gas_station(player, gas_stations):
        return "lose_fuel"

    if all(cp["visited"] for cp in CHECKPOINTS):
        return "win"

    return None


def show_end_screen(result, player):
    while True:
        draw_sky_gradient(SCREEN)
        draw_dynamic_mountains(SCREEN)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 12, 18, 105))
        SCREEN.blit(overlay, (0, 0))

        if result == "win":
            title_text = "Ring Road Completed"
            title_color = AURORA_CYAN
            subtitle_text = "You completed every Iceland checkpoint."
        elif result == "lose_life":
            title_text = "Journey Failed"
            title_color = WARNING_RED
            subtitle_text = "You lost all lives."
        elif result == "lose_fuel":
            title_text = "Journey Failed"
            title_color = WARNING_RED
            subtitle_text = "You ran out of fuel away from a gas station."
        else:
            title_text = "Journey Failed"
            title_color = WARNING_RED
            subtitle_text = "You ran out of money."

        panel = pygame.Rect(WIDTH // 2 - 360, 126, 720, 460)
        draw_glass_panel(panel, (230, 245, 248, 226), title_color, 8)

        title = TITLE_FONT.render(title_text, True, LAVA_BLACK)
        subtitle = FONT.render(subtitle_text, True, DARK_GRAY)
        SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, panel.y + 34))
        SCREEN.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, panel.y + 92))

        visited = sum(1 for cp in CHECKPOINTS if cp["visited"])
        completion = int(visited / len(CHECKPOINTS) * 100)
        stats = [
            ("Total distance", f"{player.total_km()} km"),
            ("Trip time", f"{player.day} days"),
            ("Total spend", f"€{player.total_spend()}"),
            ("Refuel + lodging + fines", f"€{player.total_refuel_cost} + €{player.total_lodging_cost} + €{player.total_fine_cost}"),
            ("Speeding violations", str(player.fine_count)),
            ("Checkpoint completion", f"{completion}%"),
            ("Remaining funds", f"€{player.money}"),
            ("Final stability", f"{int(player.stability)}%"),
        ]

        x1 = panel.x + 70
        y = panel.y + 145
        for i, (label, value) in enumerate(stats):
            col_x = x1 if i % 2 == 0 else panel.x + 390
            row_y = y + (i // 2) * 64
            label_surf = SMALL_FONT.render(label.upper(), True, DARK_GRAY)
            value_surf = FONT.render(value, True, LAVA_BLACK)
            SCREEN.blit(label_surf, (col_x, row_y))
            SCREEN.blit(value_surf, (col_x, row_y + 22))

        badges = []
        if result == "win" and player.fine_count == 0:
            badges.append("Perfect clean driving")
        if player.refuel_count > 0:
            badges.append("Planned fuel supply")
        if player.fine_count > 0:
            badges.append("Speed penalty record")
        if player.lodging_count > 0:
            badges.append("Rested traveler")

        badge_x = panel.x + 70
        for badge in badges[:3]:
            badge_rect = pygame.Rect(badge_x, panel.y + 392, 180, 34)
            pygame.draw.rect(SCREEN, (20, 36, 42), badge_rect, border_radius=6)
            pygame.draw.rect(SCREEN, AURORA_CYAN, badge_rect, 1, border_radius=6)
            txt = SMALL_FONT.render(badge, True, GLACIER_WHITE)
            SCREEN.blit(txt, (badge_rect.centerx - txt.get_width() // 2, badge_rect.centery - txt.get_height() // 2))
            badge_x += 196

        hint = FONT.render("Press ESC to quit", True, GLACIER_WHITE)
        SCREEN.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 632))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit

        pygame.display.flip()
        CLOCK.tick(FPS)


# =========================
# Main Game Loop
# =========================

def main():
    start_menu()

    restaurants = load_restaurants()
    gas_stations = load_gas_stations()
    cameras = load_speed_cameras()
    map_image = load_map_background()

    player = Player()

    floating_texts = []
    snow_particles = [SnowParticle() for _ in range(120)]

    show_tasks = True

    running = True
    while running:
        keys = pygame.key.get_pressed()
        weather = get_weather(player)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                if event.key == pygame.K_t:
                    show_tasks = not show_tasks

                if event.key == pygame.K_e:
                    check_restaurant_interaction(player, restaurants)

                if event.key == pygame.K_f:
                    check_gas_interaction(player, gas_stations)

                if event.key == pygame.K_h:
                    lodging_popup(player)

                if event.key == pygame.K_r:
                    overnight_risk_mode(player)

        player.update(keys, weather)

        check_checkpoint_visit(player, floating_texts)
        check_speed_camera(player, cameras, floating_texts)
        check_ring_road_bonus(player, floating_texts)

        result = check_game_end(player, gas_stations)
        if result:
            show_end_screen(result, player)

        global CURRENT_CAMERA
        CURRENT_CAMERA = get_follow_camera(player) if FOLLOW_CAMERA else None

        draw_background(map_image, player, CURRENT_CAMERA)
        draw_ring_road(CURRENT_CAMERA)
        draw_speed_cameras(cameras, CURRENT_CAMERA)
        draw_restaurants(restaurants, CURRENT_CAMERA)
        draw_gas_stations(gas_stations, CURRENT_CAMERA)
        draw_checkpoints(CURRENT_CAMERA)
        draw_car(player)

        draw_top_ui(player, weather)

        if show_tasks:
            draw_task_list(player)

        draw_minimap(player)
        draw_speedometer(player)
        draw_help_box()
        draw_violation_alert(player)
        draw_floating_texts(floating_texts)

        pygame.display.flip()
        CLOCK.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
