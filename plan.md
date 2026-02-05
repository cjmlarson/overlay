# Position Refinement: Grid Search

## Problem Statement

We have a working skyline matching pipeline that estimates camera orientation (azimuth, roll, pitch) from geotagged mountain photos. The orientation matching works well (correlations ~0.96-0.97), but we observe **local shape discrepancies** between the image skyline and DEM-rendered skyline that indicate **camera position error** from GPS noise.

### The Single vs Double Peak Problem

In our test image (`IMG_5620.jpeg`), we observe a clear diagnostic signal:
- **Image skyline**: Shows a **single peak** for the main summit
- **DEM skyline**: Shows a **double peak** structure at the same location

This mismatch is caused by **parallax from position error**. The DEM skyline is rendered from the GPS coordinates, but the actual camera position was slightly different. Because the foreground peak is close to the camera, even a small position offset (tens of meters) causes:
- Different occlusion of background features
- Different apparent shape of the ridge crest

The correlation is still high because the *overall* skyline matches globally, but the *local peak structure* differs in the near-field. The closer the feature, the more sensitive it is to position error.

### Goal

Refine the camera position (x, y, and optionally z) to minimize the discrepancy between the image skyline and the DEM-rendered skyline. Grid search provides a baseline approach that:
1. Visualizes the objective landscape
2. Guarantees finding the optimum within the search grid
3. Reveals whether the objective is smooth/convex or has multiple local optima

## Literature Review

### Saurer et al. 2015 / Baatz et al. 2012 - Grid-Based Localization

**Reference**: Saurer, O., Baatz, G., Köser, K., Ladický, L., & Pollefeys, M. (2015). "Image Based Geo-localization in the Alps." *International Journal of Computer Vision*.

**Section 2.2 - Visual Database Creation** (p. 6-7):
> "At each position on a regular grid on the surface (every 0.001° in N-S direction and 0.0015° in E-W direction, i.e. 111 m and 115 m respectively) and from 1.80 m above the ground, we render a cubemap of the textureless DEM... Overall, we generate 3.5 million cubemaps."

**Section 2.3.4 - Geometric Verification** (p. 8):
> "After retrieval we geometrically verify the top 1000 candidates. The verification consists in computing an optimal alignment of the two visible skylines using iterative closest points (ICP)."

**Key insight**: They pre-compute skylines at a regular grid and use ICP for fine alignment. For our case, we can use a smaller, denser grid around the GPS position.

### Mikolka-Floery et al. 2022 - Coarse-to-Fine Grid Search

**Reference**: Mikolka-Floery, S., et al. (2022). "Automated orientation of historical terrestrial images."

**Section 3.1 - Coarse Orientation**:
> "Uses horizon matching with grid points (100m spacing) to reduce search space, estimating position and azimuth... Pre-computes terrain horizons at 100m grid spacing over study area."

**Results** (Section 4):
- 63% of images positioned within 250m of true position
- For easier cases, 40% within 100m with <1° azimuth error

**Key insight**: 100m grid spacing is sufficient for coarse localization; finer grids can refine further.

### Fedorov et al. 2014 - Multi-Stage Refinement

**Reference**: Fedorov, R., Fraternali, P., & Tagliasacchi, M. (2014). "Mountain peak identification in visual content based on coarse digital elevation models."

**Section 3.4 - Local Alignment**:
> "Fine-tunes individual peak positions within local neighborhoods around globally-aligned locations (7.5° radius)."

**Key insight**: After global alignment, local refinement in a bounded region improves accuracy significantly (21% improvement over global alignment alone).

## Implementation Plan

### Phase 1: Grid Search Infrastructure

1. **Define search region**: ±100m around GPS in x and y (optionally z)
2. **Grid resolution**: Start with 10m steps → 21×21 = 441 candidates
3. **For each candidate position**:
   - Render DEM skyline from that position using existing `skyline/dem/nagy_20.py`
   - Run orientation optimization (azimuth, roll, pitch) - reuse existing code
   - Compute correlation between image skyline and DEM skyline
   - Store: position, best orientation, correlation score

### Phase 2: Objective Function Design

The objective function should capture both:
1. **Global alignment quality**: Normalized cross-correlation (existing)
2. **Local shape fidelity**: Penalize peak structure mismatches

Options for scoring:
- Pure correlation (simple, may miss local issues)
- Hausdorff distance (captures worst-case local error)
- Combined: `score = correlation - λ * hausdorff_distance`

### Phase 3: Visualization & Analysis

1. **Heatmap**: 2D plot of correlation vs (x, y) position
2. **Best match overlay**: Show skylines at best position
3. **Diagnostic**: Compare peak structure at GPS vs refined position

### Phase 4: Evaluation

1. Does the refined position produce a single peak matching the image?
2. Is the objective landscape smooth or multi-modal?
3. How sensitive is the result to grid resolution?

## File Structure

```
pos-grid-search/
├── plan.md                    # This file
├── position_grid_search.py    # Main implementation
├── tmp/
│   ├── grid_heatmap.png       # Visualization of objective landscape
│   └── refined_skylines.jpg   # Comparison at refined position
```

## Key Functions to Implement

```python
def render_dem_skyline_at_position(lat, lon, alt, fov_h, azimuth):
    """Render DEM skyline from a specific camera position."""
    pass

def compute_position_score(image_skyline, dem_skyline):
    """Score how well DEM skyline matches image skyline."""
    pass

def grid_search_position(
    image_path: str,
    gps_lat: float,
    gps_lon: float,
    gps_alt: float,
    search_radius_m: float = 100.0,
    grid_step_m: float = 10.0
) -> dict:
    """
    Search for optimal camera position around GPS coordinates.

    Returns:
        dict with best_position, best_score, heatmap, etc.
    """
    pass
```

## Success Criteria

1. **Quantitative**: Refined position produces higher correlation than GPS position
2. **Qualitative**: DEM skyline at refined position shows single peak (matching image)
3. **Insight**: Heatmap reveals the shape of the objective landscape

## Dependencies

- Existing codebase: `skyline/dem/nagy_20.py`, `skyline/image/*.py`
- NumPy, Matplotlib for computation and visualization
- pyproj or similar for coordinate conversions (lat/lon ↔ meters)

## Next Steps After Grid Search

Grid search results will inform:
1. Whether the objective is smooth enough for gradient-free optimization (Nelder-Mead)
2. Whether there are multiple local optima requiring global search (PSO)
3. What grid resolution is needed for accurate localization
