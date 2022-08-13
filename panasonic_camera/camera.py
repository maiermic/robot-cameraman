import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Iterator, Optional
from urllib.parse import urlparse

import requests

from panasonic_camera.discover import discover_panasonic_camera_devices


class RejectError(Exception):
    pass


class BusyError(Exception):
    pass


class CriticalError(Exception):
    pass


class UnsuitableApp(Exception):
    def __init__(self, *args) -> None:
        self.message = ("Camera replied 'unsuitable_app'. If this camera is"
                        " DC-FZ80 or similar, you probably need to specify the "
                        "identifyAs parameter so that an accctl request will be"
                        " sent.")
        super().__init__(self.message)


@dataclass
class State:
    batt: str
    cammode: str
    sdcardstatus: str
    sd_memory: str
    sd_access: str
    version: str


@dataclass
class ProductInfo:
    model_name: str


@dataclass
class Setting:
    current_value: str
    values: List[str]


@dataclass
class Capability:
    comm_proto_ver: str
    product_info: ProductInfo
    commands: List[str]
    controls: List[str]
    settings: Dict[str, Setting]
    states: List[str]
    specifications: List[str]


def find_text(element: Optional[ET.Element],
              path: str,
              default: str = '') -> str:
    if element is None:
        return default
    e = element.find(path)
    return default if e is None else str(e.text)


def find_all_text(element: ET.Element, path: str) -> List[str]:
    return [str(e.text) for e in element.findall(path)]


def find_elements(element: ET.Element, path: str) -> Iterator[ET.Element]:
    elements = element.find(path)
    if elements is not None:
        for e in list(elements):
            if e is not None:
                yield e


class PanasonicCamera:

    def __init__(self, hostname: str) -> None:
        self.cam_cgi_url = 'http://{}/cam.cgi'.format(hostname)

    @staticmethod
    def _validate_camrply(camrply: ET.Element) -> None:
        assert camrply.tag == 'camrply'
        result = find_text(camrply, 'result')
        if result == 'err_reject':
            raise RejectError(result)
        elif result == 'err_busy':
            raise BusyError(result)
        elif result == 'err_critical':
            raise CriticalError(result)
        elif result == 'err_unsuitable_app':
            raise UnsuitableApp(result)
        assert result == 'ok', 'unknown result "{}"'.format(result)

    def _request_xml(self, *args, **kwargs) -> ET.Element:
        kwargs.setdefault('timeout', 2)
        response = requests.get(self.cam_cgi_url, *args, **kwargs)
        camrply: ET.Element = ET.fromstring(response.text)
        self._validate_camrply(camrply)
        return camrply

    def _request_csv(self, *args, **kwargs) -> List[str]:
        kwargs.setdefault('timeout', 2)
        response = requests.get(self.cam_cgi_url, *args, **kwargs)
        camrply: List[str] = response.text.split(',')
        return camrply

    def get_state(self) -> State:
        camrply: ET.Element = self._request_xml(params={'mode': 'getstate'})
        state = camrply.find('state')
        return State(
            batt=find_text(state, 'batt'),
            cammode=find_text(state, 'cammode'),
            sdcardstatus=find_text(state, 'sdcardstatus'),
            sd_memory=find_text(state, 'sd_memory'),
            sd_access=find_text(state, 'sd_access'),
            version=find_text(state, 'version'))

    def _camcmd(self, value: str) -> None:
        self._request_xml(params={'mode': 'camcmd', 'value': value})

    def recmode(self) -> None:
        self._camcmd('recmode')

    def playmode(self) -> None:
        self._camcmd('playmode')

    def video_recstart(self) -> None:
        self._camcmd('video_recstart')

    def video_recstop(self) -> None:
        self._camcmd('video_recstop')

    def zoom_stop(self) -> None:
        self._camcmd('zoomstop')

    def zoom_in_slow(self) -> None:
        self._camcmd('tele-normal')

    def zoom_in_fast(self) -> None:
        self._camcmd('tele-fast')

    def zoom_out_slow(self) -> None:
        self._camcmd('wide-normal')

    def zoom_out_fast(self) -> None:
        self._camcmd('wide-fast')

    def _get_info(self, info_type: str) -> ET.Element:
        return self._request_xml(params={'mode': 'getinfo', 'type': info_type})

    def get_info_capability(self) -> Capability:
        camrply: ET.Element = self._get_info('capability')
        # print(ET.tostring(camrply, encoding='utf8', method='xml').decode())
        # print(generate_class('Capability', camrply))
        settings: Dict[str, Setting] = {
            e.tag: Setting(current_value=find_text(e, 'curvalue'),
                           values=find_text(e, 'valuelist').split(','))
            for e in find_elements(camrply, 'settinglist')
        }
        return Capability(
            comm_proto_ver=find_text(camrply, 'comm_proto_ver'),
            product_info=ProductInfo(
                model_name=find_text(camrply, 'productinfo/modelname')),
            commands=find_all_text(camrply, 'camcmdlist/camcmd'),
            controls=find_all_text(camrply, 'camctrllist/camctrl'),
            settings=settings,
            states=find_all_text(camrply, 'getstatelist/getstate'),
            specifications=find_all_text(camrply, 'camspeclist/camspec'))

    def register_with_camera(self, identify_as: str):
        # Cameras like the DC-FZ80 keep a list of devices that remote
        # control them. This request adds the current device to the list with
        # a name specified by device_name.
        return self._request_csv(
            params={
                'mode': 'accctrl',
                'type': 'req_acc',
                'value': '0',
                'value2': identify_as
            })

    def start_stream(self, port=49199):
        return self._request_xml(
            params={'mode': 'startstream', 'value': port})

    def stop_stream(self):
        return self._request_xml(
            params={'mode': 'stopstream'})


def generate_class(name, xml_element: ET.Element):
    parameter = ['self']
    constructor_body = []
    child: ET.Element
    for child in xml_element:
        parameter_name: str = child.tag
        parameter_type = None
        if not list(child):
            parameter_type = 'str'
        elif parameter_name.endswith('list'):
            parameter_type = parameter_name[0].upper() + parameter_name[1:-4]
        if parameter_type:
            parameter.append('{}: {}'.format(parameter_name, parameter_type))
        else:
            parameter.append(parameter_name)
        constructor_body.append('self.{0} = {0}'.format(parameter_name))
    if len(parameter) == 1:
        constructor_body_str = 'pass'
    else:
        constructor_body_str = '\n        '.join(constructor_body)
    return """\
class {name}:
    def __init__(
            {constructor_parameter_list}):
        {constructor_body}
""".format(
        name=name,
        constructor_parameter_list=',\n            '.join(parameter),
        constructor_body=constructor_body_str)


if __name__ == '__main__':
    from pprint import pprint

    devices = discover_panasonic_camera_devices()
    for device in devices:
        print(device)
        camera = PanasonicCamera(urlparse(device.location).hostname)
        pprint(camera.get_state())
        pprint(camera.get_info_capability().__dict__)
