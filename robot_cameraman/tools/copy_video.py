import argparse
from pathlib import Path

import cv2
from cv2 import VideoCapture
from typing_extensions import Protocol


class Arguments(Protocol):
    input: Path
    output: Path


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Copy video to fix properties like cv2.CAP_PROP_POS_FRAMES.")
    parser.add_argument('--input',
                        type=Path,
                        help="Video input file that should be copied.")
    parser.add_argument('--output',
                        type=Path,
                        help="Video output file where copy is saved.")
    # noinspection PyTypeChecker
    return parser.parse_args()


def main():
    args = parse_arguments()
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    frames_per_second = 15
    frame_size = (640, 480)
    video_writer = cv2.VideoWriter(
        str(args.output), fourcc, frames_per_second, frame_size)

    input_video = VideoCapture(str(args.input))

    frame_counter = -1
    while True:
        success, raw_image = input_video.read()
        if not success:
            break
        frame_counter += 1
        video_writer.write(raw_image)

    input_video.release()
    video_writer.release()


if __name__ == '__main__':
    main()
