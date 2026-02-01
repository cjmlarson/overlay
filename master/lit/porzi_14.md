## TUTORIAL

## Citation in BibTeX format

## Learning Contours for Automatic Annotations of Mountains Pictures on a Smartphone

ICDSC '14: International Conference on Distributed Smart Cameras
November 4-7, 2014
Venezia Mestre, Italy

## Conference Sponsors:

SIGBED

## LORENZO PORZI, University of Perugia, Perugia, PG, Italy SAMUEL ROTA BULÓ, Bruno Kessler Foundation, Trento, TN, Italy <br> PAOLO VALIGI, University of Perugia, Perugia, PG, Italy <br> OSWALD LANZ, Bruno Kessler Foundation, Trento, TN, Italy <br> ELISA RICCI, University of Perugia, Perugia, PG, Italy

Open Access Support provided by:
University of Perugia

## Bruno Kessler Foundation

# Learning Contours for Automatic Annotations of Mountains Pictures on a Smartphone 

Lorenzo Porzi<br>Fondazione Bruno Kessler Trento, Italy

University of Perugia
Perugia, Italy

Samuel Rota Buló<br>Fondazione Bruno Kessler Trento, Italy

Paolo Valigi<br>University of Perugia Perugia, Italy

Oswald Lanz<br>Fondazione Bruno Kessler<br>Trento, Italy

Elisa Ricci<br>Fondazione Bruno Kessler<br>Trento, Italy

University of Perugia<br>Perugia, Italy


#### Abstract

In the last few years the ubiquity and computational power of modern smartphones, together with the significant progresses made on wireless broadband technologies, have made Augmented Reality (AR) technically feasible in consumer devices. In this paper we present an AR application for mobile phones to augment pictures of mountainous landscapes with geo-referenced data (e.g. the peaks' names, positions of mountain dews or hiking tracks). Our application is based on a novel approach for image-to-world registration, which exploits different information collected with on-board sensors. First, GPS and inertial sensors are used to compute a rough estimate of device position and orientation, then visual cues are exploited to refine it. Specifically, a new learning-based contour detection method based on Random Ferns is used to extract visible mountain profiles from a picture, which are then aligned to synthetic ones obtained from Digital Elevation Models. This solution guarantees an increased accuracy with respect to previous works based only on sensors or on standard edge detection and filtering algorithms. An experimental evaluation conducted on a large set of manually aligned photographs demonstrates that the proposed registration method is both accurate in reconstructing camera position and orientation, and computationally efficient when implemented on a smartphone.


## Categories and Subject Descriptors

H.5.1 [Multimedia Information Systems]: Artificial, augmented, and virtual realities

## Keywords

Augmented reality, inertial sensors, image annotation.

## 1. INTRODUCTION

Augmented Reality technologies allow for a digitally enhanced view of the real world. AR applications are many

[^0]![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-2.jpg?height=512&width=678&top_left_y=769&top_left_x=1170)
Figure 1: Output of the proposed system: the photo is annotated with the names of notable peaks. Synthetic profiles from DEM are superimposed (image best viewed at magnification).

and encompass different areas such as tourism (e.g. superimposing descriptions of monuments on buildings facades), entertainment (e.g. inserting characters into real scenes for gaming), civil engineering and construction (e.g. visualizing technical layouts and infrastructure information) or medicine (e.g. providing assistance to surgeons during operations). Many AR applications rely on publicly available archives of geographic referenced data (e.g. geo-referenced photo collections, geoscience data). For example, in [6] an AR approach is proposed where geo-data are exploited to label mountains in a picture, by reporting their heights above the sea level and their distances from the camera. In [13] an AR system for visualizing geo-located wine-growing data is presented. These systems work well, i.e. labels or markers are accurately and precisely superimposed to the associated objects in the pictures, but they operate "offline" as they typically rely on computationally expensive processes or human feedback. Thus, they are not appropriate to be implemented into mobile devices.

Recently, the large diffusion of smartphones and tablets equipped with on-board GPS, inertial sensors and with increased processing power, has enabled AR systems to run entirely on mobile devices in real-time. However, many current systems only make use of embedded sensors to estimate the device pose and position. This is practically insufficient in most AR applications, which need a precise and solid registration between the real scene and the synthetic representation of the world. In fact, an accurate registration
is essential to exactly label points of interest into a visual scene.

In this paper we present an AR system for the automatic annotation of pictures of mountainous landscapes, which runs on a mobile phone. Typical examples of augmented contents include notable landmarks, mountain peaks, hiking trails, names of dews, positions of other users, etc. Figure 1 provides an example of the output of our system: a picture taken by a smartphone where mountains' peaks are labeled with their names. Our system relies on a novel approach for robust registration between the real scene and a synthetic representation of the world, i.e. profiles automatically generated from Digital Elevation Models (DEM). Our method starts with a rough estimate of the orientation and position of the device that is computed by processing data from on board sensors, i.e. GPS, magnetometer, gyroscope and accelerometer. This estimate is then refined by means of a novel alignment algorithm that exploits visual information. Similarly to [4, 6], our algorithm matches edges extracted from the given image against synthetic profiles, guided by a scoring function supporting the best alignment. However, motivated by the need of devising a computationally efficient approach suitable for mobile devices, we depart from [4,6] by adopting a very simple and fast scoring function and devise a more sophisticated, learning-based edge detection approach. By doing so, we prevent the occurrence of many spurious edges, thus lightening the subsequent alignment process. Once the photo-to-world registration procedure is completed, virtual content is rendered and overlaid on the real scene. The user can then explore the augmented picture using the touch gestures commonly employed in smartphone interfaces (e.g. pinch-to-zoom).

A main contribution of this paper, inspired by recent works in computer vision [9, 10], consists in casting the problem of contour detection as a classification problem. This is motivated by out interest in locating mountain profiles instead of detecting edges indiscriminately. Specifically, we propose to use Random Ferns [15] as a simple and efficient way to detect pixels corresponding to mountain profiles, according to visual features extracted from their neighborhood. Standard edge detectors, such as Canny [5] and Compass [20], treat image edges equally regardless of their context. However, the edges of a specific object (i.e. mountains) have the characteristic local color or texture of that object on one side. A learning-based approach, oppositely to standard algorithms, is able to capture this information, filtering out spurious edges corresponding to other objects (e.g. manmade structures). This intuition is confirmed by the experimental evaluation conducted on a dataset of thousands of manually annotated pictures, where we show that our algorithm yields accurate registrations, while being fast enough to be implemented on a mobile phone.

This paper is organized as follows. In Sec. 2 we review related works. Section 3 describes the proposed AR system for annotating mountains pictures with peaks' names. In Sec. 4 the results of our experimental evaluation are provided while in Sec. 5 conclusions are drawn.

## 2. RELATED WORKS

Several mobile applications exist with a work-flow that is comparable to the one of our system (picture acquisition, offline processing, interaction), although being focused on different tasks. Notably, the Google Camera App shipped
with recent versions of the Android mobile OS offers three modes of operation that, similarly to our system, exploit inertial sensors and vision: Photo Sphere [1], Panorama and Lens Blur [2]. In the first two modes, the user, guided by the phone's sensors, takes several pictures of the environment, which are stitched together after an off-line elaboration phase that takes several seconds. The final result can then be navigated using a touch-based interface. The Lens Blur mode applies a "bokeh" effect to a picture by exploiting a second picture of the same subject, taken from a slightly different angle. After an initial elaboration, in which a depth map of the environment is computed, the user can adjust the position of the virtual focus point and export the result.

The specific problem of superimposing contents to pictures of mountainous landscapes has been considered in some previous works $[3,4,6]$. In $[4,6]$, picture-to-world registration is performed by aligning profiles obtained from a virtual panorama rendered using DEM information with an edge map computed on the given image. In [3], no initial estimate is assumed for the user position, thus a radically different approach based on bag-of-words is developed. Our approach, instead, is closer to [4,6], where on-board sensors are employed to roughly estimate the user's location, and where an image-to-profiles matching based on contours is performed. However, conversely to our work, Baboud et al. [4] focused on devising an effective score function to compare synthetic and detected profiles, while employing a standard edge detection method [20]. Moreover, importantly, none of the previous methods [4,6] is efficient enough to be run on a mobile device.

Our approach, differently from the previous ones [3,4,6], does not rely on filtering or standard edge detection algorithms, for contours pixels are found using a learning-based method. This provides significant benefits both in terms of accuracy and computational costs. Learning-based contour detection has been explored in several previous works [9, 10, 18, 19]. Dollar et al. [9] used a boosting-based approach to independently classify each pixel from its surrounding image patch. More recently [10] achieved improved results by employing a Structured Random Forest classifier, which also considers correlations between adjacent output pixels. Ren et al. [19] achieved state-of-the-art results by employing a method based on sparse coding which, however, suffers from high computational cost. Particularly relevant to our work is the method of Prasad et al. [18], which classifies according to different edge classes the pixels already recognized as edges by a Canny edge detector.

## 3. SYSTEM DESCRIPTION

Our system takes as input a photo of a mountainous landscape and augments it with geo-referenced information. To do that, it exploits the information provided by the inertial, magnetic and GPS sensors integrated in the smartphone, together with the DEM of the environment. Moreover, it is designed in a way to minimize network communication, thus being as self-contained as possible, for cellular networks are usually not reliable enough in mountainous environments. Figure 2 shows a block diagram of the proposed AR system which is composed of four main blocks: Contour Detection, 3D Rendering, Registration and Augmentation. All modules are implemented on the smartphone, excepting 3D Rendering that runs on a remote server. This approach restricts network communication to a bare minimum: in the 3D Ren-

![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-4.jpg?height=478&width=1582&top_left_y=180&top_left_x=262)
Figure 2: Schematic representation of the proposed system. Blue and green blocks correspond to operations carried out at run-time, respectively on the mobile device and on a remote server. Orange blocks correspond to the off-line contour detector training phase.

dering block the server receives a pair of GPS coordinates from the phone and uses the DEM data to calculate the synthetic mountain profiles in a $360^{\circ}$ field of view around that location. The profiles are then sent back to the phone, together with a set of relevant geo-referenced items that will be used to augment the photo in the last step of the pipeline.

Initially, the location of the smartphone gathered from the GPS sensor is sent by the device to the remote server, where the 3D Rendering module (see, Sec. 3.2) collects the DEM data and the geo-referenced items. In the meanwhile, the Contour Detection module on the smartphone detects mountain edges in the input image and determines an initial estimate of the viewpoint's orientation from the inertial and magnetic sensors (see, Sec. 3.1). The final orientation is then computed in the Registration module by optimizing a score function in a neighborhood of the initial estimate (see, Sec. 3.3). The score function compares the detected contours with the synthetic profiles received from the remote server, given a candidate camera orientation. Finally, the Augmentation module superimposes on the image the relevant geo-referenced items, i.e. names and altitudes of mountain peaks retrieved from GeoNames ${ }^{1}$. An example of the system's final output, i.e. an image where names are superimposed to mountains peaks, is shown in Fig. 1.

### 3.1 Contour Detection

The Contour Detection block takes as input an image and produces a contour map, which associates every pixel with a probability of being a contour point. In general, an input image will contain many perceptual edges, but only the ones corresponding to discontinuities in the terrain are of interest for our purpose. Standard edge detection techniques are unable to perform this kind of discrimination, thus producing many spurious, irrelevant edges, which often compromise the quality of the subsequent registration step. To fill this semantic gap, we propose to learn by examples which edges are salient for our purpose, thus regarding edge detection as a classification problem. Instead of classifying each pixel of an image as being part of a relevant countour, e.g. as done in [9, 10], we follow an approach similar to [18] by preselecting putative contour edges using an unsupervised, fast edge detector. This results in a computationally efficient solution, for a large portion of pixels will be excluded a priori from the classification, at the expense of a possible loss in the accuracy of the final prediction in the cases when

[^1]relevant countour pixels are not recognized by the baseline edge detector. This is a price we afford, given the relatively low computational power available on a mobile device. It is worth of notice that none of these aforementioned works [9, 10, 18] has addressed the problem of detecting contours of mountains profiles, their emphasis begin focused on other types of objects and natural scenes.

## Random Ferns.

We cast the edge detection problem in terms of a classification problem, in which the input space $\mathcal{X}$ consists of triplets $x=(I, u, v) \in \mathcal{X}$ identifying a pixel at coordinates ( $u, v$ ) in image $I$, and the output space $\mathcal{Y}=\{+1,-1\}^{\mathrm{w} \times \mathrm{w}}$ consists of contour predictions of a $\mathrm{w} \times \mathrm{w}$ patch around pixel ( $u, v$ ). Entries of a patchwise prediction $\mathrm{Y} \in \mathcal{Y}$, denoted by $\mathrm{Y}_{h \ell}$, indicate whether the neighour of $(u, v)$ corresponding to $(h, \ell)$ in the prediction patch is a contour element $\left(\mathrm{Y}_{h \ell}=+1\right)$, or not $\left(\mathrm{Y}_{h \ell}=-1\right)$. Moreover, we denote by $\Psi$ the set of binary features that can be defined on $\mathcal{X}$. Each binary feature is a function $\psi: \mathcal{X} \rightarrow\{0,1\}$ assigning a binary value to samples in $\mathcal{X}$.

The learning-based edge detector that we propose is based on the Random Ferns (RFn) classifier [16]. Random Ferns can be regarded as a semi-naive Bayes classifier, which combines an ensemble of independent predictors called "ferns". A random fern is a vector-valued function $\boldsymbol{f}=\left(f_{1}, \ldots, f_{k}\right)$, each component being a random, binary feature from $\Psi$, i.e. $f_{i} \in \Psi$ for all $i=1, \ldots, \mathrm{k}$. A set $\mathcal{F}=\left\{\boldsymbol{f}^{1}, \ldots, \boldsymbol{f}^{\mathrm{m}}\right\}$ of m random ferns forms a RFn classifier. Training a RFn classifier $\mathcal{F}$ amounts to learning for each single fern $\boldsymbol{f}^{j} \in \mathcal{F}$ a conditional probability distribution of the fern's output given a class label, such that we can evaluate for each $x \in \mathcal{X}$, $\mathrm{Y} \in \mathcal{Y}$ the probability $P\left(\boldsymbol{f}^{j}(x) \mid \mathrm{Y}\right)$. Given this information, the class posterior probability can be derived as

$$
\begin{equation*}
P(\mathrm{Y} \mid x, \mathcal{F}) \propto P(x \mid \mathrm{Y}, \mathcal{F})=\prod_{j=1}^{\mathrm{m}} \prod_{h, \ell=1}^{\mathrm{w}} P\left(\boldsymbol{f}^{j}(x) \mid \mathrm{Y}_{h \ell}\right), \tag{1}
\end{equation*}
$$

where we implicitly assumed uniform prior over $\mathcal{Y}$, conditionally indepedent ferns and independent prediction over the elements of Y.

Given a training set $\mathcal{T}=\left\{\left(x^{s}, \mathrm{Y}^{s}\right\}_{s=1}^{\mathrm{n}} \subseteq \mathcal{X} \times \mathcal{Y}\right.$ consisting of n labelled samples, the conditional probability distribution associated to each fern $\boldsymbol{f}^{j}$ can be learned from the data by means of a maximum-a-posteriori estimate under uniform, independent Dirichlet priors with parameter $\alpha>0$.

This yields the following learning rule:

$$
\begin{equation*}
P\left(\boldsymbol{f}^{j}(x) \mid \mathrm{Y}_{h \ell}\right) \propto \alpha+\sum_{s=1}^{\mathrm{n}} 1_{\left(\boldsymbol{f}^{j}(x), \mathrm{Y}_{h \ell}\right)=\left(\boldsymbol{f}^{j}\left(x^{s}\right), \mathrm{Y}_{h \ell}^{s}\right)}, \tag{2}
\end{equation*}
$$

where 1 is the indicator function giving 1 if the subscript proposition is true, 0 otherwise. The term on the right counts the number of training samples ( $x^{s}, \mathrm{Y}^{s}$ ) having $\mathrm{Y}_{h \ell}^{s}= \mathrm{Y}_{h \ell}$ and feature representation $\boldsymbol{f}^{j}\left(x^{s}\right)=\boldsymbol{f}^{j}(x)$.

## Contour map creation.

Once the RFn classifier has been trained, Equation 1 can be used to build a probabilistic contour map at test time for a novel image $I$. As mentioned in Sec. 3.1, we exploit a baseline edge detector to pre-select putative contour pixels. Specifically, we apply a simple Sobel filter to image $I$ to compute an approximate gradient magnitude for every pixel. Each pixel ( $u, v$ ) exhibiting a magnitude larger than $\tau$ originates a sample $x=(u, v, I)$ that is fed to our trained RFN classifier. This yields predictions for all pixels in a $\mathrm{w} \times \mathrm{w}$ neighbourhood of $(u, v)$. Note that, by adopting this approach, pixels get multiple predictions due to overlapping neighborhoods, which are averaged in the final map.

## Binary features.

The type of binary features that we adopt resemble the ones used in [15], with the important difference that we encode a multi-resolution component, which implicitly allows us to inspect pixel values at different scales. In detail, a random, binary feature $f(\cdot ; \theta) \in \Psi$ is a function parametrized by a tuple $\theta=\left(\delta u_{1}, \delta v_{1}, \delta u_{2}, \delta v_{2}, \sigma, c, \rho\right)$. Given its argument $x=(u, v, I)$, the parameters $\delta u_{1 / 2}, \delta v_{1 / 2} \in[-\mathrm{r}, \mathrm{r}]$ identify the coordinates of two random neighbours of ( $u, v$ ) in image $I$ at coordinates $\left(u+\delta u_{1}, v+\delta v_{1}\right)$ and $\left(u+\delta u_{2}, v+\delta v_{2}\right)$, $\sigma>0$ is a scale value that indicates at which resolution the value of the two neighbour pixels is taken in channel $c$, and $\rho$ is a random threshold, whose range will be specified later. Given such a parametrization, the binary feature is defined as

$$
f(x ; \theta)= \begin{cases}1 & \text { if } I_{c}^{\sigma}\left(u_{1}, v_{1}\right)-I_{c}^{\sigma}\left(u_{2}, v_{2}\right)>\rho  \tag{3}\\ 0 & \text { otherwise }\end{cases}
$$

where we abbreviated the first and second random neighbour by ( $u_{1}, v_{1}$ ) and ( $u_{2}, v_{2}$ ), and denoted by $I_{c}^{\sigma}(u, v)$ the intensity value of pixel ( $u, v$ ) in channel $c$ at scale $\sigma$. Note that to obtain the intensity values at different scale there is no need to pre-compute an image scale pyramid. Indeed, those values can be obtained in constant time given the integral image of $I$ [7]. Finally, the range in which $\rho$ has to be sampled is determined by the maximum and minimum value of the difference in (3) computed with respect to the samples in the training set.

### 3.2 3D Rendering

The 3D Rendering block exploits publicly available elevation data from the CGIAR-CSI [12] dataset and the Viewfinder Panoramas [8] dataset. A ray-casting algorithm, which also takes into account earth curvature and atmospheric refraction, is used to calculate a 2D cylindrical projection of the environment around the viewpoint. The result is a depth map that associates a distance from the observer to every cylindrical coordinate. The mountains profiles are then extracted from this depth map by calculating the gradient
magnitude, applying a threshold and finally performing a simple vectorization procedure on the result.

### 3.3 Registration

The Registration block takes as input the contour map computed by the Contour Detection block, the initial camera orientation estimated from sensor data and a set of profiles received from the server, and produces as output a refined orientation. The mountain profiles are represented as sets $\mathcal{P}=\left\{\mathrm{P}_{1}, \ldots, \mathrm{P}_{T}\right\}$, with $\mathrm{P}_{i}=\left(\mathbf{p}_{i}^{1}, \ldots, \mathbf{p}_{i}^{n_{i}}\right)$. The points $\mathbf{p}_{i}^{j}=\left[\begin{array}{lll}\theta_{i}^{j} & \phi_{i}^{j} & r_{i}^{j}\end{array}\right]$ are expressed in spherical coordinates relative to a world-fixed coordinates frame centered on the user's GPS coordinates. The camera orientation is parameterized with a triplet $\mathbf{x}=\left[\begin{array}{llr}y & p & r\end{array}\right]$ of yaw, pitch and roll angles. We denote as $\operatorname{Proj}(\mathbf{x}, \mathbf{p} ; \mathbf{k})$ the function that, given an orientation $\mathbf{x}$ and the camera intrinsic parameters $\mathbf{k}$, projects the 3D profile point $\mathbf{p}$ on the coordinates $(u, v)$ of the image plane. In this paper we consider a simple pin-hole projection model. Denoting as $\mathbf{x}_{S}=\left[y_{S} p_{S} r_{S}\right]$ the orientation calculated from the smartphone's sensors, we obtain the final orientation estimate by solving:

$$
\begin{array}{cc}
\max _{\mathbf{x}} & \sum_{i=1}^{T} \sum_{j=1}^{n_{i}} d\left(r_{i}^{j}\right) \mathcal{C}\left(\operatorname{Proj}\left(\mathbf{x}, \mathbf{p}_{i}^{j} ; \mathbf{k}\right)\right)  \tag{4}\\
\text { s.t. } & \mathbf{x} \geq \mathbf{x}_{S}-\mathbf{b}_{l} \\
& \mathbf{x} \leq \mathbf{x}_{S}+\mathbf{b}_{u}
\end{array}
$$

where $\mathbf{b}_{l}$ and $\mathbf{b}_{u}$ define respectively a lower and an upper bound to a search space centered around $\mathbf{x}_{S}$ and $d\left(r_{i}^{j}\right)$ is a function of the distance of the profile point from the observer. The objective of $d(\cdot)$ is that of giving more importance to distant profiles, as the accuracy of the DEM increases when the distance from the viewpoint increases. In our current implementation $d(\cdot)$ is a step function that weights 1 the points beyond a predefined distance and 0 the others. However, other weighting schemes are possible as well. We observe that the objective function of (4) is highly non linear, has many local maxima and is pretty expensive to compute. For these reasons we chose to solve (4) using a stochastic optimization algorithm. In particular, we adopt the Accelerated Particle Swarm Optimization in [21].

## 4. EXPERIMENTAL RESULTS

In our experiments we consider two different datasets: one is used to test the performance of the proposed algorithm, the other for training. As described in Sec.3, the dataset used for training comprises 100 images taken from 100 different locations in the Alps downloaded from Flickr ${ }^{2}$. The test set consists of 12 outdoors sequences recorded from several locations in the Alps. Each sequence has been captured using a Sony Ericsson XPERIA Z smartphone, and comprises between 150 and 500 frames with a resolution of $640 \times 480$ pixels, for a total of 3117 images, together with a dump of the phone's sensors and GPS coordinates. We manually aligned all images in both datasets to the DEM to derive their absolute orientation, then, using the algorithms described in Sec. 3.2, we projected a set of synthetic mountain profiles onto each image plane. Finally, for the images in the training set, we labeled each pixel lying on a profile as "contour" and every other pixel as "not-contour".

In the next paragraphs, if not otherwise noted, we consider the following fixed parameter values for RFN: $\mathrm{r}=8, \mathrm{k}=12$.

[^2]![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-6.jpg?height=326&width=1454&top_left_y=214&top_left_x=330)
Figure 3: Comparison of different approaches according to (left) registration error and (right) running time.

Table 1: Comparison of different approaches for contour detection.
| Methods | Average error (degrees) |  |  |  |  |  |  |  |  |  |  |  |  |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
|  | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | Avg. |
| Canny [6] | 1.74 | 16.04 | 1.42 | 1.52 | 3.36 | 5.41 | 16.92 | 1.77 | 1.10 | 2.55 | 2.95 | 0.89 | 4.64 |
| Compass [4] | 0.37 | 15.44 | 0.70 | 0.20 | 0.53 | 2.71 | 22.79 | 1.66 | 0.11 | 1.12 | 0.38 | 0.19 | 3.85 |
| Structured Output Random Forest [10] | 0.37 | 0.25 | 0.23 | 0.22 | 0.43 | 3.88 | 1.06 | 0.48 | 0.24 | 1.13 | 0.53 | 0.22 | 0.76 |
| RFn, $\mathrm{w}=4, \tau=0.1, \mathrm{~m}=100$ | 0.30 | 4.25 | 0.25 | 0.24 | 0.30 | 3.65 | 5.22 | 0.42 | 0.12 | 0.92 | 0.48 | 0.26 | 1.87 |


In the first series of experiments we evaluate the performance of the proposed system, analyzing the impact of different contour detection algorithms on both registration accuracy and computational times. Specifically, we consider the proposed RFN approach analyzing the influence of the threshold $\tau$ and the number of ferns $m$ while fixing $\mathrm{w}=4$. We compare RFN with a standard edge detector (i.e. Canny [5]) that was also used for registering mountains pictures in previous works [6]. As a baseline we also show the results obtained using sensor-based orientation estimation, i.e. without exploiting visual cues. Figure 3 compares the different approaches showing the average registration error (Fig. 3, left) and the computational times (Fig. 3, right) when they run on a Sony XPERIA Z smartphone. As expected we achieve close to real-time performance when using only the sensors or the Canny edge detector, but the resulting registration accuracy is generally insufficient for an AR application (average error greater than $5^{\circ}$ ). Our RFn approach, on the other side, guarantees a significantly lower registration error ( $\sim 1.3^{\circ}$ for some choice of parameters). In this case the associated computational time is in the order of a few seconds, which is reasonable for our application. From the results shown in Fig. 3 we can also observe the influence of different parameters: $\mathrm{m}=100$ ferns and a threshold $\tau=0.2$ seem to be the values of choice according to a trade-off between registration error and running time (small values of $\tau$ and large values of $m$ increase the running time).

The influence of the Sobel threshold $\tau$ and the output patch size w is further investigated in Fig. 6, which shows the registration error for our RFn approach when $\mathrm{m}=100$. Generally, increasing $\tau$ the registration accuracy degrades as expected. Setting $\mathbf{w}=4$ or $\mathbf{w}=8$ guarantees superior accuracy with respect to $\mathrm{w}=1$, as a wider output patch leads to a smoother and less noisy edge map.

In a second series of experiments we compare two learningbased and two standard contour detectors. In particular we consider: the proposed RFn, the Random Forest classifier with structured output in [10], the Canny [5] edge detector and the Compass [20] edge detector. Both Canny and Compass have been adopted in previous works [6, 4] for registering pictures of mountainous terrains. Table 1 shows the mean registration error for the 12 test sequences when using these different approaches. The advantage of employing a learning-based contour detection algorithm is evident,
as Canny and Compass are consistently outperformed by our RFn method and by the Random Forest classifier. In most sequences the Random Forest classifier gives the best results: this is somehow expected as its output is generally smoother and less noisy compared to the other contour detectors. However, this approach and in general any structured output classifier typically relies on a complex inference algorithm which is too computationally expensive to run on a mobile device. Similarly, the Compass detector produces a more accurate edge map than Canny, but its high computation complexity makes it unsuitable for our application.

It is worth noting that the estimation error for the proposed methods varies significantly among different sequences. For instance, the first two images of Fig. 4 correspond to the system output on the first frame of sequence 12 when Canny and RFn are used as contour detectors. In this case we observe a small alignment error for both detectors (resp. $\sim 0.9^{\circ}$ and $\sim 0.3^{\circ}$ ), which translates to an accurate augmentation. The last two images of Fig. 4 show the system output for the first frame of sequence 2 and the same contour detectors. Here RFn produces an error of $\sim 4^{\circ}$ resulting in an inaccurate but still intelligible augmentation, while Canny produces an error of $\sim 16^{\circ}$ which is not acceptable for our application. In general RFN produces significantly better results than traditional approaches such as Canny or Compass in all those cases where the scene is highly cluttered or presents spurious edges. Our approach, in fact, is able to discard many edges that are not due to mountain profiles, as it is evident from Fig. 5.

## 5. CONCLUSIONS

We presented an AR application for annotating mountain pictures running on a mobile phone. Our system is based on a novel approach for photo-to-world registration which jointly exploits information provided by GPS, inertial sensors and visual cues. Our experiments on a large dataset of manually annotated photographs clearly demonstrate that our registration method guarantees robust orientation estimates and thus precise content augmentation. Future works will explore other approaches based on structured output learning for contour detection [14], novel optimization solutions for improving computational efficiency and how to integrate this algorithm into an ego-motion estimation framework [17] selecting adaptively discriminative features [11].

![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-7.jpg?height=285&width=1490&top_left_y=182&top_left_x=309)
Figure 4: System output for the first frames of sequences 1 and 2 when using $\operatorname{RFn}(A, D)$ and $\operatorname{Canny}(B, C)$.

![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-7.jpg?height=289&width=1494&top_left_y=541&top_left_x=305)
Figure 5: First frame of sequence 5 (A) and contour maps obtained with the Canny (B), Compass (C) and our approach (D).

![](https://cdn.mathpix.com/cropped/c0373a2e-0833-4843-a2d3-59c2bf6bac76-7.jpg?height=486&width=520&top_left_y=937&top_left_x=336)
Figure 6: Registration errors obtained with our approach at varying values of the patch size w and the threshold $\tau$.

## 6. ACKNOWLEDGMENTS

This research has been partly funded by the European 7th Framework Program, under grant VENTURI (FP7-288238).

## 7. REFERENCES

[1] Google photo sphere. http://www.google.com/maps/ about/contribute/photosphere/.
[2] Lens blur in the new google camera app. http://googleresearch.blogspot.it/2014/04/ lens-blur-in-new-google-camera-app.html.
[3] G. Baatz, O. Saurer, K. Köser, and M. Pollefeys. Large scale visual geo-localization of images in mountainous terrain. In ECCV. 2012.
[4] L. Baboud, M. Cadík, E. Eisemann, and H.-P. Seidel. Automatic photo-to-terrain alignment for the annotation of mountain pictures. In CVPR, 2011.
[5] J. Canny. A computational approach to edge detection. IEEE Trans. on PAMI, 1986.
[6] P. Chippendale, M. Zanin, and C. Andreatta. Spatial and temporal attractiveness analysis through geo-referenced photo alignment. In IGARSS, 2008.
[7] F. C. Crow. Summed-area tables for texture mapping. In ACM SIGGRAPH Computer Graphics, 1984.
[8] J. de Ferranti. Viewfinder panoramas digital elevation
data.
http://www.viewfinderpanoramas.org/dem3.html.
[9] P. Dollár, Z. Tu, and S. Belongie. Supervised learning of edges and object boundaries. In CVPR, 2006.
[10] P. Dollár and C. L. Zitnick. Structured forests for fast edge detection. ICCV, 2013.
[11] S. Duffner, J.-M. Odobez, and E. Ricci. Dynamic partitioned sampling for tracking with discriminative features. In BMVC, 2009.
[12] A. Jarvis, H. Reuter, A. Nelson, and E. Guevara. Hole-filled seamless srtm data v4. http://srtm.csi.cgiar.org.
[13] G. R. King, W. Piekarski, and B. H. Thomas. Arvino-outdoor augmented reality visualisation of viticulture gis data. In Mixed and Augmented Reality. IEEE and ACM Int. Symp. on, 2005.
[14] P. Kontschieder, S. Rota Bulo, M. Pelillo, and H. Bischof. Structured labels in random forests for semantic labelling and object detection. IEEE Trans. on PAMI, (99):1-1, 2014.
[15] M. Ozuysal, M. Calonder, V. Lepetit, and P. Fua. Fast keypoint recognition using random ferns. PAMI, 2010.
[16] M. Ozuysal, P. Fua, and V. Lepetit. Fast keypoint recognition in ten lines of code. In CVPR, 2007.
[17] L. Porzi, E. Ricci, T. A. Ciarfuglia, and M. Zanin. Visual-inertial tracking on android for augmented reality applications. In EESMS, 2012.
[18] M. Prasad, A. Zisserman, A. Fitzgibbon, M. P. Kumar, and P. H. Torr. Learning class-specific edges for object detection and segmentation. In Computer Vision, Graphics and Image Processing. Springer, 2006.
[19] X. Ren and L. Bo. Discriminatively trained sparse code gradients for contour detection. In NIPS, 2012.
[20] M. A. Ruzon and C. Tomasi. Color edge detection with the compass operator. In CVPR, 1999.
[21] X.-S. Yang, S. Deb, and S. Fong. Accelerated particle swarm optimization and support vector machine for business optimization and applications. In Networked digital technologies. Springer, 2011.


[^0]:    Permission to make digital or hard copies of all or part of this work for personal or classroom use is granted without fee provided that copies are not made or distributed for profit or commercial advantage and that copies bear this notice and the full citation on the first page. To copy otherwise, to republish, to post on servers or to redistribute to lists, requires prior specific permission and/or a fee.
    ICDSC'14, November 04-07 2014, Venezia Mestre, Italy
    Copyright 2014 ACM 978-1-4503-2925-5/14/11
    http://dx.doi.org/10.1145/2659021.2659046 ...\$15.00.

[^1]:    ${ }^{1}$ http://www.geonames.org

[^2]:    ${ }^{2}$ https://www.flickr.com/

