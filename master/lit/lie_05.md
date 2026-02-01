# A robust dynamic programming algorithm to extract skyline in images for navigation 

Wen-Nung Lie ${ }^{\mathrm{a}, *}$, Tom C.-I. Lin ${ }^{\mathrm{a}}$, Ting-Chih Lin ${ }^{\mathrm{a}}$, Keng-Shen Hung ${ }^{\mathrm{b}}$<br>${ }^{\mathrm{a}}$ Department of Electrical Engineering, National Chung Cheng University, 160 San-Hsing, Min-Hsiung, Chia-Yi 621, Taiwan, ROC<br>${ }^{\mathrm{b}}$ Chung-Shan Institute of Science and Technology, Lung-Tan, Tao-Yuan 325, Taiwan, ROC

Received 21 August 2004
Available online 14 October 2004


#### Abstract

In this paper, a skyline image detection algorithm is proposed for navigation of mobile vehicles or planes in mountainous environments. First, edge detection and subsequent binary thresholding are applied on the luminance component to obtain the edge map, from which a multi-stage graph is constructed for determining the skyline curve by using the dynamic programming (DP) algorithm. In optimal DP search, characteristics (e.g., preferred position and orientation) of the skyline are utilized to help in correct linking of curves. The tolerance in short breakage of skyline curve is considered for robustness consideration. Experiments show that the processing speed is fast (approximately $0.12-0.21 \mathrm{~s}$ for a $352 \times 240$ pixel image on a Pentium-M 1.3 GHz CPU) and promising for real-time applications.


© 2004 Elsevier B.V. All rights reserved.

Keywords: Dynamic programming; Skyline extraction; Edge/contour linking

## 1. Introduction

This paper is to discuss a robust algorithm to extract the skyline in mountainous images for navigation of mobile vehicles or planes. The position estimation problem has received considerable attention in the fields of computer vision and robot navigation in the indoor environment case. Often,

[^0]artificial landmarks (e.g., Kabuka and Arenas (1987)) or ceiling corners were sensed and recognized by a vision system to determine the position and orientation of the robot itself. On the other hand, natural landmarks such as road edges (e.g., Yang and Ozawa (1996) and Kim et al. (2003)), trees, or buildings were used for outdoor navigation. The position estimation problem becomes more complicated in an unstructured environment, such as the mountainous area dealt with in Suh et al.'s work (1993) and this paper. In this case, no distinct landmarks are available. Nevertheless,
the skyline represents silhouettes of terrain objects against the sky. The skyline of each instance in an image sequence can serve as the natural landmark or reference feature which can be detected by a vision sensor and matched with those pre-stored in database to determine the accurate vehicle position (e.g., Fang et al. (1993), Suh et al. (1993) and Talluri et al. (1990)). In this way, it is unnecessary to build artificial landmarks and have the knowledge of their approximate locations in advance. Nor does it need to structure the environment model for position matching. Only video images of mountainous scenes have to be recorded to construct the skyline database (others adopted the digital elevation model (DEM) (e.g., Talluri et al., 1990) in database, which can also be used to derive the skyline). Whenever the environment changes, a newly captured video sequence is needed to update the database without much effort.

Skyline can also be used in other applications, such as rendering cartographic data, rendering self-shadowing textures, accelerating flight simulation, visualizing scientific data, path planning to avoid detection, etc. (e.g., Stewart, 1998). For example, in flight simulation, horizon or skyline can be used to determine which parts of the terrain are visible from the current viewpoint for rendering, since rendering invisible parts is wasteful and potentially time consuming. On the other hand, skylines between consecutive images can be matched for video stabilization (like the stabilizer in digital video camcorder), which is much helpful when the vehicle moves on an outdoor rugged ground.

Extracting the skyline in outdoor images is similar to a segmentation problem which partitions the image into the sky and non-sky areas. Most of the researches addressed above either assumed that the skylines are given (e.g., in Suh et al.'s work, 1993) or applied a very simple method (e.g., Fang et al. (1993) and Talluri et al. (1990)). In (Fang et al.'s work, 1993), an intensity thresholding technique was adopted and the threshold for the skyline was determined using the maximum average intensity within 10 sub-windows and the contrast of the whole image. The skyline pixels were determined by searching each image column from top to bottom for the first pixel position
whose intensity is below the threshold value. Their method is generally not robust (e.g., may fail for images with cloudy or cluttered sky), but also cannot guarantee the contiguity of the skyline due to independent search between adjacent columns. While in the work of Talluri and Aggarwal (1990), they applied a gradient operator on synthetic images (generated by using the AT\&T Pixel Machine from the DEM) to extract the horizon line, the sky in their images is obviously clear and easy for image processing.

Normally, the skyline is characterized of a curve which: (1) is composed of edge points that separate the terrain objects and the sky, (2) locates at the upper part of the image and extends from one side to the opposite side of the image boundary. However, a weak skyline may exist, due to low contrast or clutter between the terrain and the sky. In this paper, a skyline search algorithm is proposed, based on the dynamic programming (DP) technique.

The DP algorithm has been widely used to solve problems in the areas of edge/boundary following (Ballard and Brown, 1982). In Kim et al.'s work (2003), the CNN (Cellular Neural Networks)based DP approach was used to find the globally optimal road boundary line for automatic vehicle driving, based on the detected edge map. Some arrangements, e.g., the provision of goal/start lines at the upper and bottom parts of the image, were required. Merlet and Zerubia (1996) proposed extending the $F^{*}$ algorithm for the DP problem to extract lines (roads, ridges, valleys or canals) in satellite images. They dealt with the definition of cost function by aggregating local features, such as the gray-level, contrast, and curvature. Advantages of their algorithm include: a complete absence of any thresholds or control parameters, and concurrent edge detection and contour grouping. The DP algorithm was also widely used in medical image processing. For example, Geiger et al. (1995) used the DP method in the detection, tracking, and matching of deformable objects. Other examples can also be seen in Lee et al.'s work (2001). They defined a goal to finding a globally optimal contour/edge with connectedness and closeness and found that the DP method is indeed useful in achieving the goal.

Our skyline curve detection problem differs from the above mentioned in the following aspects:
(1) Their problems to be solved are much more general (e.g., lines/curves can be of any orientations and can be arbitrarily closed or open), while our skyline is defined to be an open curve and extend from one side to the other side.
(2) Their method may need information provided by the user (e.g., an initial curve surrounding the object boundary) to limit the search space for optimization. Even so, the DP algorithm is generally slow and requires large memory.
(3) Their DP algorithms operate on the gray-level space and embed the edge detection step in the linking optimization process.

For vehicle/plane navigation purpose, image processing must be completed in high frame rate. Most of the above algorithms suffered from this limitation. The strategy we adopted is to separate edge detection from curve formation process and the DP algorithm is applied on the binary space. Since edge detection is easily achievable by using ASIC/DSP hardware, the only problem left is to find the skyline in a robust and efficient way.

In this paper, our proposed DP-based method will produce a correct and contiguous skyline curve even for cloudy or noisy sky. The processing speed is fast and promising for real-time vehicle navigation.

## 2. Proposed algorithm for skyline extraction

There are basically two approaches to skyline extraction: one is region-growing-based and the other is edge-based. Since the sky often occupies the upper part of an image, the first image row
can be selected as the wave-fronts that propagate downwards until the skyline boundaries are met. The approach proposed in Fang's work (1993) belongs to this kind and has the drawback of weak robustness once clear clouds are present above the skyline. The edge-based approach takes advantage of the fact that humans recognize skyline by perceiving contiguous boundaries between two distinctive regions. The key points come from humans' superior capability in strong detection of edge points and robust linking of them to form a contiguous curve. In this paper, we adopt the edge-based approach, whose flow of processing is illustrated in Fig. 1.

The step of edge detection can be easily implemented by a well-known edge detector, e.g., the Sobel, Canny, or Marr-Hildreth operator. Edge thresholding is to extract pixels that have significant edge responses by setting a threshold. The method is principally similar to those developed for the well-known gray-level thresholding. Traditional algorithms may evaluate the behavior of gray-level histogram (e.g., Otsu, 1979) or co-occurrence matrix (e.g., Chanda and Majumder, 1988) to achieve an optimal value of selected criterion. Suitability of this threshold value determines how easily and effectively these edge points can be linked to form a skyline curve. In this paper, we would compare algorithms in the Otsu's, 1979 and Chanda et al.'s (1988) works to see their relative performances in skyline extraction.

A skyline curve is a set of contiguous edge points that often extend from one side of the image to the other side. Skyline extraction is then modeled as a dynamic programming (DP) problem that searches a path or linkage by optimizing preselected preferences or cost. Based on this edgebased processing architecture, the processing time can be significantly reduced. Based on the DP search, the robustness to noises or broken lines can be ensured.

![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-03.jpg?height=134&width=1341&top_left_y=2118&top_left_x=268)
Fig. 1. The processing flow for skyline extraction.

## 3. Dynamic programming for skyline search

As illustrated in Fig. 1, we obtain a binary edge map as input of dynamic programming search. For moderate noise, the skyline can still be recognizable based on human's perception on contiguity of edges. That is, curve segments that preserve local smoothness and satisfy geometrical preferences will be considered as the better candidates.

First, we use the $M \times N$ binary edge map $\left\{b_{i j} \mid\right. b_{i j}=1$ or $\left.0, i=1, \ldots, M, j=1, \ldots, N\right\}$ to construct a multi-stage graph $G=\{V, L, \Psi, \Phi\}$ as follows:
(1) Each point $b_{i j}$ in the map corresponds to one node or vertex $v_{i, j} \in V$ in the $j$-th stage of the graph; $v_{i, j}$ is attributed as an edge vertex if $b_{i j}=1$ and as a non-edge vertex if $b_{i j}=0$.
(2) Two virtual vertices, $s$ and $t$, are added in the front and rear end, respectively, of the graph to represent the 0th and the ( $N+1$ )th stages.
(3) A link $l_{h, k, j} \in L$ is established between two edge vertices of adjacent stages, i.e., $v_{h, j}$ and $v_{k, j+1}$.
(4) Associate each vertex $v_{i, j}$ with a cost function $\Psi(i, j)$ :

$$
\Psi(i, j)= \begin{cases}(i+1)^{2}, & j=1 \text { or } N  \tag{1}\\ 0, & \text { otherwise }\end{cases}
$$

That is, $\Psi(i, j)$ is directly proportional to $v_{i, j}$ 's vertical position (assuming that the upper-left corner is the origin), which implies a preference of skylines at the upper part of the image (i.e., small $i$ ). It should be noticed that only the entry ( $j=1$ ) and exit ( $j=N$ ) nodes are charged with a square-of-level cost.
(5) Associate each link $l_{h, k, j}$ with a cost function $\Phi(h, k, j)$ :

$$
\Phi(h, k, j)= \begin{cases}|h-k| & \text { if }\left(b_{h, j}=b_{k, j+1}=1\right.  \tag{2}\\ & \text { and }|h-k| \leqslant \delta) \\ \infty, & \text { otherwise }\end{cases}
$$

where $\delta$ is a preset threshold. Eq. (2) means that two edges vertices with a vertical distance larger than $\delta$ cannot be linked. The choice of $\delta$ actually affects the capability in detecting steep skyline curves, e.g., those formed by buildings
in the suburb scenario, as well as the processing time required.
(6) Any link connecting vertex $s$ or $t$ is associated with a cost value of 0 , i.e., $\Phi(s, k, 0)= \Phi(h, t, N)=0$. This implies that $s$ and $t$ are freely linked to edge vertices at stages 1 and $N$, regardless of their vertical positions.

The topology for dynamic programming problem is therefore established and finding the shortest path from $s$ to $t$ is to find the path owning the minimum cost (the sum of vertex and link costs). A simple example is shown in Fig. 2, where an $8 \times 8$ edge map is converted to a multistage graph for DP evaluation. The black and white circles represent edge and non-edge vertices, respectively (the gray ones are originally non-edge vertices and will be explained later). To find a shortest path from $s$ to $t$, the backwards dynamic programming algorithm (see Horowitz and Sartaj (1978)) which evaluates temporary minimum at each edge node from stage 0 to stage $N+1$ can be applied.

Since the skyline curve may be disconnected due to poor image contrast or bad thresholding, a reasonable tolerance of gap (denoted as tog) should be allowed for robust detection. Practically, an expansion of the search region, up to tog stages, can be performed to bridge the gap and continue the linking of skyline curve. Fig. 3 illustrates the expanded region for a given vertex $p$ at stage $n$, which finds no edge nodes within $\pm \delta$ distance in the successive stage $n+1$. Our rule of expansion is that a set of $2(\delta+i)-1$ nodes are searched at stage $(n+i), i=1, \ldots$, tog , thus forming a fanshaped area, until an edge node is met or stage$(n+t o g)$ is reached. In this example, we set $\delta=3$ and $t o g=3$.

We now go back to the DP processing of Fig. 2. When evaluating $v_{32}$, there are no edge nodes in its near neighborhoods at the next stage. Expansion of the search region finds out $v_{65}$ as a candidate for linking. Hence, we would like to introduce dummy edge vertexes (i.e., the gray vertices $v_{43}$ and $v_{54}$ ) by linear interpolation and establish dummy linkages between them (i.e., $l_{3,4,2}, l_{4,5,3}$ and $l_{5,6,4}$ ). Accompanying the insertion of dummy edge vertices, we associate each dummy link with an extra punishment pun (as shown in Fig. 2) to

![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-05.jpg?height=852&width=999&top_left_y=316&top_left_x=435)
Fig. 2. The multi-stage graph topology corresponding to an $8 \times 8$ edge map for DP search.

increase the path cost so that linking artifacts due to dummy vertices can be avoided.

In the case where the skyline is broken in such a way that the horizontal gap is larger than tog (hence no other edge vertices locate within the expanded search region), the vertex $p$ will be considered invalid and incapable of obtaining its minimum partial path cost. For example, in Fig. 2 , if we set $t o g=2$ instead, $v_{32}$ will be invalid and the DP process can not find out a minimum-cost path from $s$ to $t$. Some tradeoffs should be made in selecting the parameters $\delta$ and tog. With the increase in the size of the search area, a larger gap can be tolerated, but noisy edge vertices may be falsely linked to form incorrect paths.

With the DP process going on stage by stage in Fig. 2, all possible paths originating from the leftmost stage (i.e., stage 1) are evaluated and the path owning the minimum cost from $s$ to $t$ (with the tolerance of gaps and punishment of extra costs) is selected. Up to now, our underlying algorithm still suffers from certain deficiencies or assumptions. Solutions to overcome these deficiencies are stated below.
(1) The above underlying algorithm relies on the connectedness of the skyline at two image boundaries, i.e., there should be no skyline breakage at stages 1 and $N$. To ensure this situation, we set all nodes at stages 1 and $N$ to be edges and search of the minimum-cost path from $s$ to $t$ will be initiated for each image row.
(2) The underlying algorithm assumes that the skyline curve expands from left to right sides of the image. However, the skyline may start or end at the top boundary of the image, due to low camera tilt angle. To make our DP algorithm operable, we set vertices $v_{1 j}, j=1, \ldots, \alpha$ and $j=\beta, \ldots, N$, to be edges. To prevent the first image row from being recognized as the skyline, the artificial breakage should be made larger than the maximum tolerance, i.e., $\beta-\alpha<$ tog .
(3) When the skyline has vertical segments, the DP algorithm is incapable of linking them in the vertical direction due to the fact that vertices at the same stage cannot be linked to each other. Nevertheless, with our algorithm, a ver-

![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-06.jpg?height=972&width=511&top_left_y=316&top_left_x=282)
Fig. 3. Expansion of search region for a vertex $p$ finding no edge nodes in the successive stages ( $\delta=3$ and tog $=3$ ).

tical segment of length less than or equal to $2 \delta$ can still be recognized, but with a slight distortion, as shown in Fig. 4.

Our skyline detection algorithm can be summarized as follows:

Step 1: Set the pixels at the left and right boundary columns and those in the front and rear parts of the first image row to be edges.
Step 2: Generate the multi-stage graph $G=\{V, L, \Psi, \Phi\}$ according to the binary edge map with two virtual vertices $s$ and $t$ at stage 0 and $N+1$, respectively.
Step 4: Perform dynamic programming to find the minimum-cost path $P^{*}$ from $s$ to $t$ according to the graph representation $G$. In the searching process, we allow skyline gaps small than tog.

![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-06.jpg?height=442&width=341&top_left_y=318&top_left_x=1197)
Fig. 4. DP processing on skylines with vertical segments. The gray vertices represent those obtained after linking (assuming $\delta=3$ ).

Step 5: Back trace the graph (see Horowitz and Sartaj (1978)) to derive the series of vertices that constitute $P^{*} \cdot P^{*}$ is recognized as the extracted skyline.

## 4. Computational complexity analysis

For edge detection and thresholding in Fig. 1, the computational cost depends solely on image dimensions (i.e., $M$ and $N$ ), but not on image contents. However, the computational cost of dynamic programming is dependent on the number of edge points (denoted as $n$ ) and the topological relations they have. In the best case, each edge vertex has to search only $2 \delta+1$ nodes at its successive stage, while in the worst case, it is $(2 \delta+ t o g+1) \cdot(t o g+1)$, due to possibly expanded search region. Hence the computational complexity of DP is $\mathrm{O}(n \cdot \delta)$ or $\mathrm{O}\left(n \cdot t o g^{2}\right)$, when $\delta<t o g$ is assumed practically. Since we often have $n \gg \delta$, tog , a linear time complexity with respect to $n$, i.e., $\mathrm{O}(n)$, is valid for speed evaluation of proposed algorithm.

## 5. Experimental results

In our experiments, $25352 \times 240$ images were tested with $\delta=3$, tog $=30$ and pun $=100$. Only some of them are shown here. Fig. 5(a1)-(a5) show the original test images, Fig. 5(b1)-(b5) are for the Sobel edge responses, and Fig. 5(c1)-(c5) for the

| Test image | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=280&top_left_y=324&top_left_x=335) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=192&width=273&top_left_y=326&top_left_x=618) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=192&width=277&top_left_y=326&top_left_x=892) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=279&top_left_y=324&top_left_x=1173) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=279&top_left_y=324&top_left_x=1449) |
| :--- | :--- | :--- | :--- | :--- | :--- |
|  | (al) | (a2) | (a3) | (a4) | (a5) |
| Sobel edge response | □ |  |  |  |  |
|  | (b1) | (b2) | (b3) | (b4) | (b5) |
| Sobel+ Otsu | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=284&top_left_y=807&top_left_x=335) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=198&width=279&top_left_y=807&top_left_x=612) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=198&width=284&top_left_y=807&top_left_x=892) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=192&width=277&top_left_y=809&top_left_x=1173) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=196&width=279&top_left_y=809&top_left_x=1449) |
|  | (c1) | (c2) | (c3) | (c4) | (c5) |
| Sobel+CP | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=198&width=280&top_left_y=1051&top_left_x=335) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=190&width=271&top_left_y=1051&top_left_x=620) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=196&width=284&top_left_y=1047&top_left_x=892) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=190&width=281&top_left_y=1051&top_left_x=1173) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=196&width=281&top_left_y=1047&top_left_x=1447) |
|  | (d1) | (d2) | (d3) | (d4) | (d5) |
| Sobel+ averaging | (e1) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=196&width=275&top_left_y=1291&top_left_x=620) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=192&width=282&top_left_y=1295&top_left_x=892) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=279&top_left_y=1291&top_left_x=1173) | " |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  | (f1) | (f2) | (f3) | (f4) | (f5) |
| Canny edge response | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=284&top_left_y=1778&top_left_x=335) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=192&width=275&top_left_y=1780&top_left_x=620) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=273&top_left_y=1778&top_left_x=894) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=190&width=277&top_left_y=1782&top_left_x=1173) | ![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-07.jpg?height=194&width=277&top_left_y=1778&top_left_x=1451) |
|  | (g1) | (g2) | (g3) | (g4) | (g5) |
| Skyline detected |  |  |  |  |  |
|  | (h1) | (h2) | (h3) | (h4) | (h5) |

Fig. 5. Experimental results for five chosen test images.

edge maps by using the Otsu's, 1979 automatic thresholding method.

Fig. 5(d1)-(d5) show the results based on another thresholding algorithm: conditional probability (CP) (see Chanda et al. (1988)). It was found that characteristics of the thresholded results might be complementary between the Otsu and CP algorithms. This phenomenon motivates us to determine the threshold value by averaging those obtained individually. The thresholded results are more stable (Fig. 5(e1)-(e5)) and all lead to successful skyline extraction (Fig. 5(f1)-(f5)). Though there are breakages for the skyline edge map in Fig. 5(e2), our DP algorithm can extract it robustly (Fig. 5(f2)). For the edge maps in Fig.

5(e1), our algorithm still work well, in spite of the existence of clouds.

We also applied the well-known Canny operator, for comparison, to obtain the edge map (Fig. 5(g1)-(g5)), which are then processed for the extraction of skylines (Fig. 5(h1)-(h5)). It can be found that only part of the skyline is correct in Fig. 5(h4) and some defects are present in Fig. 5(h3).

To have an intensive comparison between the Sobel-based and the Canny-based approaches, we conducted experiments on a total of 25 test images, with the same DP parameters in both cases. The extracted skylines were manually evaluated into scores between 0 and 5 . We gave a score

![](https://cdn.mathpix.com/cropped/01b1ccbe-8eab-413e-a65f-b3652e4c8bd2-08.jpg?height=1206&width=773&top_left_y=1044&top_left_x=564)
Fig. 6. Experimental results for other two chosen cases.

Table 1
CPU time in each step of proposed algorithm
| CPU time (s) | Fig. 5(al) | Fig. 5(a2) | Fig. 5(a3) | Fig. 5(a4) | Fig. 5(a5) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Sobel | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 |
| Averaging thresholding | 0.05 | 0.05 | 0.05 | 0.04 | 0.05 |
| DP | 0.09 | 0.05 | 0.12 | 0.04 | 0.06 |
| Total | 0.18 | 0.14 | 0.21 | 0.12 | 0.15 |


0 if the skyline cannot be extracted; a score 1 if up to $1 / 5$ of the skyline is extracted; a score 2 if 1/5-2/ 5 of the skyline is obtained;. . .; and a score 5 if the whole skyline is successfully extracted. The average of these 25 subjective scores was calculated for both cases. According to the experiments, both the Canny-based and the Sobel-based approaches yield an average score of 4.4. The skylines were missed (i.e., scored 0 ) in 2 out of the 25 images for the Sobel-based method, while only 1 for the Canny-based method. The average scores, without considering the 0's, for the Sobel-based and the Canny-based methods are 4.78 and 4.58, respectively. Fig. 6 shows two other cases. The result in Fig. 6(e1) shows superiority, with respective to Fig. 6(c1) (no skyline is detected), of Canny operator in low-contrast edge extraction. On the other hand, Fig. 6(c2) and (e2) illustrate the failure case (scored 0 ) for both operators. We hence conclude that the Sobel-based implementation has more accuracy in skyline extraction, while the Canny operator presents a better performance in extracting low contrast skylines.

In view of the processing speed, the Canny operator surely requires much more irregular computations than the Sobel operator, which even has ASIC products in hardware implementation. We conducted the Sobel-based experiments on a PentiumM 1.3 GHz CPU. The CPU time needed in each step (including Sobel edge detection, averaging (Otsu + CP) thresolding, and DP search) is listed in Table 1. Among them, the processing time for Sobel and thresholding is nearly content-independent, while the CPU time for DP search, ranging from 0.04 to 0.12 s , heavily depends on the number of edge points processed. These figures indicate that our algorithm for skyline detection can be operated at a frame rate of about $5-8 \mathrm{~Hz}$, without special computing hardware. With simple hardware for

Sobel and edge thresholding, the algorithm can be run in near real-time for navigation purpose.

## 6. Conclusions

The position estimation problem for mobile navigation becomes more complicated in an unstructured environment, such as the mountainous area. The skyline representing silhouettes of terrain objects against the sky can serve as the natural landmark or reference feature which can be detected by a vision sensor and matched with those pre-stored in database to determine the accurate vehicle/plane position. We propose here a skyline detection algorithm, including processes of edge map detection and edge linking. By constructing a multi-stage graph according to the detected edge map, our algorithm is capable of applying the dynamic programming principle for skyline linking. Characteristics of the skyline and tolerance consideration are utilized to achieve better performance and robustness. Experiments show that the processing speed is fast and promising for real-time applications.

## References

Ballard, D.H., Brown, C.M., 1982. Computer Vision. PrenticeHall, Englewood Cliffs, NJ, p. 137-143.
Chanda, B., Majumder, D.D., 1988. A note on the use of the graylevel co-occurrence matrix in threshold selection. Signal Process. 15, 149-167.
Fang, M., Chiu, M.-Y., Liang, C.-C., Singh, A., 1993. Skyline for video-based virtual rail for vehicle navigation. In: Proc. of IEEE Internat. Sympos. on Intelligent Vehicles, pp. 207212.

Geiger, D., Gupta, A., Costa, L.A., Vlontzos, J., 1995. Dynamic programming for detecting, tracking, and matching deformable contours. IEEE Trans. Patten Anal. Machine Intell. 17 (3), 294-302.

Horowitz, E., Sartaj, S., 1978. Fundamentals of Computer Algorithms. Computer Science Press Inc.
Kabuka, M., Arenas, A., 1987. Position verification of a mobile robot using a standard pattern. IEEE J. Robot. Autom. 3 (6), 505-516.

Kim, H., Hong, S., Son, H., Roska, T., Werblin, F., 2003. High speed road boundary detection on the images for autonomous vehicle with the multilayer CNN. In: Proc. IEEE Internat. Sympos. on Circuits and Systems, pp. V-769-V772.

Lee, B., Yan, J.Y., Zhuang, T.G., 2001. A dynamic programming based algorithm for optimal edge detection in medical images. In: Proc. Internat. Workshop on Medical Imaging and Augmented Reality, pp. 193-198.
Merlet, N., Zerubia, J., 1996. New prospects in line detection by dynamic programming. IEEE Trans. Pattern Anal. Machine Intell. 18 (4), 426-431.

Otsu, N., 1979. A threshold selection method from graylevel histogram. IEEE Trans. Systems Man Cybernet. 9 (1), 6266.

Stewart, J.A., 1998. Fast horizon computation at all points of a terrain with visibility and shading applications. IEEE Trans. Visual. Comput. Graphics 4 (1), 82-93.
Suh, S.H., Kang, J.K., Jee, W.S., Jung, M.Y., Kim, K.S., 1993. Estimating ALV position in mountainous area. In: Proc. IEEE/RSJ Internat. Conf. on Intelligent Robots and Systems, pp. 2178-2185.
Talluri, R., Aggarwal, J., 1990. Position estimation for a mobile robot in an unstructured environment. In: Proc. IEEE Internat. Conf. on Intelligent Robots and Systems, pp. 159166.

Yang J., Ozawa, S., 1996. Road scene analysis from perspective image. In: Proc. IEEE Conf. on Acoustics, Speech, and Signal Processing, pp. 3474-3477.


[^0]:    * Corresponding author. Tel.: +886 $52720411 \times 33211$; fax: +886 52720862.

    E-mail address: wnlie@ee.ccu.edu.tw (W.-N. Lie).

