from robot_cameraman.box import Box
from robot_cameraman.pose_detection.pose import Pose, KeyPoint


class TestPose:
    def test_get_bounding_box(self):
        pose = Pose(
            nose=KeyPoint(y=224.17, x=317.26, confidence=0.56),
            left_eye=KeyPoint(y=216.31, x=325.12, confidence=0.63),
            right_eye=KeyPoint(y=218.28, x=301.52, confidence=0.36),
            left_ear=KeyPoint(y=230.07, x=340.85, confidence=0.63),
            right_ear=KeyPoint(y=232.04, x=291.04, confidence=0.56),
            left_shoulder=KeyPoint(y=277.27, x=356.59, confidence=0.70),
            right_shoulder=KeyPoint(y=283.17, x=267.44, confidence=0.49),
            left_elbow=KeyPoint(y=230.07, x=411.65, confidence=0.70),
            right_elbow=KeyPoint(y=228.11, x=201.89, confidence=0.70),
            left_wrist=KeyPoint(y=145.52, x=411.65, confidence=0.70),
            right_wrist=KeyPoint(y=155.35, x=183.53, confidence=0.56),
            left_hip=KeyPoint(y=420.82, x=351.34, confidence=0.19),
            right_hip=KeyPoint(y=412.96, x=283.17, confidence=0.36),
            left_knee=KeyPoint(y=479.82, x=356.59, confidence=0.12),
            right_knee=KeyPoint(y=471.95, x=288.41, confidence=0.07),
            left_ankle=KeyPoint(y=475.89, x=338.23, confidence=0.07),
            right_ankle=KeyPoint(y=489.65, x=283.17, confidence=0.07))
        expected_bounding_box = Box.from_coordinates(
            183.53, 145.52,
            411.65, 489.65)
        actual_bounding_box = pose.get_bounding_box()
        assert (actual_bounding_box.x == expected_bounding_box.x
                and actual_bounding_box.y == expected_bounding_box.y
                and actual_bounding_box.width == expected_bounding_box.width
                and actual_bounding_box.height == expected_bounding_box.height)
