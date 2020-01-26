# import the necessary packages
from collections import OrderedDict
from logging import Logger, getLogger
from typing import List, Dict, Set

import numpy
import numpy as np
from scipy.spatial import distance as dist

from robot_cameraman.image_detection import DetectionCandidate

logger: Logger = getLogger(__name__)


# https://www.pyimagesearch.com/2018/07/23/simple-object-tracking-with-opencv/
class CentroidTracker:
    def __init__(self, max_disappeared=50):
        # initialize the next unique object ID along with two ordered
        # dictionaries used to keep track of mapping a given object
        # ID to its centroid and number of consecutive frames it has
        # been marked as "disappeared", respectively
        self.next_object_id = 0
        self.objects = OrderedDict()
        self.candidates: OrderedDict[int, DetectionCandidate] = OrderedDict()
        self.disappeared = OrderedDict()

        # store the number of maximum consecutive frames a given
        # object is allowed to be marked as "disappeared" until we
        # need to deregister the object from tracking
        self.max_disappeared = max_disappeared

    def register(self, centroid, candidate):
        # when registering an object we use the next available object
        # ID to store the centroid
        self.objects[self.next_object_id] = centroid
        self.candidates[self.next_object_id] = candidate
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        # to deregister an object ID we delete the object ID from
        # both of our respective dictionaries
        del self.objects[object_id]
        del self.candidates[object_id]
        del self.disappeared[object_id]

    def is_registered(self, object_id: int) -> bool:
        return object_id in self.objects

    def update(self, input_centroids: numpy.ndarray, candidates):
        # check to see if the list of input bounding box rectangles
        # is empty
        if len(input_centroids) == 0:
            # loop over any existing tracked objects and mark them
            # as disappeared
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1

                # if we have reached a maximum number of consecutive
                # frames where a given object has been marked as
                # missing, deregister it
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            # return early as there are no centroids or tracking info
            # to update
            return self.objects

        # if we are currently not tracking any objects take the input
        # centroids and register each of them
        if len(self.objects) == 0:
            for i in range(0, len(input_centroids)):
                self.register(input_centroids[i], candidates[i])

        # otherwise, we are currently tracking objects so we need to
        # try to match the input centroids to existing object
        # centroids
        else:
            # grab the set of object IDs and corresponding centroids
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())

            # compute the distance between each pair of object
            # centroids and input centroids, respectively -- our
            # goal will be to match an input centroid to an existing
            # object centroid
            d = dist.cdist(np.array(object_centroids), input_centroids)

            # in order to perform this matching we must (1) find the
            # smallest value in each row and then (2) sort the row
            # indexes based on their minimum values so that the row
            # with the smallest value is at the *front* of the index
            # list.
            # Ignore warning "Parameter 'initial' unfilled" of the following
            # statement in Intellij. It is a bug in the stubs. The parameter is
            # actually optional.
            # noinspection PyArgumentList
            rows = d.min(axis=1).argsort()

            # next, we perform a similar process on the columns by
            # finding the smallest value in each column and then
            # sorting using the previously computed row index list
            cols = d.argmin(axis=1)[rows]

            # in order to determine if we need to update, register,
            # or deregister an object we need to keep track of which
            # of the rows and column indexes we have already examined
            used_rows: Set[int] = set()
            used_cols: Set[int] = set()

            logger.debug('  distances:')
            # loop over the combination of the (row, column) index
            # tuples
            for (row, col) in zip(rows, cols):
                # if we have already examined either the row or
                # column value before, ignore it
                # val
                if row in used_rows or col in used_cols:
                    continue

                # otherwise, grab the object ID for the current row
                object_id = object_ids[row]
                distance = d[row, col]
                # it is assumed that older objects may have moved further,
                # but recently seen objects do not move suddenly in big steps
                limit = min(500, 100 * (self.disappeared[object_id] + 1))
                old = self.candidates[object_id].bounding_box
                new = candidates[col].bounding_box
                old_a = old.area()
                new_a = new.area()
                size_change_factor = max(old_a, new_a) / min(old_a, new_a)
                intersection = old.percental_intersection_area(new)
                intersection_limit = 0.3
                if distance > limit and intersection < intersection_limit:
                    logger.debug(
                        f'    {object_id}: {int(distance):3} > {limit:3}'
                        f' and {intersection:.2} < {intersection_limit:.2}')
                    # objects too far away from recently seen one are treated as
                    # new ones if they do not overlap for the most part
                    self.register(input_centroids[col], candidates[col])
                elif size_change_factor > 4:
                    # TODO log distance, intersection and areas
                    self.register(input_centroids[col], candidates[col])
                else:
                    logger.debug(
                        f'    {object_id}: {int(distance):3} <= {limit:3}'
                        f' or {intersection:.2} >= {intersection_limit:.2}')
                    # set new centroid, and reset the disappeared counter
                    self.objects[object_id] = input_centroids[col]
                    self.candidates[object_id] = candidates[col]
                    self.disappeared[object_id] = 0

                # indicate that we have examined each of the row and
                # column indexes, respectively
                used_rows.add(row)
                used_cols.add(col)

            # compute both the row and column index we have NOT yet
            # examined
            unused_rows = set(range(0, d.shape[0])).difference(used_rows)
            unused_cols = set(range(0, d.shape[1])).difference(used_cols)

            # in the event that the number of object centroids is
            # equal or greater than the number of input centroids
            # we need to check and see if some of these objects have
            # potentially disappeared
            if d.shape[0] >= d.shape[1]:
                # loop over the unused row indexes
                for row in unused_rows:
                    # grab the object ID for the corresponding row
                    # index and increment the disappeared counter
                    object_id = object_ids[row]
                    self.disappeared[object_id] += 1

                    # check to see if the number of consecutive
                    # frames the object has been marked "disappeared"
                    # for warrants deregistering the object
                    if self.disappeared[object_id] > self.max_disappeared:
                        self.deregister(object_id)

            # otherwise, if the number of input centroids is greater
            # than the number of existing object centroids we need to
            # register each new input centroid as a trackable object
            else:
                for col in unused_cols:
                    self.register(input_centroids[col], candidates[col])

        # return the set of trackable objects
        return self.objects


class ObjectTracker:
    _centroid_tracker: CentroidTracker

    def __init__(self, max_disappeared=20):
        self._centroid_tracker = CentroidTracker(
            max_disappeared=max_disappeared)

    def update(self, inference_results: List[DetectionCandidate]) \
            -> Dict[int, DetectionCandidate]:
        centroid_to_inference_result = dict()
        centroids = np.zeros((len(inference_results), 2), dtype="int")
        for i, r in enumerate(inference_results):
            c = (int(r.bounding_box.center.x), int(r.bounding_box.center.y))
            centroids[i] = c
            centroid_to_inference_result[c] = r
        objects = self._centroid_tracker.update(centroids, inference_results)
        return {object_id: centroid_to_inference_result[(x, y)]
                for object_id, (x, y) in objects.items()
                if (x, y) in centroid_to_inference_result}

    def is_registered(self, object_id: int) -> bool:
        return self._centroid_tracker.is_registered(object_id)
