# Automatic orientation of historical terrestrial images in mountainous terrain using the visible horizon 

Sebastian Mikolka-Flöry *, Camillo Ressl, Lorenz Schimpl, Norbert Pfeifer<br>TU Wien, Department of Geodesy and Geoinformation, Research Unit Photogrammetry E120.7, Wiedner Hauptstraße 8/E120, Vienna, 1040, Austria

## ARTICLE INFO

## Keywords:

Automatic orientation
Historical terrestrial image
Spatial resection
Horizon
Monoplotting


#### Abstract

Historical terrestrial images are the only visual sources documenting alpine environments shortly after the end of the Little Ice Age. Despite their unique value, they are largely unused for quantifying environmental changes because of the difficult and time-consuming estimation of the unknown camera parameters. For most images large parts of the captured scenery have vastly changed over time, making automatic feature point matching infeasible. In contrast, the visible image horizon seems to remain stable over time and hence, appears to be a suitable feature for image orientation. Since the focal length is unknown for historical terrestrial images, existing methods, focusing solely on estimating the exterior orientation of recent imagery, can not be applied. Accordingly, it was investigated if the horizon is suitable to estimate both the interior and exterior orientation of historical terrestrial images, with an accuracy comparable to manually oriented images. In a first step, the whole horizon was used to approximate the unknown camera parameters, reducing the potential search space. In the subsequent spatial resection these approximations were further refined using salient points along the horizon. We evaluated our approach using 204 manually oriented reference images. With the proposed method the accuracy of the estimated exterior orientation could be significantly improved compared to previous works. Additionally, the unknown focal length was estimated within $5 \%$ of the true focal length for $75 \%$ of the images. As historical terrestrial images are commonly used for monoplotting, the accuracy for 2400 manually selected checkpoints was evaluated. This analysis showed that for $63 \%$ of the images the same accuracy as with manually oriented images was achieved. For additional $22 \%$ the estimated camera parameters were still accurate enough to serve as initial estimates for a subsequent manual orientation. In $15 \%$ of the images our method completely failed. Due to the vastly changing scenery and oblique viewing geometry, finding the initial camera parameters, in our experience, is often the most challenging and time consuming step during manual orientation of historical images. Hence, in $85 \%$ of the images this initial step can be replaced with our method, leading to a significantly reduced effort for orienting whole collections of historical terrestrial images.


## 1. Introduction

Since 1850, the end of the little ice age (LIA), mountain regions like the Alps are strongly affected by the climate change (Nogués-Bravo et al., 2007). Commonly used historical aerial images, dating back as far as 1940, provide only a glimpse into the recent past. Leaving a gap of nearly 100 years, additional sources are necessary, documenting the early changes of these environments as an immediate response to the changing climate. With the advent of alpinism and the increasing availability of cameras, historical terrestrial images of the Alps became available around 1870, 70 years earlier than aerial images. Accordingly, these images are the only visual sources showing European alpine
environments in their nearly unaltered LIA state and therefore represent a unique and invaluable resource for many research areas including botany, hydrology, glaciology and geomorphology.

Historical terrestrial images are commonly used for monoplotting (Kraus, 2012; Bozzini et al., 2012), by intersecting rays from the projection center through individual pixels with a reference digital terrain model (DTM), to analyse environmental changes including natural hazards (Conedera et al., 2018), glacial changes (Scapozza et al., 2014) or Alpine Treeline Ecotone (McCaffrey and Hopkinson, 2020). Accordingly, the interior and exterior orientation have to be estimated. Being acquired in an unsystematic manner by mountaineers, tourists and locals over multiple decades, combined orientation of multiple images is

[^0]![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-02.jpg?height=853&width=1199&top_left_y=187&top_left_x=124)
Fig. 1. In the historical images (Source: Archive of the Austrian Alpine Club (ÖAV, Innsbruck)) from 1905 (top-left) and 1907 (top-right) the dominant visual features are the glaciers, covering most of the captured scenery. In the repeated photographies (Source: Moritz Altmann) from 2019 (bottom row) the glaciers are barely visible anymore. While most of the image content changed, the image horizon appears stable. Both historical images show the tongue of the Geptaschferner glacier in Kauner valley, Austria.

not feasible. Therefore, each image has to be oriented individually by spatial resection, using manually selected ground control points (GCPs) both in image and object space. Generally, the term spatial resection refers to the estimation of the 6 unknown parameters of the exterior orientation. Within this work spatial resection includes the estimation of the interior orientation in form of the unknown focal length, whereas the coordinates of the principal point are considered fixed in the image center. For historical terrestrial images the identification and selection of GCPs is very challenging. The oblique viewing geometry and the vast change in the captured landscape make the manual selection increasingly difficult, more time consuming and requiring more experience. Furthermore, the surrounding topography heavily restricts the horizontal field of view (HFOV), especially in mountainous terrain. Accordingly, the requirements for orienting whole image collections of hundreds or even thousands of images is disproportionately high and, despite their unprecedented potential, historical terrestrial images have not been used for quantitative analysis at larger scales yet (Stockdale et al., 2015).

Hence, automatic methods for the orientation of historical terrestrial images are required. The most accurate automatic methods establish correspondences between query images and georeferenced reference data (Sattler et al., 2011; Liu et al., 2017; Sarlin et al., 2019). Unfortunately, these methods are not well suited for natural environments: i) In natural environments dense reference datasets are rarely available and ii) they change vastly throughout the year with the seasons. In the case of historical images these changes are even more dramatic as shown in Fig. 1. Large parts of the historic images (top row) have completely changed as the glacier has melted. Hence, these image regions will not even contain corresponding points with recent images (bottom row). At the same time, however, one can observe that the visible horizon is less affected by these vast changes, mostly remaining stable over time. Therefore, it seems obvious to extract salient points along the image horizon and salient points of the terrain to calculate the spatial resection without the need for manual GCPs. Unfortunately, matching points between images and a mountain scenery is not unique. Typically, $10-50$ salient points are extracted along image horizons, whereas in the object space even for small mountainous regions the number of peaks easily exceeds a few thousand. While RANSAC (Fischler and Bolles, 1981) was proposed to deal with a high proportion of outliers, the number of iterations to select a valid combination of points leads to unusable
processing times.
Hence, Naval et al. (1997) proposed a "K-Nearest Feature Point Search Strategy" based on the assumption that nearby peaks on the image horizon are also close in the object space. While this might be true for their specific setup using images of one prominent mountain in Japan, this assumption does not hold true for mountainous regions. In the majority of the cases the image horizon consists of multiple spatially distributed ridge lines in the object space. Furthermore, selecting nearby points both in the image and object space on purpose might lead to unstable geometric constellations within the spatial resection, one normally wants to avoid. Instead of using individual salient points extracted along the horizon, Baatz et al. (2012) matched the visible horizon in query images with horizons extracted from a digital terrain model (DTM). Followed by a refinement step using ICP (Besl and McKay, 1992) they reported that for $88 \%$ of the images the projection center was estimated within 1 km of the ground truth position, not considering any deviation in the angular orientation of the camera. Pan et al. (2020) extended the approach by using a different representation for the horizons and incorporated so called "lapel points". In Tang et al. (2022) full panoramic images were used, achieving an average error of 42 m for 50 test images considering an area of approximately $200 \mathrm{~km}^{2}$. A slightly different approach related to horizons was suggested in Tomešek et al. (2022), using rendered modalities of the terrain. Considering images from the whole Alps they estimated $39 \%$ of them within 1 km of the reference position. While all of these approaches have shown that horizons can be used to estimate the exterior orientation of recent imagery with varying accuracy, the situation for historical terrestrial images differs in several aspects:

- Most approaches are devoted to large scale recognition tasks considering whole countries (Baatz et al., 2012) or the whole Alps (Tomešek et al., 2022). In case of historical terrestrial images the potential search region can be limited due to available metadata. Being part of larger collections in archives, all images at least contain information regarding the valley where they were acquired, sometimes even the names of captured geographical features (e.g. mountains, glaciers, mountain range). Considering smaller regions has two advantages: i) Less potential error sources are present and ii) potentially more detailed feature descriptors can be used because storage and processing times are generally lower for smaller regions.

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-03.jpg?height=778&width=1199&top_left_y=189&top_left_x=124)
Fig. 2. Schematic illustration of the proposed method. Image and terrain horizons were both split into smaller overlapping horizon parts. For each image horizon part the k nearest terrain horizon parts were searched and ordered. After ranking these matches, the results of the coarse orientation were used to establish correspondences between prominent points along the image and terrain horizons. These correspondences were used in the subsequent spatial resection leading to the selection of the final solution.

- For historical terrestrial images the focal length is unknown. While (Baatz et al., 2012) briefly discussed the influence of an unknown focal length based on one image, no thorough evaluation has been conducted yet as in all previous works the focal length was known.
- In previous works only the distance to the reference camera position was considered for evaluation, but the deviation in azimuth direction was improperly included. If it was addressed, huge thresholds were chosen e.g. $30^{\circ}$ in (Tomešek et al., 2022).

Furthermore, the aforementioned works solely focused on estimating the position of modern images whereas in our case the estimation of the unknown camera parameters is only a prerequisite for subsequent spatial analysis. Considering that the main usage will be monoplotting, the potential accuracy varies strongly within the image, being not only dependent on the accuracy of the estimated camera parameters, but also on the topography of the captured scenery. Hence, only considering the accuracy of the interior and exterior orientation is not sufficient. To address the monoplotting accuracy of manually oriented images, Bayr (2021); Stockdale et al. (2015) used manually identified checkpoints. By calculating the distance between the reference coordinates and the coordinates obtained from monoplotting using the estimated camera parameters, both the influence of the camera parameters as well as the topography were addressed for. Using this measure, Bayr (2021) reported an average error of 1.52 m for 7 modern images containing 56 points in total. Based on 8 historical images and a total of 121 points, Stockdale et al. (2015) reported a considerable larger error of 14.7 m . Following these considerations, the question arises if it is possible to automatically estimate both the interior and exterior orientation of historical terrestrial images using the visible horizon with an accuracy comparable to the ones achieved in (Bayr, 2021; Stockdale et al., 2015). The only assumption we make is, that the potential location of the photograph can be restricted to at least an alpine valley which in our case corresponds to approximately $100 \mathrm{~km}^{2}$. We test our approach on 204 images selected from 3 different alpine valleys acquired between 1890 and 1990. To quantify the accuracy of the proposed approach not only the deviation from the reference camera position and rotation are addressed, but we also conduct analysis based on more than 2400 manually selected checkpoints. Our main contributions are:

- Extension of automatic image orientation to historical terrestrial images.
- Comparison and evaluation of new horizon descriptors.
- Automatic estimation of the exterior and interior orientation.
- Thorough accuracy assessment using manually identified GCPs addressing the potential usage for monoplotting.


## 2. Method

Our proposed approach is illustrated in Fig. 2. Within the coarse orientation, in the first step, the feature extraction, image and terrain horizons were both split into smaller overlapping parts of predefined width and each horizon part was described using a vector of feature descriptors. In the subsequent horizon matching, the image horizon parts were matched to the terrain parts. After ranking these matches, to generate a top-n list, the top-n candidates were further used to establish point correspondences between prominent points along the image and terrain horizons. In the last step, the spatial resection, the top-n candidates retrieved from the coarse orientation were further refined based on these point correspondences and a final estimate for the interior and exterior orientation of the camera was calculated.

### 2.1. Coarse orientation

The goal of the coarse orientation was to reduce the potential search space for corresponding pairs of salient points along the image horizon and of the terrain. To calculate the coarse orientation, grid points were selected every 100 m within our study areas. For each grid point the full panoramic horizon was calculated, further refereed to as terrain horizons. The basic idea was, that the grid point having the best matching terrain horizon with the image horizon will be very close to the position where the image was originally taken. Furthermore, by locating the image horizon within the best matching panoramic terrain horizon an estimate for the azimuth of the camera could be derived. More details on the extraction of the image and terrain horizons are given in Section 3.

For the calculation of the terrain horizons we assumed a perfectly levelled camera whereas in reality cameras are generally slightly tilted and rotated. These slight changes introduce systematic differences between the image and terrain horizon geometry. Furthermore, the terrain horizons, extracted from a DTM, will never be identical with the image horizons. Because of these unavoidable differences between image and terrain horizons, shape feature descriptors were used to describe the horizons, increasing robustness against these differences. In the following we will refer to these descriptors as horizon descriptors.

As cameras have various HFOVs, using the full image horizon for

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-04.jpg?height=808&width=1215&top_left_y=176&top_left_x=120)
Fig. 3. Visual representation of the evaluated horizon descriptors. a) raw horizon part with 8 equally distributed sampling points with a sampling distance of $\frac{w_{h o r}}{N-1}$ b) contourlet with the smoothed horizon c) height function for two sampling points (green) d) invariant multiscale triangle feature for one selected point (green) and two scales $(k=1, k=3)$. The Area component is shown by the blue triangle and cDist as the orange dashed line. See Section 2.1.1. (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

matching was problematic because it would become necessary to recalculate the horizon descriptors of all terrain horizons for each query image individually. To circumvent this step, we followed Baatz et al. (2012) using overlapping horizon parts of predefined width $w_{h o r}$ extracted every $1^{\circ}$ for all image and terrain horizons. Hence, the horizon descriptors were calculated for these image and terrain horizon parts. As only selected candidates from the coarse orientation were further considered within the spatial resection, the quality of the horizon descriptor had direct influence on the overall accuracy of our method. Accordingly, its choice was crucial and three different ones were evaluated.

### 2.1.1. Horizon descriptors

2.1.1.1. Contourlets (CONTS). Introduced by Baatz et al. (2012) in their large scale localization approach, $N$ equally distributed points were sampled from a low-pass filtered horizon part of width $w_{h o r}$ (Fig. 3-b). The mean value $\bar{y}$ of the sampled values $\widetilde{y}_{i}$ was subtracted, making the descriptor invariant to the vertical position in the image. Furthermore, the descriptor of each part was divided with $w_{h o r}$ (Equation (1)).

$$
\begin{equation*}
y_{i}=\frac{\tilde{y}_{i}-\bar{y}}{w_{h o r}} \quad \text { for } i=1, \ldots, N \quad \text { with } \bar{y}=\frac{1}{N} \sum_{j=1}^{N} \tilde{y}_{j} \tag{1}
\end{equation*}
$$

In the original implementation $N=8$ was chosen to quantize the final descriptor into a 24 -bit integer word using 3 bits for each $y_{i}$. In our implementation this step was skipped and $y_{i}$ was directly used, allowing different values for $N$ to be evaluated. Accordingly, the length of this horizon descriptor is equal to the number of sampling points.
2.1.1.2. Height functions (HF). Height functions (Wang et al., 2012) show interesting properties in the context of horizon matching as they are invariant to translation, rotation and scaling. Furthermore, Wang et al. (2012) showed that even smaller deformations introduced by noise or occlusion had only little impact on the recognition performance. For each point of $N$ equally distributed sampling points, the distance of all other sampling points with respect to the local tangent line were calculated (Fig. 3 - c). Furthermore, the calculated height values were smoothed and normalized by their maximum value. Smoothing was achieved by calculating the mean height value for every $k$ consecutive points. The final dimension of this horizon descriptor is ( $M \times N$ ) with $M=\frac{N}{k}$ being the number of the smoothed height values and $N$ the
number of sampling points.
2.1.1.3. Invariant multiscale triangle features (IMTF). Being the most recently published descriptor used in our work, invariant multiscale triangle features (Yang and Yu, 2021) achieved promising results on various benchmark datasets having characteristics being similar to the ones encountered in the horizon matching problem. The IMTF descriptor (Fig. 3 - d) is a concatenation of two individual feature parts namely the triangle area Area and centroid distance cDist. Both were calculated at T scales for $N$ equally distributed sampling points (Equation (2)).

$$
\begin{equation*}
I M T F=\left\{\operatorname{Area}_{k}(i), \operatorname{cDist}_{k}(i)\right\} \quad \text { with } k \in[1, T], i \in[1, N] \tag{2}
\end{equation*}
$$

Following Yang and Yu (2021), $T$ was defined as $\log _{2}\left(\frac{N}{2}\right)$. For each sampling point $p_{i}$ two adjacent points were defined as $p_{i-h(k)}$ and $p_{i+h(k)}$ with $h(k)=2^{k-1}$ and $i$ being the index of the current point. The $\operatorname{Area} a_{k}(i)$ and $c \operatorname{Dist}_{k}(i)$ were calculated

$$
\begin{align*}
\operatorname{Area}_{k}(i) & =\frac{1}{2}\left|\begin{array}{ccc}
x_{i-h(k)} & y_{i-h(k)} & 1 \\
x_{i} & y_{i} & 1 \\
x_{i+h(k)} & y_{i+h(k)} & 1
\end{array}\right|  \tag{3}\\
\operatorname{cDist}_{k}(i) & =\sqrt{\left(x_{i}-x_{c}\right)^{2}+\left(y_{i}-y_{c}\right)^{2}}
\end{align*}
$$

with $x_{c}, y_{c}$ being the coordinates of the current centroid point, calculated using

$$
\begin{align*}
& x_{c}=\frac{x_{i-h(k)}+x_{i}+x_{i+h(k)}}{3}  \tag{4}\\
& y_{c}=\frac{y_{i-h(k)}+y_{i}+y_{i+h(k)}}{3}
\end{align*}
$$

Both parts were individually normalized by dividing with the largest Area or cDist over all scales. Hence the values for Area are in the range $[-1,1]$ and for cDist in [ 0,1 ]. The feature dimension $d_{\text {feat }}$ of the IMTF descriptor is $2 \times N \times \log _{2}(N / 2)$.

### 2.1.2. Horizon matching and ranking

The horizon matching was formulated as a k-nearest neighbor (kNN) search. As outlined earlier, $P$ image horizon parts, with $P$ depending on $w_{h o r}$ and the HFOV of the image, were extracted for each image and the $k$ nearest terrain horizon parts were returned. This results in $P \times k$ matches.

The goal of the coarse orientation is to find the best grid point, the

Table 1
Percentage of 204 images for which among the top-n at least one candidate could be found using the specified bounds. A potential candidate was considered as valid if its euclidean distance was closer than $250 m$ from the ground truth projection center and the estimated azimuth direction differed less than $2.5^{\circ}$. Bold values indicate the highest \% for each top-n.
| Descriptor | $\operatorname{dim}_{\text {desc }}$ | top-n |  |  |  |  |  |  |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
|  |  | 1 | 5 | 10 | 25 | 50 | 75 | 100 |
| CONTS | 20 | 37.3 | 63.7 | 69.1 | 78.4 | 81.9 | 82.8 | 83.3 |
| HF | 800 | 31.4 | 54.4 | 58.8 | 64.2 | 71.6 | 75.5 | 77.0 |
| IMTF | 96 | 72.5 | 88.2 | 89.7 | 91.7 | 92.2 | 92.2 | 92.2 |
| IMTF_Area | 48 | 73.0 | 86.8 | 89.2 | 90.7 | 91.2 | 91.7 | 92.2 |
| IMTF_cDIST | 48 | 65.7 | 86.3 | 90.2 | 91.7 | 93.6 | 94.1 | 94.1 |


one being closest to where the image was taken. Assuming that the location of the grid point, which occurs most within these matches, is the one closest to the true camera location, we counted the occurrences for each grid point within these matches and sorted descending. Unfortunately just counting the occurrences was error prone due to mismatches. As reported by Baatz et al. (2012), this task benefits from considering also the direction of the terrain and image horizon parts. Therefore the difference of these two directions were additionally stored as azimuth for each match. The best overall candidate was that grid point which had the highest count of similar azimuths. In our experiments a threshold of $1^{\circ}$ was used for clustering the calculated azimuths. For the nearest neighbor search $k$ was set to 1000 .

To further increase the accuracy of the coarse orientation, Baatz et al. (2012) combined the results of different $w_{h o r}$. Accordingly, we repeated the k-NN search for different $w_{h o r}$ and merged the results before calculating the final ranking. In our experiments a combination of $10^{\circ}$ and $20^{\circ}$ for $w_{h o r}$ performed best.

The usage of smaller horizon parts was originally suggested for the case of known focal lengths. Hence, the question arose if extracting smaller parts was still necessary in the case of unknown focal length, as one could assume various HFOVs for the whole image and conduct the kNN matching based on the whole image horizon. Comparison of both approaches showed that using smaller parts still achieved significantly better results. Furthermore, another benefit of using smaller horizon

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-05.jpg?height=1403&width=1201&top_left_y=1145&top_left_x=122)
Fig. 4. Correlation between distance to the ground truth projection center ( $d_{3 D}$ ), maximum inlier count and height above terrain of the estimated cameras (blue dots). If the camera with the highest inlier count was selected (red point) it is not necessarily the one closest to the ground truth reference. Hence, the 10 candidates with the lowest absolute height above the DTM (orange points) are identified. From this subsample the one with the highest inlier count (green point) is chosen as our final "best" candidate. The ground truth camera is displayed as a white point with a vector indicating the reference azimuth. The image (top right) was provided by the Archive of the Austrian Alpine Club (ÖAV, Innsbruck). (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

parts was that gaps present in image horizons e.g. due to small clouds could easily be dealt with.

### 2.1.3. Unknown focal length

In contrast to Baatz et al. (2012); Pan et al. (2020) the focal length of the historical terrestrial images is unknown. Accordingly, the width $w_{h o r}$ of the extracted image horizon parts was relative. To account for the unknown focal length, the matching was repeated multiple times with varying HFOVs for each query image and a ranked list of candidates was stored for each HFOV. As the selected horizon descriptors compensate for smaller differences and variations between an image and terrain horizon part, it was not necessary to sample the potential ranges of HFOVs very densely. Furthermore, the HFOV , and therefore the focal length, was further refined in the subsequent spatial resection. Hence, in our experiments we sampled the range from $25^{\circ}$ to $65^{\circ}$ every $5^{\circ}$ which proofed to be a good compromise between accuracy and run time. The range was selected as it represents the typical HFOV for commonly used historical cameras.

### 2.2. Spatial resection

The result of the coarse orientation were ranked lists with potential candidates for each evaluated HFOV . Each candidate contained the coordinates of its grid point, a calculated azimuth and the used HFOV. For the spatial resection these estimates were used to limit the potential search space for finding corresponding point pairs between the image and terrain horizons.

We considered prominent points along the terrain and image horizon, extracting both local maxima (=peaks) and minima (=saddle points). These prominent points will be further referred to as horizon GCPs (HGCPs). To calculate the spatial resection, point correspondences between the image and terrain HGCPs were required. As we assumed that the azimuth obtained from the coarse orientation was a good estimate of the true azimuth, the correspondence search was guided as only HGCPs within $\pm 1^{\circ}$ were considered as potential matches. While potential false matches were significantly reduced, multiple HGCPs were still present as candidates within this search range. Accordingly, it was further necessary to describe the HGCPs using a feature point descriptor. As we will show in Table 1, the IMTF_Area descriptor achieved good results in describing horizon parts and therefore it was also used as a descriptor for the HGCPs. To further reduce mismatches, the inverse matching from terrain to image HGCPs was also computed and only mutual matches were kept.

Based on the potential point pairs obtained from the guided point matching, we used RANSAC in combination with the method presented by Gao et al. (2003) to calculate the spatial resection. Within the coarse orientation, the HFOV selection was limited to $5^{\circ}$ steps in order to reduce processing times. Hence, the available focal length was only a rough estimate. Sattler et al. (2014) showed that the unknown focal length can be estimated by sampling various focal lengths and using the RANSAC inlier count as a direct measure for the correct focal length. Accordingly, to refine the initial estimate, the spatial resection was rerun multiple times for each candidate varying the HFOV in the range $H F O V_{\text {coarse }}-2.5^{\circ} \leq H F O V \leq H F O V_{\text {coarse }}+2.5^{\circ}$ with a step width of $0.1^{\circ}$. The RANSAC inlier threshold was set to $3 p x$. As we expected a high inlier count due to the prior coarse orientation, the maximum number of iterations within RANSAC was limited to 10000.

To find the best solution from the spatial resection for the query image, two different approaches were evaluated: In the first approach only the maximum inlier count was used for ranking the solutions, further referred to as N-IN.

In the second approach also the height difference to the ground was considered and is outlined in the following (Fig. 4). Due to the acquisition geometry and the geometry of the horizon itself, HGCPs were poorly distributed both in the image and object space. In the image space all HGCPs were located within a narrow region of the image distributed
mainly horizontally. In object space, all HGCPs were approximately equidistant from the camera. Especially HGCPs in the foreground of the image, corresponding to points being closer to the camera in object space, were missing. This poor distribution of HGCPs both in image and object space combined with the unknown focal length led to multiple solutions having the same or similar amount of inliers, making it an unstable predicate for the selection of the best solution. Terrestrial images are generally captured close above ground and accordingly, the estimated camera height must be close to the ground as well. We observed that in the spatial resection, varying the focal length had only little influence on the height of the camera, but shifted the cameras position a lot along the viewing direction. Due to the topography and the fact that images were captured from slightly raised positions, the absolute height difference to the ground was larger as the estimated position was further away from the reference position. By adjusting the focal length towards its true reference, the absolute height difference got smaller. Hence, we incorporated this absolute height difference into the selection of the best solution from the spatial resection. In a first step, the 10 solutions having the lowest absolute height difference to the ground were selected. From this smaller subset the one was selected as best solution, having the highest inlier count. This method is referred to as N-IN-H.

## 3. Datasets

### 3.1. Query images

A total of 204 historical terrestrial images were selected from 3 different study areas: Kauner valley and Horlach valley in Tyrol (Austria) and Martell valley in South Tirol (Italy). For Kauner and Horlach valley the images were obtained from various archives and private persons. In Martell valley the major proportion of the images was provided by the Italian Glaciological Committee, conducting repeated photographic surveys since 1920 to document the development of the Italian glaciers. The images cover a time span of approximately 100 years from 1890 to 1990.

### 3.2. Terrain horizons

To calculate the terrain horizons a DTM with $5 m$ resolution was used. According to the manufacturer the vertical accuracy of the DTM is within $\pm 10 \mathrm{~cm}$. While this accuracy did not have a direct influence on our results, the resolution of the DTM introduced potential error sources. With a grid size of $5 m$ some smaller peaks were not represented by the DTM and hence were not available for matching. Furthermore, the terrain horizons contained additional differences compared to the image horizons beyond the ones expected due to the retreat of snow or glaciers. While in theory this could have influenced our approach, we observed that due to the quality (e.g. resolution, exposure) of the historical terrestrial images, which is not comparable to modern images, the terrain horizons were not the limiting factors within our approach but the horizon extracted from the images.

Grid points, used for calculating the terrain horizons, were regularly positioned on a $100 m$ grid within our study areas. The height of each grid point was set to $2 m$ above ground. In each grid point we defined a horizontal ray starting from the current grid point towards a specified direction e.g. north. All DTM grid cells intersected by this ray were identified using Bresenham's line algorithm (Bresenham, 1965) and the angle of elevation was calculated for each cell. The grid cell with the highest angle of elevation defines the horizon for this specific direction. By rotating the ray around the grid point with a step width of $0.01^{\circ}$ the full panoramic horizon was derived. The step width was chosen as it results in a spacing of 5 m , the resolution of the used DTM, between consecutive rays at a distance of 25 km . We limited the length of the ray to 25 km as prior analysis within our study areas revealed that no visible peaks are more distant. The number of grid points ranges between

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-07.jpg?height=1153&width=1199&top_left_y=189&top_left_x=124)
Fig. 5. Comparison of the coarse orientation with known focal length for 2 selected images using CONTS and IMTF_Area descriptors. On the left both descriptors performed equally well, whereas in the second example (right column) only using the IMTF_Area descriptor resulted in valid potential candidates. The red circle indicates the $250 m$ radius around the reference position. The historical image shown in the left column was acquired between 1880 and 1890. The right image between 1881 and 1892. Both images were provided by Archive of the German Alpine Club (DAV, Munich). (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

~5500 for Horlach valley and ~6200 for Kauner and Martell valley.

### 3.3. Reference data

For evaluation, the query images were manually oriented using 5-10 GCPs per image, resulting in 2400 GCPs in total. While the automatic orientation method was solely based on points along the horizon, for the manual orientation GCPs in the whole image region, including the foreground, could be identified. These points were not only used for the manual reference orientation but also for evaluating the potential accuracy of the automatic orientation method in more detail.

## 4. Results and discussion

### 4.1. Evaluation metrics

For the coarse orientation we evaluated how many of the top-n candidates contain at least one correct estimate using a distance threshold of 250 m and a direction threshold of $2.5^{\circ}$. In contrast to Baatz et al. (2012); Pan et al. (2020) we considered not only the distance to the ground truth projection center, but also the deviation in azimuth direction. Both thresholds were chosen such that a camera having the estimated parameters still looks towards the correct terrain horizon, which is an important prerequisite for the subsequent spatial resection. In addition, as the coarse orientation was used as preliminary step, evaluation based on the top-n candidates easily allowed to decide how many candidates needed to be considered in the spatial resection without excluding good ones.

The final goal of the automatic orientation was to obtain one estimation for the exterior and interior orientation of the query image. Hence, in contrast to the coarse orientation, only one selected solution per camera was evaluated for the spatial resection considering multiple
distance and direction thresholds. For terrestrial images the critical component of the camera rotation is the azimuth direction, as due to the acquisition geometry the other two angles used to describe the full orientation in 3D space are indirectly defined and vary only slightly. Hence, besides the distance threshold only the azimuth direction was considered. For the estimated focal length $f_{\text {est }}$ we used the relative error defined as

$$
\begin{equation*}
\left|d_{\text {relF }}\right|=\left|1-\frac{f_{\text {est }}}{f_{\text {ref }}}\right| * 100 \tag{5}
\end{equation*}
$$

with respect to the true focal length $f_{\text {ref }}$. Hence, various focal lengths can be compared easily with each other.

To evaluate the accuracy of the automatic orientation method with regard to monoplotting, the manually selected GCPs were used. Monoplotting these GCPs, using the automatically estimated camera parameters, resulted in errors from their true position in object space. These errors result from inaccuracies of the estimated camera parameters and further depend on the viewed topography and position of the GCPs both in the image and object space. Hence, by analysing these errors, all factors influencing the accuracy of monoplotting could be considered.

### 4.2. Coarse orientation

### 4.2.1. Comparison of horizon descriptors

To evaluate the performance of the different horizon descriptors, various settings and parameters were tested. To exclude the influence of the unknown focal length and evaluate the performance of the descriptors itself, the reference focal lengths were used. Further, only the best combination of parameters are reported in Table 1 for each descriptor. For CONTS the number of sampling points $N$ achieving the highest result was 20 for both horizon part widths ( $10^{\circ}$ and $20^{\circ}$ ), $N=16$

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-08.jpg?height=586&width=1201&top_left_y=183&top_left_x=434)
Fig. 6. Top-5 candidates for each evaluated HFOV for the same images used in Fig. 5. Colors of the points indicate the used HFOV . The true HFOV is $34.9^{\circ}$ for the left and $43.9^{\circ}$ for the right example. The red circle indicates the 250 m radius around the reference position. (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

for IMTF and for HF a combination of $N=40$ with $M=20$.
The top-1 accuracy of the IMTF descriptor was significantly higher compared to both CONTS and HF. In 73\% of the images the top candidate was within the specified bounds which was about twice as high as the top- 1 accuracy using CONTS. While HF was the horizon descriptor having the highest dimensionality, it performed worst. Compared to CONTS, the dimensionality of IMTF is roughly five times larger. For historical terrestrial images the region of interest can be limited due to the available metadata and therefore, the dimension of the horizon descriptor was not as a limiting factor as for the large scale localization problem addressed in Baatz et al. (2012). Nevertheless, lower dimensionality was preferable in terms of disk storage and processing times, especially in the case of unknown focal lengths. As mentioned in Section 2.1.1, the IMTF descriptor is the concatenation of two individual parts (IMTF_Area and IMTF_cDIST) and the matching was repeated with each part individually. The top-1 accuracy for IMTF_Area was even slightly higher compared to the complete descriptor whereas for IMTF_cDIST the accuracy was reduced. Interestingly, the situation was different for the top-5 and top-10 accuracy: For top-5 the complete descriptor achieved the best result whereas from top-10 on IMTF_cDIST performed best, but these differences were only marginal and therefore negligible. Hence, for all remaining experiments the IMTF_Area descriptor was chosen, reducing the descriptor dimensionality by $50 \%$. As the accuracy did not increase significantly beyond the top-5 candidates, only these were further used.

Fig. 5 shows the top- 5 candidates for two selected images using the CONTS (top row) and IMTF_Area (bottom row) descriptor. For the example shown in the left column both descriptors performed equally well. All top- 5 candidates were tightly clustered around the reference position, highlighted in red. In addition, the estimated azimuths, indicated by the lines originating from the respective points, were nearly identical. In the second example shown on the right, the situation is somewhat different. While the top-5 candidates using the IMTF_Area descriptor were again tightly clustered around the reference position, all candidates were far off using CONTS.

### 4.2.2. Unknown focal length

To estimate the unknown focal length the coarse orientation was repeated multiple times with different HFOVs . Following the evaluation of the coarse orientation with known focal length (Table 1), for each HFOV the top- 5 candidates were selected. Fig. 6 shows the result using the IMTF_Area descriptor for the same examples as in Fig. 5. Two different situations were observed: In the left example each HFOV results in tight clusters of the top-5 candidates all facing towards the correct direction. Due to wrong HFOVs the clusters appeared translated

Table 2
Comparison of the recall in \% for the coarse orientation with unknown focal length using two different ranking methods. A potential candidate was considered as valid if its euclidean distance was closer than 250 m from the ground truth projection center and the estimated azimuth direction differed less than $2.5^{\circ}$.
| Descriptor | Ranking | top-n |  |  |  |  |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
|  |  | 1 | 5 | 10 | 25 | 45 |
| IMTF_Area | CNT | 45.1 | 65.7 | 77.9 | 83.8 | 89.2 |
| IMTF_Area | N-CNT | 49.5 | 73.5 | 80.9 | 88.2 | 89.2 |


along the direction of acquisition, resembling the well-known correlation between focal length and computed distance to the observed object. In the second example (Fig. 6 - right) the top- 5 candidates appeared randomly oriented and distributed over the whole region of interest with increasing difference from the reference HFOV. Despite these differences, in both examples the top-5 candidates converged towards the reference position as the HFOV approaches the true HFOV .

The question remained how to select the overall top-n candidates from these $F \times n$ candidates with F being the number of different HFOVs and $n$ the number of top-n candidates considered in each HFOV . As we sampled the HFOV 9 times from $25^{\circ}$ to $65^{\circ}$ and selected $n=5$, a total of 45 potential candidates were available. As for the case of the known focal length, we ranked these 45 candidates descending by their number of matched parts, referred to as CNT in Table 2. Unfortunately this measure was biased when comparing different HFOVs as choosing a wider HFOV potentially led to a higher number of image horizon parts. Hence, also the number of matches tend to be higher for wider HFOVs. Accordingly, we normalized the counts by the total number of image horizon parts for each HFOV, referred to as N-CNT in Table 2.

The accuracy was slightly improved using the normalized counts for the final ranking for multiple HFOVs. Nevertheless, comparing the results with the accuracy achieved using the known HFOV showed that the top-1 accuracy dropped by $25 \%$. While some loss was expected due to the unknown focal length and the decision to only sample the HFOV every $5^{\circ}$, the vast decrease is not solely explained by that. Further visual inspection revealed that correct candidates exist within the obtained candidates but they are just not necessarily the ones with the highest counts. While the match count was a good measure to rank candidates for one HFOV, it is not a good measure, normalized or not, to rank candidates across multiple HFOVs. Unfortunately, no other measure is available after the coarse orientation. Hence, all potential 45 candidates were further used in the spatial resection.

Table 3
Percentage of images having their solution within the specified bounds for the coarse orientation (top-1 candidate, N-CNT) and after the spatial resection (RANSAC using max. N-IN or max. N-IN-H). The last column shows the percentage of images where the automatic orientation completely failed.
| $d_{3 D}[\mathrm{~m}]$ | (0,50] | (0, 100] | (0, 250] | (0,500] | (0, 1000] | (1000, $+\infty$ ] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| $d_{\alpha}\left[{ }^{\circ}\right]$ | (0, 0.5] | (0, 1] | (0, 2.5] | (0, 5] | (0, 10] | (10, 360] |
| N-CNT | 5.4 | 20.6 | 49.5 | 66.7 | 78.9 | 21.1 |
| N-IN | 3.4 | 11.8 | 43.1 | 66.2 | 84.8 | 15.2 |
| N-INH | 19.6 | 40.7 | 63.2 | 75.0 | 85.3 | 14.7 |


### 4.3. Spatial resection

For each of the 45 candidates the interior and exterior orientation was calculated by spatial resection using RANSAC. Table 3 shows the percentage of images where the selected candidate for each image was within various distance ( $d_{3 D}$ ) and direction ( $d_{\alpha}$ ) thresholds, including not only results from the spatial resection (N-IN, N-IN-H) but also from the coarse orientation (N-CNT).

Interestingly, using the maximum inlier count (N-IN) for ranking the results of the spatial resection yielded worse results than the coarse orientation itself. This was quite surprising as grid points located every 100 m were used for the coarse orientation, limiting the potential accuracy one could achieve. Furthermore, the HFOV was sampled only every $5^{\circ}$ in the coarse orientation, whereas it was further refined within the spatial resection. Following Sattler et al. (2014) the maximum inlier count should have approached a maximum when the focal length approached its true value. Hence, by selecting the candidate with the highest inlier count we expected a significant increase in accuracy of the automatic orientation. Unfortunately, this was not true for prominent points sampled from horizons. As outlined earlier, the distribution of the HGCPs in the image and object space led to similar or equal RANSAC inlier counts for various solutions. Hence, we further considered the absolute height difference to the ground as an additional measure which led to a massive improvement (N-IN-H). Selected solutions being closer than 50 m and having an azimuth difference of less than $0.5^{\circ}$ increased from $5 \%$ for the coarse orientation to $20 \%$. For 100 m and $1^{\circ}$ difference $40 \%$ were achieved using N-IN-H, which is twice as high as for the coarse orientation.

### 4.3.1. Estimation of the focal length

Besides the exterior orientation, the unknown focal length was estimated as well. As shown in Fig. 7 (left), for $75 \%$ of the images the magnitude of the relative focal length error $\left|d_{\text {rel } F}\right|$ was smaller than $5 \%$ using N-IN-H and only $50 \%$ for N-IN. Hence, estimating the focal length was significantly improved incorporating the height above ground into the selection of the best solution. This further confirmed our observation that for the horizons the maximum inlier count alone does not necessarily correspond with the true focal length. Furthermore, the accuracy
of the estimated focal length very well agreed with the deviation from the ground truth projection center as well as with the deviation in azimuth direction (Fig. 7 - right). Below a relative error of $25 \%$, accounting for $85 \%$ of the images, almost all estimated camera positions were within 1000 m of the true position and azimuth deviation was less than $2.5^{\circ}$. With increasing $\left|d_{\text {rel } F}\right|, d_{3 D}$ increased whereas no significant increase in $d_{\alpha}$ was observed. Hence, the selected best solutions were mainly translated in direction of the camera azimuth as a direct result of the unknown focal length. Above an error of $25 \%$ the selected solutions were completely off and randomly oriented.

### 4.3.2. Usability for spatial analyses

As outlined earlier, historical terrestrial images are commonly used for monoplotting, intersecting image rays, originating from the projection center through pixels, with a DTM to obtain the coordinates of the pixels in object space. The accuracy of the monoplotted points varies for different parts of the image, depending not only on the estimated camera parameters, but also on the geometry of the captured scene as well. Hence, considering only the estimated camera parameters was not sufficient. Accordingly, we incorporated the 2400 GCPs used in the manual

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-09.jpg?height=800&width=881&top_left_y=951&top_left_x=1059)
Fig. 8. Box plot of the monoplotting error for the checkpoints. The same distance ( $d_{3 D}$ ) and direction ( $d_{\alpha}$ ) thresholds were used as in Table 3. The scale of the $y$-axis is symmetrical logarithmic with a linear range up to 10 m . The orange points are the observations. Whiskers represent the 1.5 IQR (interquartile range) value. (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-09.jpg?height=445&width=1217&top_left_y=2023&top_left_x=424)
Fig. 7. Left: Cumulative percentage of images in relation to the relative focal length error for both ranking methods. Right: Correlation between relative focal length error and distance to the projection center $d_{3 D}$ using the N-IN-H ranking method. The azimuth deviation $d_{\alpha}$ is represented as color. (For interpretation of the references to color in this figure legend, the reader is referred to the Web version of this article.)

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-10.jpg?height=1693&width=1543&top_left_y=185&top_left_x=262)
Fig. 9. Succesfully oriented historical images with rendered terrain based on the automatically estimated camera parameters. First two rows: Source: Archive of the German Alpine Club (DAV, Munich); Third row: Source: Archive of the Austrian Alpine Club (ÖAV, Innsbruck); Remaining images: Source: Franco Secchieri.

orientation of the images as checkpoints. By calculating their object coordinates through monoplotting based on the automatically estimated camera parameters the achievable accuracy of the checkpoints could be estimated.

In Fig. 8 the errors of the monoplotted checkpoints are represented by their quartiles, further separated into the same groups as previously used in Table 3. Using the same distinction allowed to directly relate the accuracy of the estimated camera parameters with the achievable accuracy for monoplotting. Furthermore, the observations are displayed as points over the box plots, revealing the underlying distribution of the data. This showed that even for the manually oriented cameras monoplotting errors in range of few kilometers occur. This was not surprising as for points along ridge lines or horizons even smallest errors in the rotation of the camera led to huge errors as the ray does not intersect the terrain around the true location but extends until it hits the terrain
further away.
The median error was close to 1 m for the reference images as well as the automatically oriented images up to a deviation of 250 m and $2.5^{\circ}$. Besides the median, also the 75th percentile remained below 5 m for these images. Beyond that, both the median and the 75th percentile rapidly increased towards 1 km for those images with deviations above 1 km and $10^{\circ}$. Our assumption based on Table 3, that for this last group of images the automatic orientation completely failed, was further confirmed. For those images with a deviation between ( $250 \mathrm{~m}, 1000 \mathrm{~m}$ ] and $\left(2.5^{\circ}, 10^{\circ}\right]$ the situation was somewhere in between. While their medians were significantly lower with 3 and 15 m compared to this last group, their 75th percentiles were around 1 km .

This analysis showed that up to an deviation of 250 m and $2.5^{\circ}$ from the reference camera, accounting for $63 \%$ of our images, the accuracy achievable for monoplotting was comparable to our manually oriented

![](https://cdn.mathpix.com/cropped/b2797dc5-5edb-4c1d-a16d-821b99d98cb9-11.jpg?height=1181&width=867&top_left_y=191&top_left_x=135)
Fig. 10. Selected images where the automatic image orientation completely failed. Top: Close up of a glaciated rock wall. The glacier has melted by now, vastly changing the shape of the horizon. Bottom: Horizon is partly covered by fog. Apparent image horizon in the left image part does not correspond to the true horizon. Both images: © Franco Secchieri.

reference images and also to the accuracies reported in Bayr (2021); Stockdale et al. (2015). Hence, these images could be directly used for any subsequent spatial analysis. Selected successfully oriented images are shown in Fig. 9 alongside renderings of the DTM based on the estimated camera parameters. Beyond these limits, the accuracy was not sufficient anymore. The results for these image could still be useful, except for $15 \%$ of the images where our method completely failed. Manually orienting these 204 reference images showed that the most time consuming step in the manual orientation of historical terrestrial images includes finding the initial camera position and identifying the first GCPs. With the achieved results this step can be replaced in $85 \%$ of the cases with the results of the automatic orientation, significantly reducing the required time for orienting whole image collections.

### 4.4. Failures

The last column of Table 3 contains the percentage of images where our method completely failed. Analyzing these images revealed two common cases: i) Image horizons partly covered by clouds and ii) close ups of rock walls (Fig. 10). In the first case, smaller clouds covering parts of the image horizon led to a complete failure of the automatic orientation. Furthermore, for some images the true image horizon was completely covered by fog, which was not apparent beforehand. The second group of falsely oriented images were close ups of rock walls with partly overhanging glacier structures. The horizons in these images had little or no variation, making them poor horizons for matching.

Furthermore, some of these rock walls had glaciated parts, completely vanished by now. Accordingly, the terrain horizon and the image horizon did not correspond any longer.

These cases clearly demonstrate the limits of our approach. If the image horizon was not or only partly visible or its shape had largely changed due to e.g. retreating glaciers, our approach completely failed. But also for those images where we achieved good results the sole dependence on the image horizon has its drawbacks. As the distribution of the HGCPs, extracted from the horizon, in the image and object space is far from ideal, an increased monoplotting error can be observed in the close range of the camera, corresponding to the lower image half. These errors partly explain the increased 75th percentiles for those images having a deviation between $(100 \mathrm{~m}, 500 \mathrm{~m}]$ in Fig. 8. Hence, to overcome this dependency and increase the overall accuracy of our approach the inclusion of ridge lines, stable features similar to image horizons, will be necessary. These are visually highlighted in the renderings of the terrain in Fig. 9. By incorporating these features, a better distribution of HGCPs both in the image and object space may be achieved, improving the accuracy of the automatic orientation method. Unfortunately, the detection of ridge lines in images is quite challenging and has not been approached yet.

## 5. Conclusion

A method for the automatic orientation of historical terrestrial images based on the visible horizon was proposed. As the scenery captured in historical images of mountain regions is subject of vast changes, the horizon was selected as stable feature over time. By matching the image horizon parts with terrain horizon parts, a list of potential candidates was obtained for each query image. In a subsequent spatial resection, based on prominent points extracted along the horizon, these candidates were further refined. By incorporating the height above ground into the selection of the best solution, the accuracy of our method could be significantly improved: $40 \%$ of the 204 investigated images were positioned within 100 m of the true position having an azimuth deviation less than $1^{\circ}$. The true orientation was computed manually using 2400 hand picked GCPs. Furthermore, the unknown focal length could be estimated within an relative error of $5 \%$ in $75 \%$ of the images. By using these 2400 manually selected GCPs as checkpoints, we further showed that for $63 \%$ of the images the monoplotting accuracy is comparable to the manually oriented images. In $22 \%$ of the images the achieved accuaracy does not suffice for monoplotting and in $15 \%$ our method completely failed. The presented approach still opens up the possibility to exploit larger historical image collections. One of the biggest problems of orienting historical terrestrial images is the identification of the initial position and orientation of the camera due to the vast changes of the captured scenery and its complex topography. As soon as the initial parameters are found, the further refinement using additional GCPs is often trivial. Based on the achieved results, for $85 \%$ of the images this time consuming step can be replaced using our proposed automatic orientation method.

## Code availability

We implemented our approach in Python 3 and provide the code on GitHub: https://github.com/smfloery/auterior. The automatic orientation of one image takes around 45 s on a multi-core CPU with 3.7 GHz and 32 GB of RAM.

## Funding

This work is part of the SEHAG project (project number I 4062) funded by the Austrian Science Fund (FWF).

## Declaration of competing interest

The authors declare that they have no known competing financial
interests or personal relationships that could have appeared to influence the work reported in this paper.

## Acknowledgement

We would like to thank the Archive of the Austrian Alpine Club (ÖAV, Innsbruck), Archive of the German Alpine Club (DAV, Munich), Moritz Altmann and Franco Secchieri for providing the images used within this work.

## References

Baatz, G., Saurer, O., Köser, K., Pollefeys, M., 2012. In: Large Scale Visual GeoLocalization of Images in Mountainous Terrain, vol. 7573. https://doi.org/10.1007/ 978-3-642-33709-3_37.
Bayr, U., 2021. Quantifying historical landscape change with repeat photography: an accuracy assessment of geospatial data obtained through monoplotting. Int. J. Geogr. Inf. Sci. 35, 1-21. https://doi.org/10.1080/13658816.2021.1871910.
Besl, P.J., McKay, N.D., 1992. Method for registration of 3-D shapes. In: Sensor Fusion IV: Control Paradigms and Data Structures, pp. 586-606. https://doi.org/10.1117/ 12.57955. SPIE.

Bozzini, C., Conedera, M., Krebs, P., 2012. A new monoplotting tool to extract georeferenced vector data and orthorectified raster data from oblique non-metric photographs. Int. J. Heritage Digital Era 1, 499-518. https://doi.org/10.1260/20474970.1.3.499.

Bresenham, J.E., 1965. Algorithm for computer control of a digital plotter. IBM Syst. J. 4, 25-30. https://doi.org/10.1147/sj.41.0025.
Conedera, M., Bozzini, C., Ueli, R., Thalia, B., Patrik, K., 2018. Using the Monoplotting Technique for Documenting and Analyzing Natural Hazard Events. https://doi.org/ 10.5772/intechopen.77321.

Fischler, M.A., Bolles, R.C., 1981. Random sample consensus: a paradigm for model fitting with applications to image analysis and automated cartography. Commun. ACM 24, 381-395. https://doi.org/10.1145/358669.358692.
Gao, X.S., Hou, X.R., Tang, J., Cheng, H.F., 2003. Complete solution classification for the perspective-three-point problem. Pattern analysis and machine intelligence. IEEE Transactions on 25, 930-943. https://doi.org/10.1109/TPAMI.2003.1217599.
Kraus, K., 2012. Photogrammetrie: Geometrische Informationen aus Photographien und Laserscanneraufnahmen. Walter de Gruyter.

Liu, L., Li, H., Dai, Y., 2017. Efficient global 2D-3D matching for camera localization in a large-scale 3D map. In: Proceedings of the IEEE International Conference on Computer Vision, pp. 2372-2381.
McCaffrey, D., Hopkinson, C., 2020. Repeat oblique photography shows terrain and fireexposure controls on century-scale canopy cover change in the alpine treeline Ecotone. Rem. Sens. 12, 1569. https://doi.org/10.3390/rs12101569.
Naval, P., Mukunoki, M., Minoh, M., Ikeda, K., 1997. Estimating Camera Position and Orientation from Geographical Map and Mountain Image.
Nogués-Bravo, D., Araújo, M.B., Errea, M.P., Martínez-Rica, J.P., 2007. Exposure of global mountain systems to climate warming during the 21st Century. Global Environ. Change 17, 420-428. https://doi.org/10.1016/j.gloenvcha.2006.11.007.
Pan, Z., Tang, J., Tjahjadi, T., Xiao, X., Wu, Z., 2020. Camera geolocation using digital elevation models in hilly area. Appl. Sci. 10, 6661. https://doi.org/10.3390/ app10196661.
Sarlin, P.E., Cadena, C., Siegwart, R., Dymczyk, M., 2019. From coarse to fine: robust hierarchical localization at large scale. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, pp. 12716-12725.
Sattler, T., Leibe, B., Kobbelt, L., 2011. Fast image-based localization using direct 2D-to3D matching. In: 2011 International Conference on Computer Vision, pp. 667-674. https://doi.org/10.1109/ICCV.2011.6126302.
Sattler, T., Sweeney, C., Pollefeys, M., 2014. In: On Sampling Focal Length Values to Solve the Absolute Pose Problem. https://doi.org/10.1007/978-3-319-10593-2_54.
Scapozza, C., Lambiel, C., Bozzini, C., Mari, S., Conedera, M., 2014. Assessing the rock glacier kinematics on three different time scales: a case study from the Southern Swiss Alps. Earth Surf. Process. Landforms 39. https://doi.org/10.1002/esp.3599.
Stockdale, C.A., Bozzini, C., Macdonald, S.E., Higgs, E., 2015. Extracting ecological information from oblique angle terrestrial landscape photographs: performance evaluation of the WSL Monoplotting Tool. Appl. Geogr. 63, 315-325. https://doi. org/10.1016/j.apgeog.2015.07.012.
Tang, J., Gong, C., Guo, F., Yang, Z., Wu, Z., 2022. Automatic geo-localization framework without GNSS data. IET Image Process. 16, 2180-2195. https://doi.org/10.1049/ ipr2.12482.
Tomešek, J., Cadík, M., Brejcha, J., 2022. CrossLocate: cross-modal large-scale visual geo-localization in natural environments using rendered modalities. In: 2022 IEEE/ CVF Winter Conference on Applications of Computer Vision. WACV), pp. 2193-2202. https://doi.org/10.1109/WACV51458.2022.00225.
Wang, J., Bai, X., You, X., Liu, W., Latecki, L.J., 2012. Shape matching and classification using height functions. Pattern Recogn. Lett. 33, 134-143. https://doi.org/10.1016/ j.patrec.2011.09.042.

Yang, C., Yu, Q., 2021. Invariant multiscale triangle feature for shape recognition. Appl. Math. Comput. 403, 126096 https://doi.org/10.1016/j.amc.2021.126096.


[^0]:    * Corresponding author.

    E-mail address: sebastian.floery@geo.tuwien.ac.at (S. Mikolka-Flöry).
    https://doi.org/10.1016/j.ophoto.2022.100026
    Received 24 August 2022; Received in revised form 31 October 2022; Accepted 1 November 2022
    Available online 11 November 2022
    2667-3932/© 2022 The Authors. Published by Elsevier B.V. on behalf of International Society of Photogrammetry and Remote Sensing (isprs). This is an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/).

