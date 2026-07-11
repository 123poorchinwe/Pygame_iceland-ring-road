import pygame
import math
import csv
import json
import os
import random
import glob
from datetime import datetime

# =========================
# Basic Settings
# =========================

pygame.init()

WIDTH, HEIGHT = 1100, 720
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iceland Ring Road Challenge")

CLOCK = pygame.time.Clock()
FPS = 60

# Pixel-style colors
WHITE = (245, 245, 245)
BLACK = (20, 20, 20)
BLUE = (70, 130, 180)
DARK_BLUE = (20, 40, 70)
GREEN = (90, 180, 110)
RED = (220, 70, 70)
YELLOW = (245, 210, 90)
ORANGE = (240, 150, 60)
GRAY = (120, 120, 120)
DARK_GRAY = (50, 50, 50)
ICE = (190, 230, 240)

def make_font(size, bold=False):
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except (TypeError, OSError, pygame.error):
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        return font


FONT = make_font(18)
BIG_FONT = make_font(30, bold=True)
TITLE_FONT = make_font(42, bold=True)

# Iceland bounding box for simple map projection
LAT_MIN, LAT_MAX = 63.0, 66.8
LON_MIN, LON_MAX = -24.8, -13.0

# Game data files
RESTAURANT_FILE = "restaurants_iceland.json"
SPEED_CAMERA_FILE = "speed_cameras_iceland.csv"
PHOTO_FOLDER = "assets/photos"


# =========================
# Geo Conversion
# =========================

def geo_to_screen(lat, lon):
    """
    Convert latitude and longitude to screen coordinates.
    This is a simple equirectangular projection for gameplay.
    """
    x = int((lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH)
    y = int((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT)
    return x, y


def screen_distance(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


# =========================
# Game Nodes
# =========================

CHECKPOINTS = [
    {"name": "Reykjavik", "lat": 64.1466, "lon": -21.9426, "visited": False},
    {"name": "Thingvellir National Park", "lat": 64.2559, "lon": -21.1295, "visited": False},
    {"name": "Geysir", "lat": 64.3104, "lon": -20.3024, "visited": False},
    {"name": "Gullfoss", "lat": 64.3271, "lon": -20.1199, "visited": False},
    {"name": "Seljalandsfoss", "lat": 63.6156, "lon": -19.9886, "visited": False},
    {"name": "Skogafoss", "lat": 63.5321, "lon": -19.5114, "visited": False},
    {"name": "Vik", "lat": 63.4186, "lon": -19.0060, "visited": False},
    {"name": "Jokulsarlon Glacier Lagoon", "lat": 64.0481, "lon": -16.1794, "visited": False},
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
# Load Restaurants
# =========================

def load_restaurants():
    """
    Load restaurants from local JSON file.
    If the file does not exist, create demo restaurant points.
    """
    if os.path.exists(RESTAURANT_FILE):
        with open(RESTAURANT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # Demo fallback data
    demo_restaurants = [
        {"name": "Reykjavik Food Hall", "lat": 64.1475, "lon": -21.9330},
        {"name": "Vik Local Restaurant", "lat": 63.4190, "lon": -19.0050},
        {"name": "Akureyri Diner", "lat": 65.6900, "lon": -18.1200},
        {"name": "Hofn Seafood House", "lat": 64.2500, "lon": -15.2100},
        {"name": "Egilsstadir Cafe", "lat": 65.2650, "lon": -14.3900},
    ]
    return demo_restaurants


# =========================
# Load Speed Cameras
# =========================

def load_speed_cameras():
    """
    Load speed cameras from CSV.
    Expected columns:
    name,lat,lon,speed_limit

    Example:
    Camera_001,64.12,-21.80,90
    """
    cameras = []

    if not os.path.exists(SPEED_CAMERA_FILE):
        # Demo fallback cameras
        return [
            {"name": "Demo Camera 1", "lat": 64.20, "lon": -21.50, "speed_limit": 80},
            {"name": "Demo Camera 2", "lat": 63.70, "lon": -19.80, "speed_limit": 70},
            {"name": "Demo Camera 3", "lat": 65.50, "lon": -18.20, "speed_limit": 90},
            {"name": "Demo Camera 4", "lat": 64.30, "lon": -15.50, "speed_limit": 80},
        ]

    with open(SPEED_CAMERA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                cameras.append({
                    "name": row.get("name", "Speed Camera"),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "speed_limit": int(row.get("speed_limit", 80))
                })
            except Exception:
                continue

    return cameras


# =========================
# Player Class
# =========================

class Player:
    def __init__(self):
        self.x, self.y = geo_to_screen(HOME["lat"], HOME["lon"])
        self.speed = 0
        self.angle = 0
        self.max_speed = 6
        self.acceleration = 0.12
        self.friction = 0.04

        self.money = 1000
        self.life = 5
        self.has_eaten_today = False
        self.day = 1
        self.game_minutes = 8 * 60  # Start at 08:00

        self.message = "Welcome to Iceland Ring Road Challenge!"
        self.message_timer = 240

        self.camera_cooldown = {}

    def update(self, keys):
        if keys[pygame.K_UP]:
            self.speed += self.acceleration
        elif keys[pygame.K_DOWN]:
            self.speed -= self.acceleration
        else:
            if self.speed > 0:
                self.speed -= self.friction
            elif self.speed < 0:
                self.speed += self.friction

        self.speed = max(-2.5, min(self.speed, self.max_speed))

        if keys[pygame.K_LEFT]:
            self.angle -= 3
        if keys[pygame.K_RIGHT]:
            self.angle += 3

        rad = math.radians(self.angle)
        self.x += math.sin(rad) * self.speed
        self.y -= math.cos(rad) * self.speed

        self.x = max(0, min(WIDTH, self.x))
        self.y = max(0, min(HEIGHT, self.y))

        # Time passes faster when driving
        time_factor = 0.045 + abs(self.speed) * 0.035
        self.game_minutes += time_factor

        if self.game_minutes >= 24 * 60:
            self.game_minutes -= 24 * 60
            self.day += 1

            if not self.has_eaten_today:
                self.life -= 1
                self.show_message("You skipped meals yesterday! -1 life")

            self.has_eaten_today = False

        # If after 02:00 and before 08:00, player must be home
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

    def show_message(self, text):
        self.message = text
        self.message_timer = 240

    def current_time_text(self):
        h = int(self.game_minutes // 60)
        m = int(self.game_minutes % 60)
        return f"Day {self.day}  {h:02d}:{m:02d}"

    def current_speed_kmh(self):
        return int(abs(self.speed) * 25)


# =========================
# Drawing Functions
# =========================

def draw_pixel_background():
    SCREEN.fill(ICE)

    # Ocean
    pygame.draw.rect(SCREEN, (95, 160, 200), (0, 0, WIDTH, HEIGHT))

    # Simplified Iceland landmass
    island_points = [
        geo_to_screen(66.3, -24.0),
        geo_to_screen(66.5, -20.5),
        geo_to_screen(66.2, -16.0),
        geo_to_screen(65.2, -13.8),
        geo_to_screen(64.0, -14.2),
        geo_to_screen(63.3, -18.0),
        geo_to_screen(63.5, -22.0),
        geo_to_screen(64.5, -24.3),
    ]
    pygame.draw.polygon(SCREEN, (170, 210, 165), island_points)
    pygame.draw.polygon(SCREEN, (80, 120, 90), island_points, 4)

    # Pixel-style mountains
    for _ in range(35):
        x = random.randint(120, WIDTH - 120)
        y = random.randint(110, HEIGHT - 120)
        pygame.draw.polygon(
            SCREEN,
            (130, 150, 135),
            [(x, y), (x - 8, y + 16), (x + 8, y + 16)]
        )


def draw_ring_road():
    """
    Draw a rough ring road by connecting checkpoints.
    """
    points = [geo_to_screen(p["lat"], p["lon"]) for p in CHECKPOINTS]
    if len(points) > 2:
        pygame.draw.lines(SCREEN, DARK_GRAY, True, points, 5)
        pygame.draw.lines(SCREEN, GRAY, True, points, 2)


def draw_car(player):
    car_surface = pygame.Surface((26, 38), pygame.SRCALPHA)
    pygame.draw.rect(car_surface, RED, (6, 4, 14, 28))
    pygame.draw.rect(car_surface, YELLOW, (8, 7, 10, 7))
    pygame.draw.rect(car_surface, BLACK, (4, 8, 4, 6))
    pygame.draw.rect(car_surface, BLACK, (18, 8, 4, 6))
    pygame.draw.rect(car_surface, BLACK, (4, 24, 4, 6))
    pygame.draw.rect(car_surface, BLACK, (18, 24, 4, 6))

    rotated = pygame.transform.rotate(car_surface, -player.angle)
    rect = rotated.get_rect(center=(player.x, player.y))
    SCREEN.blit(rotated, rect)


def draw_checkpoints():
    for cp in CHECKPOINTS:
        x, y = geo_to_screen(cp["lat"], cp["lon"])
        color = GREEN if cp["visited"] else ORANGE
        pygame.draw.rect(SCREEN, color, (x - 6, y - 6, 12, 12))
        pygame.draw.rect(SCREEN, BLACK, (x - 6, y - 6, 12, 12), 2)

        label = FONT.render(cp["name"], True, BLACK)
        SCREEN.blit(label, (x + 8, y - 8))


def draw_restaurants(restaurants):
    for r in restaurants:
        x, y = geo_to_screen(r["lat"], r["lon"])
        pygame.draw.circle(SCREEN, YELLOW, (x, y), 6)
        pygame.draw.circle(SCREEN, BLACK, (x, y), 6, 1)
        txt = FONT.render("R", True, BLACK)
        SCREEN.blit(txt, (x - 5, y - 10))


def draw_speed_cameras(cameras):
    for cam in cameras:
        x, y = geo_to_screen(cam["lat"], cam["lon"])
        pygame.draw.rect(SCREEN, BLACK, (x - 5, y - 5, 10, 10))
        pygame.draw.rect(SCREEN, WHITE, (x - 3, y - 3, 6, 6))


def draw_ui(player):
    pygame.draw.rect(SCREEN, DARK_BLUE, (0, 0, WIDTH, 72))
    pygame.draw.rect(SCREEN, BLACK, (0, 0, WIDTH, 72), 3)

    texts = [
        f"Time: {player.current_time_text()}",
        f"Speed: {player.current_speed_kmh()} km/h",
        f"Money: €{player.money}",
        f"Life: {player.life}",
        f"Eaten Today: {'Yes' if player.has_eaten_today else 'No'}",
    ]

    x = 15
    for t in texts:
        surf = FONT.render(t, True, WHITE)
        SCREEN.blit(surf, (x, 18))
        x += 205

    visited = sum(1 for cp in CHECKPOINTS if cp["visited"])
    progress = FONT.render(f"Checkpoints: {visited}/{len(CHECKPOINTS)}", True, WHITE)
    SCREEN.blit(progress, (15, 45))

    if player.message_timer > 0:
        msg = FONT.render(player.message, True, YELLOW)
        SCREEN.blit(msg, (360, 45))


def draw_help_box():
    pygame.draw.rect(SCREEN, (255, 255, 255), (15, HEIGHT - 95, 390, 80))
    pygame.draw.rect(SCREEN, BLACK, (15, HEIGHT - 95, 390, 80), 3)

    lines = [
        "Controls: Arrow Keys = Drive / Turn",
        "Press E near restaurant to eat",
        "Return home before 02:00 or lose life",
        "Avoid speeding near cameras"
    ]

    for i, line in enumerate(lines):
        txt = FONT.render(line, True, BLACK)
        SCREEN.blit(txt, (28, HEIGHT - 85 + i * 18))


# =========================
# Popup Functions
# =========================

def show_checkpoint_popup(name):
    popup_running = True

    image = None
    photo_patterns = [
        os.path.join(PHOTO_FOLDER, f"{name}*.jpg"),
        os.path.join(PHOTO_FOLDER, f"{name}*.png"),
        os.path.join(PHOTO_FOLDER, f"{name}*.jpeg"),
    ]

    photo_files = []
    for pattern in photo_patterns:
        photo_files.extend(glob.glob(pattern))

    if photo_files:
        try:
            image = pygame.image.load(photo_files[0])
        except pygame.error:
            image = None

    if image:
        image = pygame.transform.scale(image, (520, 320))

    while popup_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                    popup_running = False

        pygame.draw.rect(SCREEN, WHITE, (250, 120, 600, 460))
        pygame.draw.rect(SCREEN, BLACK, (250, 120, 600, 460), 5)

        title = BIG_FONT.render(f"Checkpoint: {name}", True, BLACK)
        SCREEN.blit(title, (285, 145))

        if image:
            SCREEN.blit(image, (290, 200))
        else:
            pygame.draw.rect(SCREEN, ICE, (290, 200, 520, 320))
            no_img = FONT.render("Photo not found. Add image to assets/photos/", True, BLACK)
            SCREEN.blit(no_img, (360, 350))

        hint = FONT.render("Press SPACE or ENTER to continue", True, DARK_GRAY)
        SCREEN.blit(hint, (390, 540))

        pygame.display.flip()
        CLOCK.tick(FPS)


# =========================
# Interaction Logic
# =========================

def check_checkpoint_visit(player):
    for cp in CHECKPOINTS:
        if cp["visited"]:
            continue

        cp_pos = geo_to_screen(cp["lat"], cp["lon"])
        if screen_distance((player.x, player.y), cp_pos) < 35:
            cp["visited"] = True
            player.money += 100
            player.show_message(f"Visited {cp['name']}! +€100")
            show_checkpoint_popup(cp["name"])
            break


def check_restaurant_interaction(player, restaurants, keys):
    if not keys[pygame.K_e]:
        return

    for r in restaurants:
        r_pos = geo_to_screen(r["lat"], r["lon"])
        if screen_distance((player.x, player.y), r_pos) < 35:
            if player.money >= 25:
                player.money -= 25
                player.has_eaten_today = True
                player.show_message(f"You ate at {r['name']}! -€25")
            else:
                player.show_message("Not enough money to eat!")
            return


def check_speed_camera(player, cameras):
    for i, cam in enumerate(cameras):
        cam_pos = geo_to_screen(cam["lat"], cam["lon"])
        dist = screen_distance((player.x, player.y), cam_pos)

        if dist < 35:
            current_speed = player.current_speed_kmh()
            limit = cam["speed_limit"]

            if i not in player.camera_cooldown:
                player.camera_cooldown[i] = 0

            if player.camera_cooldown[i] <= 0:
                if current_speed > limit:
                    fine = min(300, 50 + (current_speed - limit) * 5)
                    player.money -= fine
                    player.show_message(
                        f"Speeding fine! {current_speed} km/h in {limit} zone. -€{fine}"
                    )
                    player.camera_cooldown[i] = 240
                else:
                    player.show_message(f"Camera passed safely. Limit {limit} km/h")
                    player.camera_cooldown[i] = 120

        if i in player.camera_cooldown and player.camera_cooldown[i] > 0:
            player.camera_cooldown[i] -= 1


def check_game_end(player):
    if player.life <= 0:
        return "lose_life"

    if player.money <= 0:
        return "lose_money"

    if all(cp["visited"] for cp in CHECKPOINTS):
        return "win"

    return None


def show_end_screen(result):
    while True:
        SCREEN.fill(BLACK)

        if result == "win":
            title = TITLE_FONT.render("YOU COMPLETED THE ICELAND ROAD TRIP!", True, GREEN)
            subtitle = FONT.render("All checkpoints visited. Great driving!", True, WHITE)
        elif result == "lose_life":
            title = TITLE_FONT.render("GAME OVER", True, RED)
            subtitle = FONT.render("You lost all lives.", True, WHITE)
        else:
            title = TITLE_FONT.render("GAME OVER", True, RED)
            subtitle = FONT.render("You ran out of money.", True, WHITE)

        SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, 260))
        SCREEN.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 330))

        hint = FONT.render("Press ESC to quit", True, GRAY)
        SCREEN.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 390))

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
    restaurants = load_restaurants()
    cameras = load_speed_cameras()
    player = Player()

    running = True

    while running:
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        player.update(keys)

        check_checkpoint_visit(player)
        check_restaurant_interaction(player, restaurants, keys)
        check_speed_camera(player, cameras)

        result = check_game_end(player)
        if result:
            show_end_screen(result)

        draw_pixel_background()
        draw_ring_road()
        draw_speed_cameras(cameras)
        draw_restaurants(restaurants)
        draw_checkpoints()
        draw_car(player)
        draw_ui(player)
        draw_help_box()

        pygame.display.flip()
        CLOCK.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
