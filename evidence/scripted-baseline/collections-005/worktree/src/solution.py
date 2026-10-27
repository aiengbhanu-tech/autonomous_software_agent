def rotate_left(items, amount):
    return items[amount % len(items):] + items[:amount % len(items)] if items else []
