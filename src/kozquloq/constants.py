"""Audit thresholds, categories and drawing colors (spec §3.3, §5.1)."""

# Kinematic violation thresholds
VEHICLE_ACCEL_MAX_MPS2 = 12.0
PEDESTRIAN_ACCEL_MAX_MPS2 = 8.0
DEFAULT_ACCEL_MAX_MPS2 = 12.0
SCALE_VARIANCE_MAX = 0.15

# Ghost-label rule: 0 LiDAR points inside a box closer than this
GHOST_DISTANCE_LIMIT_M = 35.0

# Lidar-frame z cutoff: returns below this are road-surface ground plane
GROUND_PLANE_Z_MAX_M = -2.0

# Ghost checks only apply to rigid/movable object categories
GHOSTABLE_PREFIXES = ("vehicle.", "human.pedestrian.")

# Sensor health
UNDEREXPOSED_MEAN_INTENSITY = 25.0  # 0..255

# Severity score weights (must sum <= 1.0)
W_GHOST = 0.55
W_KINEMATIC = 0.25
W_SCALE = 0.20

PEDESTRIAN_PREFIXES = ("human.", "animal")
RIGID_PREFIXES = ("vehicle.", "movable_object.barrier")

# RGB colors for report badges / semantic naming
COLOR_CLEAN = (0, 255, 0)
COLOR_GHOST = (255, 0, 0)
COLOR_KINEMATIC = (255, 165, 0)
COLOR_SCALE = (0, 128, 255)

BOX_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),  # bottom face
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),  # top face
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),  # pillars
]
