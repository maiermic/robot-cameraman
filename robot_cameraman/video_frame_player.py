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


def main(file, font):
    vs = cv2.VideoCapture(str(file))
    frame_count = int(vs.get(cv2.CAP_PROP_FRAME_COUNT))
    is_play = True
    is_playing_backwards = False
    while True:
        try:
            if is_play:
                frame_index = int(vs.get(cv2.CAP_PROP_POS_FRAMES))
                if is_playing_backwards:
                    frame_index -= 2
                if 0 <= frame_index < frame_count:
                    vs.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    success, frame = vs.read()
                    if success:
                        image = PIL.Image.fromarray(frame)
                        draw = PIL.ImageDraw.Draw(image, 'RGBA')
                        frame_text = f'{{:0>{3}}}/{{}}'.format(frame_index + 1,
                                                               frame_count)
                        offset_x, offset_y = font.getoffset(frame_text)
                        w, h = draw.textsize(frame_text, font)
                        draw.rectangle((4, 4, w + offset_x + 16, h + offset_y + 8),
                                       fill=(0, 0, 0, 150))
                        draw.text((12, 8), frame_text, font=font)
                        frame = numpy.asarray(image)
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
    vs.release()
    cv2.destroyAllWindows()


def parse_arguments():
    resources: Path = Path(__file__).parent / 'resources'
    parser = argparse.ArgumentParser(
        description="Play video file frame by frame. Press n for next frame and p for previous frame")
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


if __name__ == '__main__':
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
    assert file.exists()
    main(file, PIL.ImageFont.truetype(str(args.font), args.fontSize))
