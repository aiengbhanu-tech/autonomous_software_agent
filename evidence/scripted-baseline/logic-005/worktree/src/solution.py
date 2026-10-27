def can_write(active, role):
    return active and role in ['admin', 'editor']
