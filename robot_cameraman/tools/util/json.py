import dataclasses
import json


class DataclassDictJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return obj.__dict__
        # Base class default() raises TypeError:
        return json.JSONEncoder.default(self, obj)
