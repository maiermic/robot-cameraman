from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import FreeTypeFont

from robot_cameraman.box import Point


class PilTranslate:
    def __init__(self, offset: Point) -> None:
        self._offset = offset

    def translate_xy(self, xy):
        x, y = xy
        return (x + self._offset.x,
                y + self._offset.y)

    def translate_xy2(self, xy):
        x1, y1, x2, y2 = xy
        return (x1 + self._offset.x,
                y1 + self._offset.y,
                x2 + self._offset.x,
                y2 + self._offset.y)

    def translate_x(self, x):
        return x + self._offset.x

    def translate_y(self, y):
        return y + self._offset.y


class NumberLine:

    def __init__(
            self,
            position: Point,
            width: int,
            tick_height: int,
            stop: int,
            start: int,
            step: int = 1,
            show_half_ticks=False) -> None:
        self._width = width
        self._tick_height = tick_height
        self._start = start
        self._stop = stop
        self._step = step
        self._tick_count = abs(stop - start)
        self._tick_distance = self._width / self._tick_count
        self._show_half_ticks = show_half_ticks
        self._translate = PilTranslate(offset=position)

    def draw(
            self,
            draw: ImageDraw,
            font: FreeTypeFont):
        # Draw a horizontal number line with 0 in the center of the image
        draw.line(
            self._translate.translate_xy2(
                (0, self._tick_height, self._width, self._tick_height)),
            fill='black',
            width=2)

        # Draw ticks and numbers on the number line
        label_y = self._tick_height + 5
        for x in range(self._start, self._stop + 1, self._step):
            x_pos = self._get_tick_x(x)
            draw.line(
                self._translate.translate_xy2(
                    (x_pos, 0, x_pos, self._tick_height)),
                fill='black',
                width=2)
            if self._show_half_ticks:
                half_tick_x = x + self._step / 2
                if half_tick_x < self._stop:
                    half_tick_x = self._get_tick_x(half_tick_x)
                    draw.line(
                        self._translate.translate_xy2(
                            (half_tick_x,
                             self._tick_height // 2,
                             half_tick_x,
                             self._tick_height)),
                        fill='black',
                        width=2)
            label = str(x)
            label_width, label_height = draw.textbbox(
                (0, 0), label, font=font)[2:]
            draw.text(
                self._translate.translate_xy(
                    (x_pos - label_width // 2, label_y)),
                text=label,
                fill='black',
                font=font)

    def _get_tick_x(self, x):
        return abs(self._start - x) * self._tick_distance

    def get_tick_x(self, x):
        return self._translate.translate_x(self._get_tick_x(x))
