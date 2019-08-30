import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict
from urllib.parse import urlparse

import requests

from panasonic_camera.discover import discover_panasonic_camera_devices


class RejectError(Exception):
    pass


class BusyError(Exception):
    pass


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


class PanasonicCamera:

    def __init__(self, hostname: str) -> None:
        self.cam_cgi_url = 'http://{}/cam.cgi'.format(hostname)

    @staticmethod
    def _validate_camrply(camrply: ET.Element) -> None:
        assert camrply.tag == 'camrply'
        result = camrply.find('result').text
        if result == 'err_reject':
            raise RejectError
        elif result == 'err_busy':
            raise BusyError
        assert result == 'ok', 'unknown result "{}"'.format(result)

    def _request(self, *args, **kwargs) -> ET.Element:
        kwargs.setdefault('timeout', 2)
        response = requests.get(self.cam_cgi_url, *args, **kwargs)
        camrply: ET.Element = ET.fromstring(response.text)
        self._validate_camrply(camrply)
        return camrply

    def get_state(self) -> State:
        camrply: ET.Element = self._request(params={'mode': 'getstate'})
        state = camrply.find('state')
        return State(
            batt=state.find('batt').text,
            cammode=state.find('cammode').text,
            sdcardstatus=state.find('sdcardstatus').text,
            sd_memory=state.find('sd_memory').text,
            sd_access=state.find('sd_access').text,
            version=state.find('version').text)

    def _camcmd(self, value: str) -> None:
        self._request(params={'mode': 'camcmd', 'value': value})

    def recmode(self) -> None:
        self._camcmd('recmode')

    def playmode(self) -> None:
        self._camcmd('playmode')

    def video_recstart(self) -> None:
        self._camcmd('video_recstart')

    def _get_info(self, info_type: str) -> ET.Element:
        return self._request(params={'mode': 'getinfo', 'type': info_type})

    def get_info_capability(self) -> Capability:
        camrply: ET.Element = self._get_info('capability')
        # print(ET.tostring(camrply, encoding='utf8', method='xml').decode())
        # print(generate_class('Capability', camrply))
        return Capability(
            comm_proto_ver=camrply.find('comm_proto_ver').text,
            product_info=ProductInfo(
                camrply.find('productinfo/modelname').text),
            commands=[e.text for e in camrply.findall('camcmdlist/camcmd')],
            controls=[e.text for e in camrply.findall('camctrllist/camctrl')],
            settings={e.tag: Setting(current_value=e.find('curvalue').text,
                                     values=e.find('valuelist').text.split(','))
                      for e in list(camrply.find('settinglist'))},
            states=[e.text for e in camrply.findall('getstatelist/getstate')],
            specifications=[e.text for e in
                            camrply.findall('camspeclist/camspec')])

    def start_stream(self, port=49199):
        return self._request(
            params={'mode': 'startstream', 'value': port})

    def stop_stream(self):
        return self._request(
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
        constructor_body = 'pass'
    else:
        constructor_body = '\n        '.join(constructor_body)
    return """\
class {name}:
    def __init__(
            {constructor_parameter_list}):
        {constructor_body}
""".format(
        name=name,
        constructor_parameter_list=',\n            '.join(parameter),
        constructor_body=constructor_body)


if __name__ == '__main__':
    from pprint import pprint

    devices = discover_panasonic_camera_devices()
    device = devices[0]
    camera = PanasonicCamera(urlparse(device.location).hostname)
    pprint(camera.get_state())
    pprint(camera.get_info_capability().__dict__)
