from typing import List

import upnpclient


def is_panasonic_camera(device: upnpclient.Device):
    return (device.manufacturer == 'Panasonic'
            and device.model_name in ('LUMIX', 'Video Camera'))


def discover_panasonic_camera_devices(timeout=1) -> List[upnpclient.Device]:
    return list(filter(is_panasonic_camera, upnpclient.discover(timeout)))


if __name__ == '__main__':
    from pprint import pprint

    pprint(discover_panasonic_camera_devices())
