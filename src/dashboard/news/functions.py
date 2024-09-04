

def chunk_list(l: list, size: int):
    result = []
    for i in range(0, len(l), size):
        result.append(l[i:i + size])
    return result