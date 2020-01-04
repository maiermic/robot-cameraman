import argparse
import glob
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import numpy
from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import FreeTypeFont

from robot_cameraman.annotation import ImageAnnotator
from robot_cameraman.image_detection import DetectionEngine, DetectionCandidate
from robot_cameraman.object_tracking import ObjectTracker
from robot_cameraman.resource import read_label_file

colors: List[Tuple[int, int, int]] = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
]


def get_color(index, default):
    if index is None:
        return default
    try:
        return colors[index]
    except IndexError:
        return default


class ColoredCandidatesImageAnnotator(ImageAnnotator):

    def __init__(self, target_label_id: int, labels: Dict[int, str],
                 font: FreeTypeFont) -> None:
        super().__init__(target_label_id, labels, font)
        self._global_candidate_id = 0

    def annotate(
            self,
            image: PIL.Image.Image,
            target_id: Optional[int],
            candidates: Dict[int, DetectionCandidate],
            previous_candidates: Optional[
                Dict[int, DetectionCandidate]] = None) -> None:
        draw = PIL.ImageDraw.Draw(image, 'RGBA')
        if previous_candidates:
            for candidate_id, candidate in previous_candidates.items():
                color = get_color(candidate_id, (255, 255, 255))
                draw.rectangle(candidate.bounding_box.coordinates(),
                               width=8, outline=(*color, 60))
        for candidate_id, candidate in candidates.items():
            color = get_color(candidate_id, (255, 255, 255))
            self.draw_detection_candidate(draw, candidate_id, candidate, color,
                                          outline_width=8)

    def draw_candidate_id(self, draw: ImageDraw, center, candidate_id: str):
        super().draw_candidate_id(draw, center,
                                  f'{candidate_id}/{self._global_candidate_id}')
        self._global_candidate_id += 1


def create_video_writer(vs, output_file: Path):
    width = int(vs.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vs.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return cv2.VideoWriter(str(output_file),
                           cv2.VideoWriter_fourcc(*'MJPG'),
                           vs.get(cv2.CAP_PROP_FPS),
                           (width, height))


def main(args):
    labels = read_label_file(args.labels)
    font = PIL.ImageFont.truetype(str(args.font), args.fontSize)
    detection_engine = DetectionEngine(
        model=args.model,
        confidence=args.confidence,
        max_objects=args.maxObjects)
    object_tracker = ObjectTracker()
    annotator = ColoredCandidatesImageAnnotator(args.targetLabelId, labels,
                                                font)
    previous_candidates: Optional[Dict[int, DetectionCandidate]] = None
    vs = cv2.VideoCapture(str(args.input))
    out = create_video_writer(vs, args.output)
    while True:
        try:
            success, frame = vs.read()
            if not success:
                break
            image = PIL.Image.fromarray(frame)
            inference_results = detection_engine.detect(image)
            target_inference_results = [
                obj for obj in inference_results
                if obj.label_id == args.targetLabelId]
            candidates = object_tracker.update(target_inference_results)
            if previous_candidates:
                previous_candidates = {
                    id: candidate
                    for (id, candidate) in previous_candidates.items()
                    if object_tracker.is_registered(id)}
            annotator.annotate(image, None, candidates, previous_candidates)
            previous_candidates = {**previous_candidates,
                                   **candidates} if previous_candidates else candidates

            annotated_image = numpy.asarray(image)
            out.write(annotated_image)
            if args.showVideo:
                cv2.imshow('NCS Improved live inference', annotated_image)
                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        except KeyboardInterrupt:
            break
    vs.release()
    cv2.destroyAllWindows()


def str2bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def parse_arguments():
    resources: Path = Path(__file__).parent / 'resources'
    mobilenet = 'mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite'
    parser = argparse.ArgumentParser(
        description="Detect objects in a video file using Google Coral USB.")
    parser.add_argument('--input', type=str, help="Path to input video file.")
    parser.add_argument('--output',
                        type=Path,
                        help="Video output file of annotated image stream.")
    parser.add_argument(
        '--showVideo',
        type=str,
        default=True,
        help="Show video while processing.")
    parser.add_argument(
        '--model',
        type=Path,
        default=resources / mobilenet,
        help="Path to the neural network graph file.")
    parser.add_argument(
        '--labels',
        type=Path,
        default=resources / 'coco_labels.txt',
        help="Path to labels file.")
    parser.add_argument('--maxObjects', type=int,
                        default=10,
                        help="Maximum objects to infer in each frame of video.")
    parser.add_argument('--confidence', type=float,
                        default=0.50,
                        help="Minimum confidence threshold to tag objects.")
    parser.add_argument('--font',
                        type=Path,
                        default=resources / 'Roboto-Regular.ttf',
                        help="Font used in image annotations.")
    parser.add_argument('--fontSize',
                        type=int,
                        default=30,
                        help="Font size used in image annotations.")
    parser.add_argument('--targetLabelId', type=int,
                        default=0,
                        help="ID of label to track.")
    args = parser.parse_args()
    args.showVideo = str2bool(args.showVideo)
    if args.showVideo:
        assert 'DISPLAY' in os.environ
    return args


if __name__ == '__main__':
    args = parse_arguments()
    input_file = Path(args.input)
    if input_file.exists():
        args.input = input_file
        if args.output.is_dir():
            args.output = args.output / (input_file.stem + '_annotated.avi')
        main(args)
    else:
        files = list(map(Path, glob.iglob(args.input)))
        if not files:
            raise Exception('Not found {}'.format(args.input))
        else:
            assert args.output.is_dir()
            out_dir = args.output
            for input_file in files:
                args.input = input_file
                args.output = out_dir / (input_file.stem + '_annotated.avi')
                assert not args.showVideo
                print('annotating\n\tinput: {}\n\toutput: {}'
                      .format(args.input, args.output))
                main(args)
