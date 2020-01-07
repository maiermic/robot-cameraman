import argparse
import os
from pathlib import Path

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import cv2
import numpy


def create_video_writer(vs, output_file: Path):
    width = int(vs.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vs.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return cv2.VideoWriter(str(output_file),
                           cv2.VideoWriter_fourcc(*'MJPG'),
                           vs.get(cv2.CAP_PROP_FPS),
                           (width, height))


class VideoFramePlayer:
    def __init__(self, file: Path, font):
        assert file.exists()
        self._file = file
        self._vs = cv2.VideoCapture(str(self._file))
        self._frame_count = int(self._vs.get(cv2.CAP_PROP_FRAME_COUNT))
        self._font = font

    def run(self):
        is_play = True
        is_playing_backwards = False
        while True:
            try:
                if is_play:
                    frame_index = int(self._vs.get(cv2.CAP_PROP_POS_FRAMES))
                    if is_playing_backwards:
                        frame_index -= 2
                    if 0 <= frame_index < self._frame_count:
                        self._vs.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                        success, frame = self._vs.read()
                        if success:
                            frame = self._draw_frame(frame, frame_index)
                            cv2.imshow('Video Player', frame)
                    is_play = False
                key = cv2.waitKey(50) & 0xFF
                if key == ord('q'):
                    break
                if key == ord('n'):
                    is_play = True
                    is_playing_backwards = False
                elif key == ord('p'):
                    is_play = True
                    is_playing_backwards = True
            except KeyboardInterrupt:
                break
        self._vs.release()
        cv2.destroyAllWindows()

    def _draw_frame(self, frame, frame_index):
        image = PIL.Image.fromarray(frame)
        draw = PIL.ImageDraw.Draw(image, 'RGBA')
        frame_text = get_frame_text(frame_index, self._frame_count)
        draw_text_box(draw, frame_text, self._font)
        return numpy.asarray(image)


def get_frame_text(frame_index, frame_count):
    return '{frame_num:0>{digits}}/{frame_count}'.format(
        frame_num=frame_index + 1,
        digits=int(numpy.log10(frame_count)) + 1,
        frame_count=frame_count)


def draw_text_box(draw, text, font):
    offset_x, offset_y = font.getoffset(text)
    w, h = draw.textsize(text, font)
    draw.rectangle(
        (4, 4, w + offset_x + 16, h + offset_y + 8),
        fill=(0, 0, 0, 150))
    draw.text((12, 8), text, font=font)


def parse_arguments():
    resources: Path = Path(__file__).parent / 'resources'
    parser = argparse.ArgumentParser(
        description=' '.join((
            'Play video file frame by frame.',
            'Press n for next frame, p for previous frame and q to quit.',
        )))
    parser.add_argument('file', type=Path, nargs='?',
                        help="Path to video file.")
    parser.add_argument('--font',
                        type=Path,
                        default=resources / 'Roboto-Regular.ttf',
                        help="Font used in image annotations.")
    parser.add_argument('--fontSize',
                        type=int,
                        default=30,
                        help="Font size used in image annotations.")
    args = parser.parse_args()
    assert 'DISPLAY' in os.environ
    return args


def main():
    args = parse_arguments()
    if args.file is None:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        args.file = filedialog.askopenfilename(title='Select input file')
        if not args.file:
            exit(0)
    file = Path(args.file)
    font = PIL.ImageFont.truetype(str(args.font), args.fontSize)
    VideoFramePlayer(file, font).run()


if __name__ == '__main__':
    main()
