# Position Refinement: Nelder-Mead Simplex Optimization

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

### Why Nelder-Mead?

Nelder-Mead (simplex method) is a classic **gradient-free optimization** algorithm ideal for this problem because:
1. **No gradients needed**: Skyline correlation is not obviously differentiable
2. **Fast convergence**: Typically 50-100 function evaluations for 2-3D problems
3. **Built-in**: Available in `scipy.optimize.minimize`
4. **Local refinement**: Perfect for polishing an initial estimate (GPS or grid search result)

## Literature Review

### Baboud et al. 2011 - Iterative Pose Refinement

**Reference**: Baboud, L., Čadík, M., Eisemann, E., & Seidel, H.-P. (2011). "Automatic photo-to-terrain alignment for the annotation of mountain pictures." *CVPR*.

**Section 4 - Robust Silhouette Map Matching Metric** (p. 3-4):
> "Because a direct extensive search on SO(3) using this metric is very costly, we additionally propose a fast preprocess based on spherical cross-correlation. It effectively reduces the search space to a very narrow subset, to which the robust matching metric is then applied."

**Section 6 - Implementation Details** (p. 6):
> "The overall process takes around 2 minutes, critical parts being compass edge detection (around 1 min.), spherical cross-correlation (less than one minute), and final matching metric evaluation (around 20 s. with the GPU implementation)."

**Key insight**: They use coarse-to-fine: fast preprocess narrows search space, then expensive metric refines. Nelder-Mead fits as the refinement step.

### Saurer et al. 2015 - ICP-Based Local Refinement

**Reference**: Saurer, O., Baatz, G., Köser, K., Ladický, L., & Pollefeys, M. (2015). "Image Based Geo-localization in the Alps."

**Section 2.3.4 - Geometric Verification** (p. 8):
> "The verification consists in computing an optimal alignment of the two visible skylines using iterative closest points (ICP). While we consider in the voting stage only one angle (azimuth), ICP determines a full 3D rotation. First, we sample all possible values for azimuth and keep the two other angles at zero. The most promising one is used as initialization for ICP."

**Key insight**: ICP is essentially iterative local optimization. Nelder-Mead can serve a similar role for position refinement.

### Porzi et al. 2014 - Bounded Optimization for Pose

**Reference**: Porzi, L., Rota Bulò, S., Riemenschneider, H., & Kontschieder, P. (2014). "Learning contour-based registration for mountain peak detection."

**Section 3.3 - Optimization** (p. 5):
> "Bounded search space: The search constraints x ≥ x_S - b_l and x ≤ x_S + b_u effectively define a bounded region around the GPS-based sensor estimate."

**Key insight**: Bounding the search region around GPS prevents divergence and focuses computation. Nelder-Mead with bounds achieves this naturally.

### General Optimization Literature

**Nelder-Mead Algorithm** (Nelder & Mead, 1965):
- Derivative-free simplex method
- Maintains a simplex of n+1 points in n dimensions
- Iteratively replaces worst point via reflection, expansion, contraction
- Converges to local minimum (not guaranteed global)

**When to use**:
- Objective function is noisy or non-differentiable
- Function evaluations are expensive (want minimal calls)
- Good initial estimate available (GPS position)

## Implementation Plan

### Phase 1: Objective Function

Define the function to minimize:
```python
def objective(position, image_skyline, dem_loader, orientation_params):
    """
    Compute negative correlation (or other score) for a candidate position.

    Args:
        position: [x_offset, y_offset] in meters from GPS, or [lat, lon]
        image_skyline: Detected skyline from photo
        dem_loader: Object to render DEM skylines
        orientation_params: FOV, initial azimuth estimate, etc.

    Returns:
        float: Negative correlation (to minimize) or other loss
    """
    # 1. Convert position offset to lat/lon
    # 2. Render DEM skyline at this position
    # 3. Optimize orientation (azimuth, roll, pitch) for this position
    # 4. Compute correlation between skylines
    # 5. Return negative correlation (or other loss)
```

### Phase 2: Nelder-Mead Setup

```python
from scipy.optimize import minimize

result = minimize(
    fun=objective,
    x0=[0.0, 0.0],  # Start at GPS position (offset = 0)
    args=(image_skyline, dem_loader, orientation_params),
    method='Nelder-Mead',
    options={
        'maxiter': 100,
        'xatol': 1.0,      # Position tolerance in meters
        'fatol': 0.001,    # Correlation tolerance
        'disp': True,
    }
)
```

### Phase 3: Multi-Start Strategy

Since Nelder-Mead finds local minima, consider multiple starting points:
1. GPS position (0, 0)
2. Offset in cardinal directions: (±50m, 0), (0, ±50m)
3. Pick best result across starts

### Phase 4: Joint vs Sequential Optimization

**Option A - Sequential**:
1. For each candidate position, optimize orientation (existing code)
2. Nelder-Mead searches over position only

**Option B - Joint**:
- Optimize [x, y, azimuth, pitch, roll] together
- More parameters but potentially better solution
- Risk: Nelder-Mead may struggle with 5D

**Recommendation**: Start with Option A (sequential) for simplicity.

### Phase 5: Visualization & Diagnostics

1. **Convergence plot**: Objective value vs iteration
2. **Path visualization**: Show Nelder-Mead trajectory on position heatmap (if grid search data available)
3. **Before/after comparison**: Skyline overlay at GPS vs refined position

## File Structure

```
pos-nelder-mead/
├── plan.md                      # This file
├── position_nelder_mead.py      # Main implementation
├── tmp/
│   ├── convergence.png          # Objective vs iteration
│   ├── trajectory.png           # Optimization path
│   └── refined_skylines.jpg     # Before/after comparison
```

## Key Functions to Implement

```python
def position_objective(
    offset_meters: np.ndarray,  # [dx, dy] from GPS
    image_skyline: np.ndarray,
    gps_lat: float,
    gps_lon: float,
    gps_alt: float,
    dem_loader,
    camera_params: dict,
) -> float:
    """
    Objective function for Nelder-Mead optimization.
    Returns negative correlation (to minimize).
    """
    pass

def refine_position_nelder_mead(
    image_path: str,
    gps_lat: float,
    gps_lon: float,
    gps_alt: float,
    initial_offset: tuple = (0.0, 0.0),
    max_iterations: int = 100,
) -> dict:
    """
    Refine camera position using Nelder-Mead optimization.

    Returns:
        dict with:
            - refined_position: (lat, lon, alt)
            - offset_from_gps: (dx, dy) in meters
            - final_correlation: float
            - iterations: int
            - convergence_history: list
    """
    pass
```

## Comparison with Grid Search

| Aspect | Grid Search | Nelder-Mead |
|--------|-------------|-------------|
| Function evaluations | O(n²) for n×n grid | O(50-100) typical |
| Global vs local | Global within grid | Local only |
| Visualization | Easy heatmap | Trajectory plot |
| Resolution | Fixed by grid | Adapts automatically |
| Best use | Exploration | Refinement |

**Recommended workflow**:
1. Grid search (coarse, 20m steps) to understand landscape
2. Nelder-Mead from best grid point for fine refinement

## Success Criteria

1. **Convergence**: Nelder-Mead converges in <100 iterations
2. **Improvement**: Final correlation > initial (GPS) correlation
3. **Qualitative**: Refined position produces single peak matching image
4. **Efficiency**: Faster than dense grid search for same accuracy

## Potential Issues & Mitigations

1. **Local minimum**: Use multi-start or combine with grid search
2. **Noisy objective**: Increase `fatol` tolerance; smooth objective if needed
3. **Slow convergence**: Check if objective is well-conditioned; try Powell method as alternative
4. **Out-of-bounds**: Add penalty term for positions too far from GPS

## Dependencies

- `scipy.optimize.minimize` (Nelder-Mead)
- Existing codebase: `skyline/dem/nagy_20.py`, `skyline/image/*.py`
- NumPy, Matplotlib
- pyproj for coordinate conversions

## Alternative Methods to Consider

If Nelder-Mead underperforms:
- **Powell's method**: `method='Powell'` in scipy, sometimes faster
- **COBYLA**: Handles constraints directly
- **L-BFGS-B**: If we can approximate gradients via finite differences
