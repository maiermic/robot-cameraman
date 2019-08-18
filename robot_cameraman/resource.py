# Read labels from text files.
def read_label_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
        ret = {}
    for line in lines:
        pair = line.strip().split(maxsplit=1)
        ret[int(pair[0])] = pair[1].strip()
    return ret
