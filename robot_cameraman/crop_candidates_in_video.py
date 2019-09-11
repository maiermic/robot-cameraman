import argparse
import os
from pathlib import Path
from typing import Any

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2

from robot_cameraman.box import Box
from robot_cameraman.image_detection import DetectionEngine


def main(args):
    detection_engine = DetectionEngine(
        model=args.model,
        confidence=args.confidence,
        max_objects=args.maxObjects)
    vs = cv2.VideoCapture(str(args.input))
    candidate_counter = 0
    while True:
        try:
            success, frame = vs.read()
            if not success:
                break
            image = PIL.Image.fromarray(frame)
            inference_results = detection_engine.detect(image)
            candidates = [
                obj for obj in inference_results
                if obj.label_id == args.targetLabelId]
            image = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            for candidate in candidates:
                out_file = args.output / '{:0>3}.jpg'.format(candidate_counter)
                candidate_counter += 1
                b = candidate.bounding_box
                size = max(b.width, b.height)
                box = Box.from_center_and_size(b.center, size, size)
                image.crop(box.coordinates).save(out_file)
            if args.showVideo:
                cv2.imshow('NCS Improved live inference', frame)
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
    parser.add_argument('--input', type=Path, help="Path to input video file.")
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
    assert args.input.exists(), args.input
    assert args.output.is_dir(), args.output
    main(args)
