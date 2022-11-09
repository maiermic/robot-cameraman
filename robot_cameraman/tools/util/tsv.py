from dataclasses import fields
from typing import Dict


def print_data_class_tsv(class_or_instance, instances, formats: Dict[str, str]):
    tsv = DataClassTsv(class_or_instance, formats)
    print(tsv.header())
    for instance in instances:
        print(tsv.row(instance))


class DataClassTsv:
    def __init__(self, class_or_instance, formats: Dict[str, str]) -> None:
        self._field_names = [field.name for field in fields(class_or_instance)]
        self._field_names += [
            p for p in dir(class_or_instance)
            if isinstance(getattr(class_or_instance, p), property)]
        self._formats = formats

    def header(self) -> str:
        return '\t'.join(self._field_names)

    def row(self, instance) -> str:
        columns = (self._format_field(instance, f) for f in self._field_names)
        return '\t'.join(columns)

    def _format_field(self, instance, name: str):
        value = getattr(instance, name)
        if value is None:
            return (' ' * (len(name) - 1)) + '-'
        if name in self._formats:
            return f'{value:{self._formats[name]}}'
        return f'{value:{len(name)}}'


def print_tsv_row(row):
    print('\t'.join(map(str, row)))
