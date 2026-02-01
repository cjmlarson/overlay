#!/usr/bin/env python3
"""Overlay GPX track onto a photo based on camera position and orientation from EXIF."""

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import gpxpy
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageOps


def parse_dms_to_decimal(dms_str: str) -> float:
    """Convert DMS string like '45 deg 58' 7.61" N' to decimal degrees."""
    # Match pattern: degrees, minutes, seconds, direction
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
    """Calculate pitch angle from acceleration vector Z component.

    Positive az → camera pointing UP (positive pitch)
    Negative az → camera pointing DOWN (negative pitch)
    """
    # Clamp az to valid range for asin
    az = max(-1.0, min(1.0, az))
    return math.degrees(math.asin(az))


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

    # Altitude - extract numeric value
    alt_str = data.get("GPSAltitude", "0")
    if isinstance(alt_str, str):
        alt = float(re.match(r"([\d.]+)", alt_str).group(1))
    else:
        alt = float(alt_str)

    # Heading
    heading = float(data["GPSImgDirection"])

    # Pitch from acceleration vector
    accel = parse_acceleration_vector(data["AccelerationVector"])
    pitch = calculate_pitch_from_acceleration(accel[2])

    # Field of View - extract numeric value
    fov_str = data.get("FieldOfView", "50")
    if isinstance(fov_str, str):
        sensor_fov = float(re.match(r"([\d.]+)", fov_str).group(1))
    else:
        sensor_fov = float(fov_str)

    # Orientation and FOV calculation
    orientation = data.get("Orientation", "Horizontal")

    # For a 4:3 sensor, calculate vertical FOV from horizontal
    # vertical_fov = 2 * atan(tan(horizontal_fov/2) * 3/4)
    sensor_vfov = 2 * math.degrees(math.atan(
        math.tan(math.radians(sensor_fov / 2)) * 3 / 4
    ))

    # Handle orientation rotation
    # Orientation 6 = "Rotate 90 CW" means portrait mode
    # The reported FOV is the sensor's horizontal FOV
    # After rotation, the display horizontal FOV becomes the sensor vertical FOV
    if "90" in str(orientation):
        # Portrait mode - swap FOVs
        fov_h = sensor_vfov  # Display horizontal = sensor vertical
        fov_v = sensor_fov   # Display vertical = sensor horizontal
    else:
        # Landscape mode - keep as is
        fov_h = sensor_fov
        fov_v = sensor_vfov

    # Timestamp
    date_str = data.get("DateTimeOriginal", "")
    offset_str = data.get("OffsetTimeOriginal", "")
    timestamp = None
    if date_str:
        # Handle format with or without subseconds
        date_str = date_str.split(".")[0]  # Remove subseconds if present
        date_str = date_str.split("+")[0].split("-")[0]  # Remove timezone if embedded
        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        if offset_str:
            sign = 1 if offset_str[0] == "+" else -1
            hours, minutes = map(int, offset_str[1:].split(":"))
            tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
            dt = dt.replace(tzinfo=tz)
        timestamp = dt

    return {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "heading": heading,
        "pitch": pitch,
        "fov_h": fov_h,
        "fov_v": fov_v,
        "timestamp": timestamp,
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
                  interpolate: bool = True) -> float | None:
    """Query elevation at a point. Returns None if outside bounds.

    If interpolate=True, uses bilinear interpolation for smooth values.
    """
    # Convert lat/lon to pixel coordinates
    # ~transform converts from pixel to world coords, so we use the inverse
    inv_transform = ~transform
    col, row = inv_transform * (lon, lat)

    if not interpolate:
        # Nearest neighbor sampling
        row_int = int(row)
        col_int = int(col)
        if row_int < 0 or row_int >= dem_data.shape[0] or col_int < 0 or col_int >= dem_data.shape[1]:
            return None
        return float(dem_data[row_int, col_int])

    # Bilinear interpolation
    row0 = int(row)
    col0 = int(col)
    row1 = row0 + 1
    col1 = col0 + 1

    # Check bounds (need all 4 corners)
    if row0 < 0 or row1 >= dem_data.shape[0] or col0 < 0 or col1 >= dem_data.shape[1]:
        return None

    # Fractional parts
    row_frac = row - row0
    col_frac = col - col0

    # Get 4 corner elevations
    z00 = dem_data[row0, col0]
    z01 = dem_data[row0, col1]
    z10 = dem_data[row1, col0]
    z11 = dem_data[row1, col1]

    # Bilinear interpolation
    z0 = z00 * (1 - col_frac) + z01 * col_frac
    z1 = z10 * (1 - col_frac) + z11 * col_frac
    z = z0 * (1 - row_frac) + z1 * row_frac

    return float(z)


# =============================================================================
# Horizon Ray-Casting
# =============================================================================

def destination_point(lat: float, lon: float, bearing: float, distance: float) -> tuple[float, float]:
    """
    Calculate destination point given start point, bearing (degrees), and distance (meters).
    Uses spherical Earth approximation.
    """
    R = 6371000  # Earth radius in meters

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


def compute_horizon(
    cam_lat: float, cam_lon: float, cam_alt: float,
    heading: float, pitch: float, fov_h: float, fov_v: float,
    dem_data: np.ndarray, transform: rasterio.Affine,
    num_rays: int = 200,
    max_distance: float = 10000,  # meters
    step_size: float = 30  # meters (match DEM resolution)
) -> list[tuple[float, float]]:
    """
    Compute the horizon/skyline by finding the maximum elevation angle along each azimuth.
    Returns list of (norm_x, norm_y) points forming the horizon.
    """
    horizon_points = []

    # Cast rays across the horizontal FOV
    for i in range(num_rays):
        # Azimuth for this ray
        azimuth = heading - fov_h / 2 + (i / (num_rays - 1)) * fov_h

        # Track the maximum elevation angle along this ray
        max_elevation_angle = -90  # Start very low
        best_point = None

        # Step along the ray and find the point with maximum elevation angle
        for distance in range(int(step_size), int(max_distance), int(step_size)):
            # Get point along this ray
            point_lat, point_lon = destination_point(cam_lat, cam_lon, azimuth, distance)

            # Get terrain elevation at this point
            terrain_alt = get_elevation(dem_data, transform, point_lat, point_lon)

            if terrain_alt is None:
                # Outside DEM bounds
                continue

            # Calculate elevation angle from camera to this terrain point
            delta_elevation = terrain_alt - cam_alt
            elevation_angle = math.degrees(math.atan2(delta_elevation, distance))

            # Track the maximum (this is the skyline)
            if elevation_angle > max_elevation_angle:
                max_elevation_angle = elevation_angle
                best_point = (point_lat, point_lon, terrain_alt)

        # Project the best point (skyline point) to image coordinates
        if best_point is not None:
            result = project_point(
                best_point[0], best_point[1], best_point[2],
                cam_lat, cam_lon, cam_alt,
                heading, pitch,
                fov_h, fov_v,
                min_distance=0  # Accept all distances for horizon
            )
            if result is not None:
                horizon_points.append(result)

    return horizon_points


# =============================================================================
# Future Feature Stubs
# =============================================================================

def compute_contours(dem_data: np.ndarray, transform: rasterio.Affine, interval: float = 100) -> list:
    """TODO: Extract contour lines at given interval."""
    raise NotImplementedError("Contour extraction not yet implemented")


def compute_fall_lines(dem_data: np.ndarray, transform: rasterio.Affine) -> list:
    """TODO: Compute lines of steepest descent."""
    raise NotImplementedError("Fall line extraction not yet implemented")


def compute_peaks(dem_data: np.ndarray, transform: rasterio.Affine, min_prominence: float = 50) -> list:
    """TODO: Find local maxima with given prominence."""
    raise NotImplementedError("Peak detection not yet implemented")


def perpendicular_distance(point: tuple, line_start: tuple, line_end: tuple) -> float:
    """Calculate perpendicular distance from point to line segment."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end

    # Line length squared
    line_len_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if line_len_sq == 0:
        return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)

    # Distance from point to line
    num = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1)
    return num / math.sqrt(line_len_sq)


def rdp_simplify(points: list[tuple[int, int]], epsilon: float) -> list[tuple[int, int]]:
    """Ramer-Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points

    # Find point with max distance from line between first and last
    max_dist = 0
    max_idx = 0
    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    # If max distance exceeds epsilon, recursively simplify
    if max_dist > epsilon:
        left = rdp_simplify(points[:max_idx + 1], epsilon)
        right = rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


# =============================================================================
# Coordinate Utilities
# =============================================================================

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
    R = 6371000  # Earth radius in meters

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


def project_point(
    lat: float, lon: float, alt: float,
    camera_lat: float, camera_lon: float, camera_alt: float,
    camera_heading: float, camera_pitch: float,
    fov_h: float, fov_v: float,
    min_distance: float = 100.0
) -> tuple[float, float] | None:
    """
    Project a GPS point to normalized image coordinates.
    Returns (norm_x, norm_y) in range [-1, 1] or None if outside FOV.
    """
    # Calculate bearing from camera to point
    bearing = haversine_bearing(camera_lat, camera_lon, lat, lon)

    # Calculate horizontal distance
    h_distance = haversine_distance(camera_lat, camera_lon, lat, lon)

    # Exclude points too close to camera (3D distance)
    delta_elevation = alt - camera_alt
    dist_3d = math.sqrt(h_distance ** 2 + delta_elevation ** 2)
    if dist_3d < min_distance:
        return None

    # Calculate elevation angle
    elevation_angle = math.degrees(math.atan2(delta_elevation, h_distance))

    # Get relative angles
    relative_bearing = normalize_angle(bearing - camera_heading)
    relative_pitch = elevation_angle - camera_pitch

    # FOV filtering
    half_fov_h = fov_h / 2
    half_fov_v = fov_v / 2

    if abs(relative_bearing) > half_fov_h or abs(relative_pitch) > half_fov_v:
        return None

    # Projection to normalized coordinates [-1, 1]
    norm_x = relative_bearing / half_fov_h
    norm_y = -relative_pitch / half_fov_v  # Negative because y increases downward

    return (norm_x, norm_y)


def load_gpx_points(gpx_path: Path) -> list[tuple[float, float, float, datetime | None]]:
    """Load all trackpoints from GPX file with timestamps."""
    with open(gpx_path) as f:
        gpx = gpxpy.parse(f)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is not None:
                    points.append((point.latitude, point.longitude, point.elevation, point.time))

    return points


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Overlay GPX track onto a photo based on camera position and orientation from EXIF."
    )
    parser.add_argument("image", type=Path, help="Input image with EXIF GPS data")
    parser.add_argument("gpx", type=Path, help="GPX track file")
    parser.add_argument("--dem", type=Path, help="DEM GeoTIFF for horizon overlay")
    parser.add_argument("output", type=Path, nargs="?", default=Path("output/overlay.jpg"),
                        help="Output image path (default: output/overlay.jpg)")
    args = parser.parse_args()

    image_path = args.image
    gpx_path = args.gpx
    dem_path = args.dem
    output_path = args.output

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract camera parameters from EXIF
    print(f"Extracting EXIF from: {image_path}")
    params = extract_camera_params(image_path)
    print(f"  Position: {params['lat']:.6f}, {params['lon']:.6f}")
    print(f"  Altitude: {params['alt']:.1f} m")
    print(f"  Heading: {params['heading']:.1f}°")
    print(f"  Pitch: {params['pitch']:.1f}°")
    print(f"  FOV: {params['fov_h']:.1f}° x {params['fov_v']:.1f}°")
    print(f"  Timestamp: {params['timestamp']}")

    # Load image and apply EXIF orientation
    print(f"Loading image: {image_path}")
    img_raw = Image.open(image_path)
    img = ImageOps.exif_transpose(img_raw)
    width, height = img.size
    print(f"Image size (after orientation): {width} x {height}")

    # Load GPX points
    print(f"Loading GPX: {gpx_path}")
    gpx_points = load_gpx_points(gpx_path)
    print(f"Total GPX points: {len(gpx_points)}")

    # Load DEM if provided
    dem_data = None
    dem_transform = None
    horizon_points = []
    if dem_path:
        print(f"Loading DEM: {dem_path}")
        dem_data, dem_transform, dem_crs = load_dem(dem_path)
        print(f"  DEM shape: {dem_data.shape}")
        print(f"  DEM CRS: {dem_crs}")

        # Compute horizon line
        print("Computing horizon...")
        horizon_points = compute_horizon(
            params['lat'], params['lon'], params['alt'],
            params['heading'], params['pitch'],
            params['fov_h'], params['fov_v'],
            dem_data, dem_transform,
            num_rays=200,
            max_distance=10000,
            step_size=30
        )
        print(f"  Horizon points: {len(horizon_points)}")

    # Project points (using GPS elevation)
    projected_gps = []
    for lat, lon, alt, timestamp in gpx_points:
        result = project_point(
            lat, lon, alt,
            params['lat'], params['lon'], params['alt'],
            params['heading'], params['pitch'],
            params['fov_h'], params['fov_v']
        )
        if result is not None:
            norm_x, norm_y = result
            # Convert normalized to pixel coordinates
            px = int(width / 2 + norm_x * width / 2)
            py = int(height / 2 + norm_y * height / 2)
            projected_gps.append((px, py))

    print(f"Points in FOV (GPS elevation): {len(projected_gps)}")

    # Project points using DEM elevation (if DEM available)
    projected_dem = []
    if dem_data is not None:
        for lat, lon, alt, timestamp in gpx_points:
            # Use DEM elevation instead of GPS elevation
            dem_alt = get_elevation(dem_data, dem_transform, lat, lon)
            if dem_alt is None:
                continue
            result = project_point(
                lat, lon, dem_alt,
                params['lat'], params['lon'], params['alt'],
                params['heading'], params['pitch'],
                params['fov_h'], params['fov_v']
            )
            if result is not None:
                norm_x, norm_y = result
                px = int(width / 2 + norm_x * width / 2)
                py = int(height / 2 + norm_y * height / 2)
                projected_dem.append((px, py))
        print(f"Points in FOV (DEM elevation): {len(projected_dem)}")

    # Draw overlay
    draw = ImageDraw.Draw(img)

    # Colors
    GPS_COLOR = (255, 165, 0)    # Orange for GPS elevation
    DEM_COLOR = (255, 105, 180)  # Pink for DEM elevation

    # Draw DEM elevation track first (pink) - so GPS track draws on top
    # Apply RDP simplification to smooth the line
    if len(projected_dem) >= 2:
        smoothed_dem = rdp_simplify(projected_dem, epsilon=15)
        print(f"DEM track simplified: {len(projected_dem)} -> {len(smoothed_dem)} points")
        for i in range(len(smoothed_dem) - 1):
            px1, py1 = smoothed_dem[i]
            px2, py2 = smoothed_dem[i + 1]
            draw.line([(px1, py1), (px2, py2)], fill=DEM_COLOR, width=8)

    # Draw GPS elevation track (orange)
    if len(projected_gps) >= 2:
        for i in range(len(projected_gps) - 1):
            px1, py1 = projected_gps[i]
            px2, py2 = projected_gps[i + 1]
            draw.line([(px1, py1), (px2, py2)], fill=GPS_COLOR, width=8)

    # Draw horizon line on top of GPX track
    if horizon_points:
        # Convert normalized coordinates to pixel coordinates
        horizon_pixels = []
        for norm_x, norm_y in horizon_points:
            px = int(width / 2 + norm_x * width / 2)
            py = int(height / 2 + norm_y * height / 2)
            horizon_pixels.append((px, py))

        # Smooth horizon with RDP
        horizon_pixels = rdp_simplify(horizon_pixels, epsilon=15)
        print(f"Horizon simplified to {len(horizon_pixels)} points")

        # Draw as connected line segments (yellow/white for visibility)
        HORIZON_COLOR = (255, 255, 0)  # Yellow
        if len(horizon_pixels) >= 2:
            for i in range(len(horizon_pixels) - 1):
                draw.line([horizon_pixels[i], horizon_pixels[i + 1]],
                          fill=HORIZON_COLOR, width=6)

    # Save output
    img.save(output_path, quality=95)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
