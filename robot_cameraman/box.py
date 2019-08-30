from typing import List, Tuple

import numpy

Box = numpy.array


def center(box: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = box
    return abs(x1 + x2) / 2, abs(y1 + y2) / 2
