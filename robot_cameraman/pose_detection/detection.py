from abc import abstractmethod
from pathlib import Path
from typing import Iterable

import PIL.Image
from PIL import Image
from typing_extensions import Protocol

from robot_cameraman.pose_detection.pose import Pose, NUM_KEY_POINTS, KeyPoint


class PoseDetectionEngine(Protocol):
    @abstractmethod
    def detect(self, image: PIL.Image.Image) -> Iterable[Pose]:
        raise NotImplementedError


class EdgeTpuPoseDetectionEngine(PoseDetectionEngine):
    def __init__(self, model: Path) -> None:
        import pycoral.utils.dataset
        import pycoral.utils.edgetpu
        self._interpreter = pycoral.utils.edgetpu.make_interpreter(str(model))
        self._interpreter.allocate_tensors()

    def detect(self, image: PIL.Image.Image) -> Iterable[Pose]:
        from pycoral.adapters import common
        resized_img = image.resize(common.input_size(self._interpreter),
                                   Image.ANTIALIAS)
        common.set_input(self._interpreter, resized_img)
        self._interpreter.invoke()
        nd_pose = common.output_tensor(
            self._interpreter, 0).copy().reshape(NUM_KEY_POINTS, 3)
        width, height = image.size
        pose: Pose = Pose._make(
            (KeyPoint(x=kp[1] * width, y=kp[0] * height, confidence=kp[2])
             for kp in nd_pose))
        return pose,
