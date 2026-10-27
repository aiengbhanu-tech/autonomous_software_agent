def file_extension(filename):
    return filename.split('.')[-1].lower() if '.' in filename else ''
