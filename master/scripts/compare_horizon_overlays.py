#!/usr/bin/env python3
"""Overlay multiple horizon representations to compare DEM-projected vs image-detected skylines.

Overlays:
- Orange line: Artificial horizon from accelerometer (pitch + roll)
- Red X: Tannhorn summit projected from DEM coordinates
- Black line: Full horizon from DEM ray-casting (100m-10km)
- Magenta line: Skyline detected from image using edge detection
"""

import argparse
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageOps
from pyproj import Transformer


# =============================================================================
# Camera Pose (6 DOF)
# =============================================================================

@dataclass
class CameraPose:
    """Camera position and orientation in 6 degrees of freedom."""
    lat: float      # degrees
    lon: float      # degrees
    alt: float      # meters
    heading: float  # degrees (0=N, 90=E)
    pitch: float    # degrees (positive=up)
    roll: float     # degrees (positive=clockwise)
    fov_h: float    # degrees
    fov_v: float    # degrees

    @classmethod
    def from_exif(cls, image_path: Path, dem_path: Path = None) -> 'CameraPose':
        """Initialize from EXIF, optionally using DEM for altitude."""
        params = extract_camera_params(image_path)

        alt = params['alt']

        # If DEM provided, use DEM elevation instead of GPS altitude
        if dem_path:
            dem_data, dem_transform, dem_crs = load_dem(dem_path)
            transformer = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=False)
            dem_alt = get_elevation(dem_data, dem_transform, params['lat'], params['lon'], transformer)
            if dem_alt is not None:
                alt = dem_alt

        return cls(
            lat=params['lat'],
            lon=params['lon'],
            alt=alt,
            heading=params['heading'],
            pitch=params['pitch'],
            roll=params['roll'],
            fov_h=params['fov_h'],
            fov_v=params['fov_v'],
        )


# =============================================================================
# EXIF Parsing
# =============================================================================

def parse_dms_to_decimal(dms_str: str) -> float:
    """Convert DMS string like '45 deg 58' 7.61" N' to decimal degrees."""
    match = re.match(r"(\d+)\s*deg\s*(\d+)'\s*([\d.]+)\"\s*([NSEW])", dms_str)
    if not match:
        raise ValueError(f"Cannot parse DMS string: {dms_str}")

    degrees = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    direction = match.group(4)

    decimal = degrees + minutes / 60 + seconds / 3600
    if direction in ('S', 'W'):
        decimal = -decimal
    return decimal


def parse_acceleration_vector(accel_str: str) -> tuple[float, float, float]:
    """Parse acceleration vector string like '0.048 -0.955 0.297' to tuple."""
    parts = accel_str.split()
    if len(parts) != 3:
        raise ValueError(f"Cannot parse acceleration vector: {accel_str}")
    return tuple(float(p) for p in parts)


def calculate_pitch_from_acceleration(az: float) -> float:
    """Calculate pitch angle from acceleration vector Z component."""
    az = max(-1.0, min(1.0, az))
    return math.degrees(math.asin(az))


def calculate_roll_from_acceleration(ax: float, ay: float) -> float:
    """Calculate roll angle from acceleration vector X and Y components."""
    return math.degrees(math.atan2(ax, -ay))


def extract_camera_params(image_path: Path) -> dict:
    """Extract all camera parameters from EXIF using exiftool."""
    result = subprocess.run(
        ["exiftool", "-json", str(image_path)],
        capture_output=True,
        text=True,
        check=True
    )
    data = json.loads(result.stdout)[0]

    # GPS Position
    lat = parse_dms_to_decimal(data["GPSLatitude"])
    lon = parse_dms_to_decimal(data["GPSLongitude"])

    # Altitude
    alt_str = data.get("GPSAltitude", "0")
    if isinstance(alt_str, str):
        alt = float(re.match(r"([\d.]+)", alt_str).group(1))
    else:
        alt = float(alt_str)

    # Heading
    heading = float(data["GPSImgDirection"])

    # Pitch and roll from acceleration vector
    accel = parse_acceleration_vector(data["AccelerationVector"])
    pitch = calculate_pitch_from_acceleration(accel[2])
    roll = calculate_roll_from_acceleration(accel[0], accel[1])

    # Field of View
    fov_str = data.get("FOV") or data.get("FieldOfView", "50")
    if isinstance(fov_str, str):
        sensor_fov = float(re.match(r"([\d.]+)", fov_str).group(1))
    else:
        sensor_fov = float(fov_str)

    # Orientation and FOV calculation
    orientation = data.get("Orientation", "Horizontal")
    sensor_vfov = 2 * math.degrees(math.atan(
        math.tan(math.radians(sensor_fov / 2)) * 3 / 4
    ))

    if "90" in str(orientation):
        fov_h = sensor_vfov
        fov_v = sensor_fov
    else:
        fov_h = sensor_fov
        fov_v = sensor_vfov

    return {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "heading": heading,
        "pitch": pitch,
        "roll": roll,
        "fov_h": fov_h,
        "fov_v": fov_v,
    }


# =============================================================================
# DEM Loading Utilities
# =============================================================================

def load_dem(dem_path: Path) -> tuple[np.ndarray, rasterio.Affine, rasterio.CRS]:
    """Load DEM and return elevation array with transform."""
    with rasterio.open(dem_path) as src:
        elevation = src.read(1)
        transform = src.transform
        crs = src.crs
    return elevation, transform, crs


def get_elevation(dem_data: np.ndarray, transform: rasterio.Affine, lat: float, lon: float,
                  transformer: Transformer = None, interpolate: bool = True) -> float | None:
    """Query elevation at a point. Returns None if outside bounds."""
    if transformer:
        x, y = transformer.transform(lat, lon)
    else:
        x, y = lon, lat

    inv_transform = ~transform
    col, row = inv_transform * (x, y)

    if not interpolate:
        row_int = int(row)
        col_int = int(col)
        if row_int < 0 or row_int >= dem_data.shape[0] or col_int < 0 or col_int >= dem_data.shape[1]:
            return None
        return float(dem_data[row_int, col_int])

    row0 = int(row)
    col0 = int(col)
    row1 = row0 + 1
    col1 = col0 + 1

    if row0 < 0 or row1 >= dem_data.shape[0] or col0 < 0 or col1 >= dem_data.shape[1]:
        return None

    row_frac = row - row0
    col_frac = col - col0

    z00 = dem_data[row0, col0]
    z01 = dem_data[row0, col1]
    z10 = dem_data[row1, col0]
    z11 = dem_data[row1, col1]

    z0 = z00 * (1 - col_frac) + z01 * col_frac
    z1 = z10 * (1 - col_frac) + z11 * col_frac
    z = z0 * (1 - row_frac) + z1 * row_frac

    return float(z)


# =============================================================================
# Coordinate Utilities
# =============================================================================

def destination_point(lat: float, lon: float, bearing: float, distance: float) -> tuple[float, float]:
    """Calculate destination point given start point, bearing (degrees), and distance (meters)."""
    R = 6371000

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)

    angular_dist = distance / R

    lat2 = math.asin(
        math.sin(lat_rad) * math.cos(angular_dist) +
        math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing_rad)
    )
    lon2 = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_dist) * math.cos(lat_rad),
        math.cos(angular_dist) - math.sin(lat_rad) * math.sin(lat2)
    )

    return math.degrees(lat2), math.degrees(lon2)


def haversine_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2 in degrees."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate horizontal distance between two points in meters."""
    R = 6371000

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def normalize_angle(angle: float) -> float:
    """Normalize angle to range [-180, 180]."""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


# =============================================================================
# Projection
# =============================================================================

def project_point(
    lat: float, lon: float, alt: float,
    camera_lat: float, camera_lon: float, camera_alt: float,
    camera_heading: float, camera_pitch: float,
    fov_h: float, fov_v: float,
    min_distance: float = 100.0
) -> tuple[float, float] | None:
    """Project a GPS point to normalized image coordinates."""
    bearing = haversine_bearing(camera_lat, camera_lon, lat, lon)
    h_distance = haversine_distance(camera_lat, camera_lon, lat, lon)

    delta_elevation = alt - camera_alt
    dist_3d = math.sqrt(h_distance ** 2 + delta_elevation ** 2)
    if dist_3d < min_distance:
        return None

    elevation_angle = math.degrees(math.atan2(delta_elevation, h_distance))

    relative_bearing = normalize_angle(bearing - camera_heading)
    relative_pitch = elevation_angle - camera_pitch

    half_fov_h = fov_h / 2
    half_fov_v = fov_v / 2

    if abs(relative_bearing) > half_fov_h or abs(relative_pitch) > half_fov_v:
        return None

    norm_x = relative_bearing / half_fov_h
    norm_y = -relative_pitch / half_fov_v

    return (norm_x, norm_y)


# =============================================================================
# DEM Horizon Computation
# =============================================================================

def compute_horizon(
    cam_lat: float, cam_lon: float, cam_alt: float,
    heading: float, pitch: float, fov_h: float, fov_v: float,
    dem_data: np.ndarray, transform: rasterio.Affine,
    transformer: Transformer = None,
    num_rays: int = 300,
    min_distance: float = 100,    # Ignore terrain within 100m
    max_distance: float = 10000,  # 10km max
    step_size: float = 30,        # Match DEM resolution
    extra_fov: float = 20,        # Compute rays this many degrees beyond FOV edges
) -> list[tuple[float, float]]:
    """
    Compute horizon by finding max elevation angle along each azimuth.
    Computes rays for fov_h + 2*extra_fov degrees, but only returns points within FOV.
    Falls back to 0° elevation (artificial horizon) if no terrain found.
    """
    horizon_points = []

    # Compute across extended FOV for clean edges
    extended_fov = fov_h + 2 * extra_fov

    for i in range(num_rays):
        azimuth = heading - extended_fov / 2 + (i / (num_rays - 1)) * extended_fov

        max_elevation_angle = -90
        best_point = None

        # Ray-cast from min to max distance
        for distance in range(int(min_distance), int(max_distance), int(step_size)):
            point_lat, point_lon = destination_point(cam_lat, cam_lon, azimuth, distance)
            terrain_alt = get_elevation(dem_data, transform, point_lat, point_lon, transformer)

            if terrain_alt is None:
                continue

            delta_elevation = terrain_alt - cam_alt
            elevation_angle = math.degrees(math.atan2(delta_elevation, distance))

            if elevation_angle > max_elevation_angle:
                max_elevation_angle = elevation_angle
                best_point = (point_lat, point_lon, terrain_alt)

        # Project result (or fall back to artificial horizon)
        if best_point is not None:
            result = project_point(
                best_point[0], best_point[1], best_point[2],
                cam_lat, cam_lon, cam_alt,
                heading, pitch, fov_h, fov_v,
                min_distance=0
            )
            if result is not None:
                horizon_points.append(result)
        else:
            # No terrain found - use artificial horizon (0° elevation)
            relative_bearing = normalize_angle(azimuth - heading)
            relative_pitch = 0 - pitch  # 0° elevation relative to camera pitch
            half_fov_h = fov_h / 2
            half_fov_v = fov_v / 2
            if abs(relative_bearing) <= half_fov_h:
                norm_x = relative_bearing / half_fov_h
                norm_y = -relative_pitch / half_fov_v
                horizon_points.append((norm_x, norm_y))

    return horizon_points


# =============================================================================
# Skyline Detection from Image
# =============================================================================

def detect_skyline_from_image(img: Image.Image) -> list[tuple[int, int]]:
    """Use color-aware edge detection to find sky/terrain boundary."""
    img_array = np.array(img)

    r = img_array[:, :, 0].astype(np.float32)
    g = img_array[:, :, 1].astype(np.float32)
    b = img_array[:, :, 2].astype(np.float32)

    # Sky score: blue dominant (blue sky) or very bright (clouds/haze)
    blue_score = b - (r + g) / 2
    brightness = (r + g + b) / 3
    sky_score = np.maximum(blue_score, (brightness - 180))
    sky_score = np.clip(sky_score, 0, 255).astype(np.uint8)

    # Terrain score: colored (not gray) and not too bright
    # Terrain tends to be green/brown with moderate brightness
    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    saturation = (max_rgb - min_rgb) / (max_rgb + 1)  # Color saturation
    terrain_score = saturation * (255 - brightness / 2)  # Saturated and not too bright
    terrain_score = np.clip(terrain_score, 0, 255).astype(np.uint8)

    # Blur both
    sky_blurred = cv2.GaussianBlur(sky_score, (15, 15), 0)
    terrain_blurred = cv2.GaussianBlur(terrain_score, (15, 15), 0)

    # For each column, find where we transition from sky to terrain
    skyline_points = []
    height = img_array.shape[0]

    for x in range(0, img_array.shape[1], 3):
        # Scan from top, looking for sky-to-terrain transition
        for y in range(50, height - 20):
            # Check region above (should be sky-like)
            above_sky = np.mean(sky_blurred[max(0, y-30):y, x])
            above_terrain = np.mean(terrain_blurred[max(0, y-30):y, x])

            # Check region below (should be terrain-like)
            below_sky = np.mean(sky_blurred[y:min(y+30, height), x])
            below_terrain = np.mean(terrain_blurred[y:min(y+30, height), x])

            # Accept if: above is sky-like, below is terrain-like
            is_sky_above = above_sky > above_terrain + 10
            is_terrain_below = below_terrain > below_sky + 10

            if is_sky_above and is_terrain_below:
                skyline_points.append((x, y))
                break

    return skyline_points


# =============================================================================
# Line Simplification
# =============================================================================

def perpendicular_distance(point: tuple, line_start: tuple, line_end: tuple) -> float:
    """Calculate perpendicular distance from point to line segment."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end

    line_len_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if line_len_sq == 0:
        return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)

    num = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1)
    return num / math.sqrt(line_len_sq)


def rdp_simplify(points: list[tuple[int, int]], epsilon: float) -> list[tuple[int, int]]:
    """Ramer-Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points

    max_dist = 0
    max_idx = 0
    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = rdp_simplify(points[:max_idx + 1], epsilon)
        right = rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


# =============================================================================
# Swiss Coordinate Conversion
# =============================================================================

def swiss_to_wgs84(east: float, north: float) -> tuple[float, float]:
    """Convert Swiss LV95 coordinates to WGS84 lat/lon."""
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(east, north)
    return lat, lon


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Overlay multiple horizon representations for comparison."
    )
    parser.add_argument("image", type=Path, help="Input image with EXIF GPS data")
    parser.add_argument("--dem", type=Path, required=True, help="DEM GeoTIFF file")
    parser.add_argument("--peak-coords", type=str, default="2641684,1180548,2212.6",
                        help="Swiss coords E,N,elev for peak marker (default: Tannhorn)")
    parser.add_argument("--heading-offset", type=float, default=0.0,
                        help="Adjust heading by N degrees")
    parser.add_argument("--pitch-offset", type=float, default=0.0,
                        help="Adjust pitch by N degrees")
    parser.add_argument("--alt-offset", type=float, default=0.0,
                        help="Adjust altitude by N meters")
    parser.add_argument("output", type=Path, nargs="?", default=Path("output/horizon_comparison.jpg"),
                        help="Output path (default: output/horizon_comparison.jpg)")
    args = parser.parse_args()

    # Parse peak coordinates
    peak_parts = args.peak_coords.split(",")
    peak_east = float(peak_parts[0])
    peak_north = float(peak_parts[1])
    peak_elev = float(peak_parts[2])

    # Convert peak to WGS84
    peak_lat, peak_lon = swiss_to_wgs84(peak_east, peak_north)

    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Load camera pose from EXIF (using DEM for altitude)
    print(f"Loading camera pose from: {args.image}")
    pose = CameraPose.from_exif(args.image, args.dem)

    # Apply offsets
    pose.heading += args.heading_offset
    pose.pitch += args.pitch_offset
    pose.alt += args.alt_offset

    print(f"  Position: {pose.lat:.6f}, {pose.lon:.6f}")
    print(f"  Altitude: {pose.alt:.1f} m (DEM)")
    print(f"  Heading: {pose.heading:.1f}° (offset: {args.heading_offset:+.1f}°)")
    print(f"  Pitch: {pose.pitch:.1f}° (offset: {args.pitch_offset:+.1f}°)")
    print(f"  Roll: {pose.roll:.1f}°")
    print(f"  FOV: {pose.fov_h:.1f}° x {pose.fov_v:.1f}°")

    # Load image
    print(f"Loading image: {args.image}")
    img_raw = Image.open(args.image)
    img = ImageOps.exif_transpose(img_raw)
    width, height = img.size
    print(f"  Image size: {width} x {height}")

    # Load DEM
    print(f"Loading DEM: {args.dem}")
    dem_data, dem_transform, dem_crs = load_dem(args.dem)
    transformer = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=False)

    # Calculate distance to peak
    peak_distance = haversine_distance(pose.lat, pose.lon, peak_lat, peak_lon)
    peak_bearing = haversine_bearing(pose.lat, pose.lon, peak_lat, peak_lon)
    print(f"  Peak: distance={peak_distance:.1f}m, bearing={peak_bearing:.1f}°")

    # Create drawing context
    draw = ImageDraw.Draw(img)

    # 1. Detect and draw magenta skyline from image (first, so it's underneath)
    print("Detecting skyline from image (magenta)...")
    MAGENTA = (255, 0, 255)
    skyline_points = detect_skyline_from_image(img)
    print(f"  Detected {len(skyline_points)} skyline points")

    if skyline_points:
        skyline_simplified = rdp_simplify(skyline_points, epsilon=5)
        print(f"  Simplified to {len(skyline_simplified)} points")

        if len(skyline_simplified) >= 2:
            for i in range(len(skyline_simplified) - 1):
                draw.line([skyline_simplified[i], skyline_simplified[i + 1]],
                          fill=MAGENTA, width=6)

    # 2. Draw orange artificial horizon (pitch + roll)
    print("Drawing artificial horizon (orange)...")
    ORANGE = (255, 165, 0)
    half_fov_v = pose.fov_v / 2
    artificial_horizon_norm_y = pose.pitch / half_fov_v
    center_py = int(height / 2 + artificial_horizon_norm_y * height / 2)

    roll_rad = math.radians(pose.roll)
    y_offset_at_edge = int((width / 2) * math.tan(roll_rad))

    left_py = center_py + y_offset_at_edge
    right_py = center_py - y_offset_at_edge

    draw.line([(0, left_py), (width, right_py)], fill=ORANGE, width=6)

    # # 3. Draw black DEM horizon (ray-cast across all distances)
    # print("Computing DEM horizon 100m-10km (black)...")
    # BLACK = (0, 0, 0)
    # dem_points = compute_horizon(
    #     pose.lat, pose.lon, pose.alt,
    #     pose.heading, pose.pitch,
    #     pose.fov_h, pose.fov_v,
    #     dem_data, dem_transform,
    #     transformer=transformer,
    #     num_rays=300,
    #     min_distance=100,
    #     max_distance=10000,
    #     extra_fov=20,
    # )
    #
    # if dem_points:
    #     dem_pixels = []
    #     for norm_x, norm_y in dem_points:
    #         px = int(width / 2 + norm_x * width / 2)
    #         py = int(height / 2 + norm_y * height / 2)
    #         dem_pixels.append((px, py))
    #
    #     dem_pixels = rdp_simplify(dem_pixels, epsilon=10)
    #     print(f"  DEM points: {len(dem_pixels)}")
    #
    #     if len(dem_pixels) >= 2:
    #         for i in range(len(dem_pixels) - 1):
    #             draw.line([dem_pixels[i], dem_pixels[i + 1]], fill=BLACK, width=4)

    # 4. Draw red X at peak location
    print(f"Drawing peak marker (red) at {peak_lat:.6f}, {peak_lon:.6f}, {peak_elev:.1f}m...")
    RED = (255, 0, 0)
    peak_proj = project_point(
        peak_lat, peak_lon, peak_elev,
        pose.lat, pose.lon, pose.alt,
        pose.heading, pose.pitch,
        pose.fov_h, pose.fov_v,
        min_distance=0
    )

    if peak_proj:
        px = int(width / 2 + peak_proj[0] * width / 2)
        py = int(height / 2 + peak_proj[1] * height / 2)
        cross_size = 20
        draw.line([(px - cross_size, py - cross_size), (px + cross_size, py + cross_size)],
                  fill=RED, width=6)
        draw.line([(px - cross_size, py + cross_size), (px + cross_size, py - cross_size)],
                  fill=RED, width=6)
        print(f"  Peak projected to: ({px}, {py})")
    else:
        print("  Peak is outside FOV!")

    # Save output
    img.save(args.output, quality=95)
    print(f"\nSaved: {args.output}")

    # Summary
    print("\nOverlay Legend:")
    print("  Orange: Artificial horizon (accelerometer pitch/roll)")
    print("  Black:  DEM horizon (ray-cast 100m-10km)")
    print("  Red X:  Peak summit location")
    print("  Magenta: Detected skyline from image")


if __name__ == "__main__":
    main()
