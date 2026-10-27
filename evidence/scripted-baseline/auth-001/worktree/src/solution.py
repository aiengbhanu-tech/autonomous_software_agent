def authentication_status(password):
    return 200 if len(password.encode('utf-8')) <= 72 else 422
