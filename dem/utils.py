#!/usr/bin/env python3
"""
DEM Tile Downloader Utility

Downloads SwissALTI3D tiles for a given radius around a geotagged image's location.
Also provides utilities for loading and sampling DEM data.
"""

import argparse
import math
import re
import urllib.request
from pathlib import Path

import exiftool
import numpy as np
import rasterio
from rasterio.merge import merge
from pyproj import Transformer
from tqdm import tqdm

# Swiss coordinate system transformer
WGS84_TO_SWISS = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)


def extract_gps_from_image(image_path: str) -> tuple[float, float]:
    """
    Extract GPS coordinates from image EXIF data.

    Returns (latitude, longitude) in decimal degrees.
    Raises ValueError if no GPS data found.
    """
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(image_path)[0]

    # Try composite GPS tags first (already in decimal)
    lat = metadata.get("Composite:GPSLatitude")
    lon = metadata.get("Composite:GPSLongitude")

    if lat is not None and lon is not None:
        return float(lat), float(lon)

    # Try EXIF GPS tags
    lat = metadata.get("EXIF:GPSLatitude")
    lon = metadata.get("EXIF:GPSLongitude")
    lat_ref = metadata.get("EXIF:GPSLatitudeRef", "N")
    lon_ref = metadata.get("EXIF:GPSLongitudeRef", "E")

    if lat is not None and lon is not None:
        lat = float(lat)
        lon = float(lon)
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon
        return lat, lon

    raise ValueError(f"No GPS data found in {image_path}")


def gps_to_swiss(lat: float, lon: float) -> tuple[float, float]:
    """
    Convert WGS84 (lat, lon) to Swiss coordinates (EPSG:2056).

    Returns (easting, northing) in meters.
    """
    # pyproj with always_xy expects (lon, lat) order
    easting, northing = WGS84_TO_SWISS.transform(lon, lat)
    return easting, northing


def tiles_in_radius(center_e: float, center_n: float, radius_km: float = 10) -> set[tuple[int, int]]:
    """
    Find all 1km tile coordinates within radius_km of center point.

    Swiss tiles are 1km x 1km, named by their SW corner in km.
    Returns set of (tile_x, tile_y) tuples representing km coordinates.
    """
    radius_m = radius_km * 1000

    # Bounding box in meters
    min_e = center_e - radius_m
    max_e = center_e + radius_m
    min_n = center_n - radius_m
    max_n = center_n + radius_m

    # Convert to tile coordinates (km, floored)
    min_tile_x = int(min_e // 1000)
    max_tile_x = int(max_e // 1000)
    min_tile_y = int(min_n // 1000)
    max_tile_y = int(max_n // 1000)

    tiles = set()
    for tx in range(min_tile_x, max_tile_x + 1):
        for ty in range(min_tile_y, max_tile_y + 1):
            # Tile center
            tile_center_e = (tx + 0.5) * 1000
            tile_center_n = (ty + 0.5) * 1000

            # Distance from camera to tile center
            dist = math.sqrt((tile_center_e - center_e) ** 2 + (tile_center_n - center_n) ** 2)

            if dist <= radius_m:
                tiles.add((tx, ty))

    return tiles


def load_available_tiles(csv_path: str) -> dict[tuple[int, int], str]:
    """
    Load tile URLs from index CSV file.

    Returns dict mapping (tile_x, tile_y) to URL.
    """
    # Pattern to extract tile coordinates from URL
    # e.g., swissalti3d_2019_2501-1120_0.5_2056_5728.tif -> (2501, 1120)
    pattern = re.compile(r"swissalti3d_\d{4}_(\d{4})-(\d{4})_")

    tiles = {}
    with open(csv_path, "r") as f:
        for line in f:
            url = line.strip()
            if not url:
                continue
            match = pattern.search(url)
            if match:
                tx = int(match.group(1))
                ty = int(match.group(2))
                tiles[(tx, ty)] = url

    return tiles


def download_tiles(urls: list[str], dest_dir: Path, skip_existing: bool = True) -> None:
    """
    Download tiles to destination directory.

    Shows progress bar and skips already-downloaded tiles if skip_existing=True.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0

    for url in tqdm(urls, desc="Downloading tiles"):
        filename = url.split("/")[-1]
        dest_path = dest_dir / filename

        if skip_existing and dest_path.exists():
            skipped += 1
            continue

        try:
            urllib.request.urlretrieve(url, dest_path)
            downloaded += 1
        except Exception as e:
            tqdm.write(f"Failed to download {filename}: {e}")

    print(f"Downloaded {downloaded} tiles, skipped {skipped} existing")


def load_dem_tiles(
    tile_dir: str | Path,
    center_e: float,
    center_n: float,
    radius: float = 10000,
    resolution: str = "200cm",
) -> tuple[np.ndarray, rasterio.Affine]:
    """
    Load and merge DEM tiles within radius of center point.

    Args:
        tile_dir: Directory containing .tif DEM tiles
        center_e: Camera easting (Swiss coords, meters)
        center_n: Camera northing (Swiss coords, meters)
        radius: Radius in meters to load tiles for (default 10km)
        resolution: DEM resolution to use ("50cm" or "200cm", default "200cm")
                    Tiles are stored in {tile_dir}/{resolution}/ subfolders.
                    50cm tiles are downsampled 4x to match 200cm effective resolution.

    Returns:
        Tuple of (elevation_grid, transform):
        - elevation_grid: 2D numpy array of elevations (meters)
        - transform: Affine transform for coordinate conversion
    """
    tile_dir = Path(tile_dir) / resolution

    # Determine downsample factor based on resolution
    # 50cm tiles need 4x downsample to get 2m effective resolution
    # 200cm tiles are already at 2m, no downsampling needed
    downsample = 4 if resolution == "50cm" else 1

    # Find tiles within radius
    needed = tiles_in_radius(center_e, center_n, radius / 1000)

    # Pattern to extract tile coordinates from filename
    pattern = re.compile(r"swissalti3d_\d{4}_(\d{4})-(\d{4})_")

    # Find matching tile files
    tile_files = []
    for tif_path in tile_dir.glob("*.tif"):
        match = pattern.search(tif_path.name)
        if match:
            tx = int(match.group(1))
            ty = int(match.group(2))
            if (tx, ty) in needed:
                tile_files.append(tif_path)

    if not tile_files:
        raise FileNotFoundError(f"No DEM tiles found in {tile_dir} for radius {radius}m around ({center_e}, {center_n})")

    # Open all tile datasets
    datasets = [rasterio.open(f) for f in tile_files]

    try:
        # Merge tiles into single array
        merged, merged_transform = merge(datasets)
        elevation = merged[0]  # First band contains elevation

        # Downsample if requested
        if downsample > 1:
            # Use block averaging for downsampling
            h, w = elevation.shape
            new_h = h // downsample
            new_w = w // downsample
            # Trim to exact multiple
            trimmed = elevation[:new_h * downsample, :new_w * downsample]
            # Reshape and average
            elevation = trimmed.reshape(new_h, downsample, new_w, downsample).mean(axis=(1, 3))

            # Adjust transform for new resolution
            merged_transform = rasterio.Affine(
                merged_transform.a * downsample,
                merged_transform.b,
                merged_transform.c,
                merged_transform.d,
                merged_transform.e * downsample,
                merged_transform.f,
            )

        return elevation.astype(np.float32), merged_transform

    finally:
        for ds in datasets:
            ds.close()


def sample_elevation(
    grid: np.ndarray,
    transform: rasterio.Affine,
    easting: float,
    northing: float,
) -> float:
    """
    Sample elevation at a point using bilinear interpolation.

    Args:
        grid: 2D elevation array
        transform: Affine transform from load_dem_tiles
        easting: Swiss easting coordinate (meters)
        northing: Swiss northing coordinate (meters)

    Returns:
        Elevation in meters, or NaN if outside grid
    """
    # Convert world coords to pixel coords (fractional)
    inv_transform = ~transform
    col, row = inv_transform * (easting, northing)

    # Check bounds
    h, w = grid.shape
    if col < 0 or col >= w - 1 or row < 0 or row >= h - 1:
        return np.nan

    # Bilinear interpolation
    c0, r0 = int(col), int(row)
    dc, dr = col - c0, row - r0

    # Four corners
    z00 = grid[r0, c0]
    z01 = grid[r0, c0 + 1]
    z10 = grid[r0 + 1, c0]
    z11 = grid[r0 + 1, c0 + 1]

    # Interpolate
    z = (
        z00 * (1 - dc) * (1 - dr)
        + z01 * dc * (1 - dr)
        + z10 * (1 - dc) * dr
        + z11 * dc * dr
    )

    return float(z)


def main():
    # Index CSV files for each resolution
    INDEX_FILES = {
        "50cm": "index.csv",
        "200cm": "ch.swisstopo.swissalti3d-6lwv7yZL.csv",
    }

    parser = argparse.ArgumentParser(
        description="Download SwissALTI3D DEM tiles around a geotagged image"
    )
    parser.add_argument("image", help="Path to geotagged image")
    parser.add_argument(
        "--radius", type=float, default=10, help="Radius in km (default: 10)"
    )
    parser.add_argument(
        "--resolution", choices=["50cm", "200cm"], default="200cm",
        help="DEM resolution to download (default: 200cm)"
    )
    parser.add_argument(
        "--index", help="Path to tile index CSV (overrides --resolution default)"
    )
    parser.add_argument(
        "--dest", help="Destination directory (overrides --resolution default)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be downloaded without downloading"
    )

    args = parser.parse_args()

    # Set index and dest based on resolution if not explicitly provided
    index_file = args.index or INDEX_FILES[args.resolution]
    dest_dir = args.dest or f"dem/{args.resolution}"

    # Extract GPS from image
    print(f"Reading GPS from {args.image}...")
    lat, lon = extract_gps_from_image(args.image)
    print(f"Extracted GPS: {lat:.4f}°N, {lon:.4f}°E")

    # Convert to Swiss coordinates
    easting, northing = gps_to_swiss(lat, lon)
    print(f"Swiss coords: {easting:.0f} E, {northing:.0f} N")

    # Find tiles in radius
    needed_tiles = tiles_in_radius(easting, northing, args.radius)
    print(f"Tiles needed for {args.radius}km radius: {len(needed_tiles)}")

    # Load available tiles
    print(f"Loading {args.resolution} tile index from {index_file}...")
    available = load_available_tiles(index_file)
    print(f"Available tiles in index: {len(available)}")

    # Find URLs to download
    urls_to_download = []
    missing = []
    for tile in needed_tiles:
        if tile in available:
            urls_to_download.append(available[tile])
        else:
            missing.append(tile)

    if missing:
        print(f"Warning: {len(missing)} tiles not in index (outside Switzerland coverage)")

    print(f"Tiles to download: {len(urls_to_download)}")

    if args.dry_run:
        print("\nDry run - tiles that would be downloaded:")
        for url in sorted(urls_to_download)[:10]:
            print(f"  {url.split('/')[-1]}")
        if len(urls_to_download) > 10:
            print(f"  ... and {len(urls_to_download) - 10} more")
        return

    # Download tiles
    if urls_to_download:
        download_tiles(urls_to_download, Path(dest_dir))
        print(f"Done! Tiles saved to {dest_dir}/")
    else:
        print("No tiles to download.")


if __name__ == "__main__":
    main()
