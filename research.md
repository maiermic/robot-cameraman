# Research
This document is a collection of terms, algorithms and sources that are related to this project.

## Terms

### Object Detection
### Object Localization
### Object Tracking
### Object Re-Identification

### On-line tracking
Only current and previous frames are available

### Off-line (batch) tracking
All frames (including future) are available

### Affinity Components
From transcript of video [Examples of multiple object tracking methods][examples-of-multiple-object-tracking-methods] 

> To associate detection and tracks, we need to estimate similarity or affinity between them. We can use several features to compute affinity scroll. This visual similarity, motion similarity and interaction between objects and objects within the scene. The simplest form of affinity is overlap between detection in the current frame and in the previous frame. If video frame rate is high and object detection is good and objects are moving slowly between frames and through detections of the highest overlap. The validity of this simple approach has been demonstrated in the recent high speed tracking by detection result using image information paper from AVSS 2017.

### Intersection over Union (IoU)
Used in [High-Speed Tracking-by-Detection Without Using Image Information by Bochinski et. al.](http://elvera.nue.tu-berlin.de/files/1517Bochinski2017.pdf)
![IoU](https://d3i71xaburhd42.cloudfront.net/9f394da08dc44501cc19bc9d2183ecba0d01c46d/1-Figure1-1.png)

## Algorithms

### Non-maximum Suppression (NMS)
Used in [Real-time Object Tracking with TensorFlow, Raspberry Pi, and Pan-Tilt HAT](https://towardsdatascience.com/real-time-object-tracking-with-tensorflow-raspberry-pi-and-pan-tilt-hat-2aeaef47e134) by [Leigh Johnson
](http://towardsdatascience.com/@grepLeigh)

> Non-maximum Suppression is technique that filters many bounding box proposals using set operations.
>
> ![nms](https://miro.medium.com/max/1558/0*weFV951XGeWqehMc.png)

[Video](https://de.coursera.org/lecture/convolutional-neural-networks/non-max-suppression-dvrjH) that explains the algorithm.

### Kalman Filter
According to [Wikipedia](https://en.wikipedia.org/wiki/Kalman_filter):

> an algorithm that uses a series of measurements observed over time, containing statistical noise and other inaccuracies, and produces estimates of unknown variables that tend to be more accurate than those based on a single measurement alone, by estimating a joint probability distribution over the variables for each timeframe.

Videos:
- [Introduction to Kalman Filters for Object Tracking](https://www.mathworks.com/videos/introduction-to-kalman-filters-for-object-tracking-79674.html)
- [Why You Should Use The Kalman Filter Tutorial - Pokemon Example](https://www.youtube.com/watch?v=bm3cwEP2nUo)

Article: [How a Kalman filter works, in pictures](https://www.bzarg.com/p/how-a-kalman-filter-works-in-pictures/)

### Object Tracking
The article [OpenCV Object Tracking](https://www.pyimagesearch.com/2018/07/30/opencv-object-tracking/) compares different algorithms:

> 1. **BOOSTING Tracker:** Based on the same algorithm used to power the machine learning behind Haar cascades (AdaBoost), but like Haar cascades, is over a decade old. This tracker is slow and doesn’t work very well. Interesting only for legacy reasons and comparing other algorithms. (minimum OpenCV 3.0.0)
> 2. **MIL Tracker:** Better accuracy than BOOSTING tracker but does a poor job of reporting failure. (minimum OpenCV 3.0.0)
> 3. **KCF Tracker:** Kernelized Correlation Filters. Faster than BOOSTING and MIL. Similar to MIL and KCF, does not handle full occlusion well. (minimum OpenCV 3.1.0)
> 4. **CSRT Tracker:** Discriminative Correlation Filter (with Channel and Spatial Reliability). Tends to be more accurate than KCF but slightly slower. (minimum OpenCV 3.4.2)
> 5. **MedianFlow Tracker:** Does a nice job reporting failures; however, if there is too large of a jump in motion, such as fast moving objects, or objects that change quickly in their appearance, the model will fail. (minimum OpenCV 3.0.0)
> 6. **TLD Tracker:** I’m not sure if there is a problem with the OpenCV implementation of the TLD tracker or the actual algorithm itself, but the TLD tracker was incredibly prone to false-positives. I do not recommend using this OpenCV object tracker. (minimum OpenCV 3.0.0)
> 7. **MOSSE Tracker:** Very, very fast. Not as accurate as CSRT or KCF but a good choice if you need pure speed. (minimum OpenCV 3.4.1)
> 8. **GOTURN Tracker:** The only deep learning-based object detector included in OpenCV. It requires additional model files to run (will not be covered in this post). My initial experiments showed it was a bit of a pain to use even though it reportedly handles viewing changes well (my initial experiments didn’t confirm this though). I’ll try to cover it in a future post, but in the meantime, take a look at [Satya’s writeup](https://www.learnopencv.com/goturn-deep-learning-based-object-tracking/). (minimum OpenCV 3.2.0)

The video [Examples of multiple object tracking methods][examples-of-multiple-object-tracking-methods] shortly explains:
1. Intersection over Union Tracker
2. Simple Online and Realtime Tracking (SORT)

#### Intersection over Union Tracker
From transcript of video [Examples of multiple object tracking methods][examples-of-multiple-object-tracking-methods]:

> Despite the simplicity of this approach, it reaches state of that result on DETRACK data set, outperforming much more elaborate methods. The results on more challenge are no better as good detector either. But if detector fails a frame and misses the object, then tracking of this object is stopped. False negative ID speech errors will be produced.

#### Simple Online and Realtime Tracking (SORT)
- [Simple Online and Realtime Tracking](https://arxiv.org/pdf/1602.00763.pdf)
- [Simple Online and Realtime Tracking with a Deep Association Metric](https://arxiv.org/pdf/1703.07402.pdf)

From transcript of video [Examples of multiple object tracking methods][examples-of-multiple-object-tracking-methods]:

> The problem (detector fails a frame and misses the object) can be alleviated if it can use predicted object position instead of a missed detection in this frame. For example, we can use kalman filter to predict objects based on its positions in previous frames. Then we can associate detections in current frame these predictions from previous frames. If object is not detected in the current frame, you don't finish the track immediately but continue to track this predictions for several frames. We hope that eventually the object will be detected. And if predictions are good enough, we will successfully associate this detection with predicted position and assume tracking. Because predictions are less precise than detection, you should replace simple grid based with old method. It's the optimal Hungarian algorithm for the assignment problem, as it was done in simple online in real time tracking these high quality detections paper. From a result of this algorithm in more challenge 2016, we see that movement predictions significantly reduce fragmentation and ID switches. Resulting by the number of false positives are also increased.

[examples-of-multiple-object-tracking-methods]: https://www.coursera.org/lecture/deep-learning-in-computer-vision/examples-of-multiple-object-tracking-methods-VJZUW
