import secrets
from datetime import datetime, timedelta


def generate_token():
    return "ibs_{}".format(secrets.token_urlsafe(48))


def token_expiration():
    return datetime.now() + timedelta(days=30)
