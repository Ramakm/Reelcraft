# Bundled model

`face_detection_yunet_2023mar.onnx` is YuNet, a small face detector by Shiqi Yu et al., distributed in
[opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) under the MIT licence
(see `LICENSE-yunet.txt`). It is unmodified. Reelcraft uses it only to find the speaker's face; if it is missing,
tracking falls back to the Haar cascades that ship with OpenCV.
