from typing import List, Set

from robot_cameraman.image_detection import DetectionCandidate


def filter_intersections(candidates: List[DetectionCandidate]):
    count = len(candidates)
    if count == 0:
        return []
    # Indices of candidates that have a bounding box with a smaller area than
    # the area of the intersected bounding box of another candidate
    excluded: Set[int] = set()
    result: List[DetectionCandidate] = []
    for c in range(0, count - 1):
        if c in excluded:
            continue
        current = candidates[c]
        for o in range(c + 1, count):
            other = candidates[o]
            intersection = current.bounding_box.percental_intersection_area(
                other.bounding_box)
            if intersection > 0.3:
                if current.bounding_box.area() < other.bounding_box.area():
                    excluded.add(c)
                    break
                else:
                    excluded.add(o)
        else:
            result.append(current)
    if (count - 1) not in excluded:
        result.append(candidates[count - 1])
    return result
