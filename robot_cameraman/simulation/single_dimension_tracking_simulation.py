# Import the Image and ImageDraw libraries from the PIL package
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import Tk

import cv2
import numpy
from PIL import Image, ImageDraw, ImageFont
from typing_extensions import Protocol

from robot_cameraman.annotation import draw_point
from robot_cameraman.box import Point, Box
from robot_cameraman.draw import NumberLine


class TargetSpeedUpdater(Protocol):
    def update_target_speed(self, current_speed: float,
                            distance: float) -> float:
        pass


class SimpleTargetSpeedUpdater(TargetSpeedUpdater):
    def update_target_speed(self, current_speed: float,
                            distance: float) -> float:
        return -distance


class RelativeTargetSpeedUpdater(TargetSpeedUpdater):
    _previous_distance = None

    def update_target_speed(self, current_speed, distance) -> float:
        if self._previous_distance is None:
            self._previous_distance = distance
            return current_speed
        delta_distance = self._previous_distance - distance
        self._previous_distance = distance
        return delta_distance - distance


@dataclass
class Target:
    x: float
    speed: float


@dataclass
class Camera:
    x: float
    speed: float
    acceleration: float
    image_width: float


class Simulator:
    def __init__(
            self,
            target_speed_updater: TargetSpeedUpdater,
            target: Target,
            camera: Camera):
        self._target_speed_updater = target_speed_updater
        self.target = target
        self.camera = camera
        self.target_history = deque(maxlen=3)
        self.camera_history = deque(maxlen=3)
        self.distance_history = deque(maxlen=3)

    def update(self):
        self.distance_history.append(self.get_distance())
        self.target_history.append(self.target.x)
        self.camera_history.append(self.camera.x)

        target_speed = self._target_speed_updater.update_target_speed(
            current_speed=self.camera.speed, distance=self.get_distance())
        if target_speed > self.camera.speed:
            self.camera.speed = min(
                self.camera.speed + self.camera.acceleration,
                target_speed)
        elif target_speed < self.camera.speed:
            self.camera.speed = max(
                self.camera.speed - self.camera.acceleration,
                target_speed)
        self.camera.x += self.camera.speed
        self.target.x += self.target.speed

    def get_distance(self):
        return self.camera.x - self.target.x


class SimulatorRenderer:
    def __init__(self, simulator: Simulator):
        self._simulator = simulator
        root = Tk()
        screen_width = root.winfo_screenwidth()
        root.destroy()

        self._border = 30
        drawing_area_height = 300
        self._image_width = screen_width
        self._image_height = drawing_area_height + 2 * self._border
        self._drawing_area = Box.from_center_and_size(
            center=Point(x=self._image_width // 2,
                         y=self._image_height // 2),
            width=screen_width - 2 * self._border,
            height=drawing_area_height)
        self._image = Image.new(
            'RGB',
            (self._image_width, self._image_height),
            color='white')
        resources = Path(__file__).parent.parent / 'resources'
        self._font = ImageFont.truetype(
            font=str(resources / 'Roboto-Regular.ttf'),
            size=26)

        self._world_number_line_position = Point(
            x=self._drawing_area.x,
            y=self._drawing_area.center.y - 40)
        self._world_number_line = NumberLine(
            position=self._world_number_line_position,
            width=self._drawing_area.width,
            tick_height=10,
            show_half_ticks=True,
            start=-100,
            stop=100,
            step=10)
        self._world_number_line.draw(draw=ImageDraw.Draw(self._image),
                                     font=self._font)

        self._number_line_position = Point(
            x=self._drawing_area.x,
            y=self._drawing_area.y + self._drawing_area.height - 40)
        self._distance_number_line = NumberLine(
            position=self._number_line_position,
            width=self._drawing_area.width,
            tick_height=10,
            start=-20,
            stop=20)
        self._distance_number_line.draw(draw=ImageDraw.Draw(self._image),
                                        font=self._font)

    def get_x_pos_of_distance(self, distance):
        return self._distance_number_line.get_tick_x(distance)

    def render(self) -> Image:
        result = self._image.copy()
        draw = ImageDraw.Draw(result, 'RGBA')

        target_radius = 14
        self._draw_world_x(
            draw=draw,
            x=self._simulator.target.x,
            fill=(0, 200, 0),
            radius=target_radius)
        self._draw_world_x_history(
            draw,
            self._simulator.target_history,
            outline=(0, 200, 0),
            radius=target_radius)

        camera_radius = 10
        self._draw_world_x(
            draw=draw,
            x=self._simulator.camera.x,
            fill=(255, 0, 255),
            radius=camera_radius)
        self._draw_world_x_history(
            draw,
            self._simulator.camera_history,
            outline=(204, 0, 255),
            radius=camera_radius)

        self._draw_distances(draw)
        return result

    def _draw_world_x_history(self, draw, history: deque, outline, radius):
        history_length = len(history)
        for i, d in enumerate(history, start=1):
            alpha = int(i * 255 / history_length)
            self._draw_world_x(
                draw, d, outline=(*outline, alpha), radius=radius)

    def _draw_world_x(
            self,
            draw: ImageDraw,
            x,
            fill=None,
            outline=None,
            radius=15):
        x = self._world_number_line.get_tick_x(x)
        y = self._world_number_line_position.y - 20
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=fill,
            outline=outline,
            width=4)

    def _draw_distances(self, draw: ImageDraw):
        self._draw_distance(
            draw, self._simulator.target.speed, color=(0, 200, 0))
        distance = self._simulator.get_distance()
        self._draw_distance(draw, distance, color=(255, 0, 255))
        history_length = len(self._simulator.distance_history)
        for i, d in enumerate(self._simulator.distance_history, start=1):
            alpha = int(i * 255 / history_length)
            self._draw_distance_circle(draw, d, color=(204, 0, 255, alpha))

    def _draw_distance(self, draw, distance, color):
        x_pos = self.get_x_pos_of_distance(distance)
        radius = 15
        draw_point(
            draw,
            Point(x_pos, self._number_line_position.y - 5 - radius),
            color=color,
            radius=radius)

    def _draw_distance_circle(self, draw, distance, color):
        radius = 15
        x = self.get_x_pos_of_distance(distance)
        y = self._number_line_position.y - 5 - radius
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=color, width=4)


class SimulatorUi:
    def __init__(self, simulator: Simulator):
        self._simulator = simulator
        self._simulator_renderer = SimulatorRenderer(simulator)
        self._is_refresh_required = True
        self._window_title = '1D Simulator'

    def run(self):
        cv2.namedWindow(self._window_title, cv2.WINDOW_NORMAL)
        while True:
            if self._is_refresh_required:
                self.render()
                self._is_refresh_required = False
            key = cv2.waitKey(5) & 0xFF
            if key == ord('q'):
                break
            if key == ord('l'):
                self._simulator.target.speed += 1
                self._is_refresh_required = True
            if key == ord('j'):
                self._simulator.target.speed -= 1
                self._is_refresh_required = True
            if key == ord('n'):
                self.update()
                self._is_refresh_required = True

        cv2.destroyAllWindows()

    def update(self):
        self._simulator.update()

    def render(self):
        image = self._simulator_renderer.render()
        # noinspection PyTypeChecker
        cv2_image = cv2.cvtColor(numpy.asarray(image),
                                 cv2.COLOR_RGB2BGR)
        cv2.imshow(self._window_title, cv2_image)
        cv2.displayStatusBar(self._window_title, ', '.join((
            f'camera speed: {self._simulator.camera.speed}',
            f'target speed: {self._simulator.target.speed}',
            f'distance: {self._simulator.get_distance()}',
        )))


def main():
    # simulator_renderer = SimulatorRenderer()
    # # Show the image
    # simulator_renderer.render().show()

    # target_speed_updater = SimpleTargetSpeedUpdater()
    target_speed_updater = RelativeTargetSpeedUpdater()
    simulator = Simulator(
        target_speed_updater=target_speed_updater,
        target=Target(x=0, speed=0),
        camera=Camera(
            x=10,
            speed=0,
            acceleration=1,
            image_width=10))
    simulator_ui = SimulatorUi(simulator)
    simulator_ui.run()


if __name__ == '__main__':
    main()
