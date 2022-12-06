import json
from pathlib import Path


def read_configuration_file(file: Path):
    if file.exists():
        with open(file) as file_descriptor:
            return json.load(file_descriptor)
    initial_configuration = {
        'tracking': {
            'color': {
                'is_single_object_detection': True,
                'min_hsv': [69, 30, 114],
                'max_hsv': [100, 255, 255],
            }
        }
    }
    save_configuration_file(file, initial_configuration)
    return initial_configuration


def save_configuration_file(file: Path, configuration):
    with open(file, 'w') as file_descriptor:
        json.dump(configuration, file_descriptor, indent=2)


def update_configuration_file(file: Path, update: callable):
    configuration = read_configuration_file(file)
    save_configuration_file(file, update(configuration))
