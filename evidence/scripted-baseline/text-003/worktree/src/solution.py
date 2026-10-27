def remove_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text
