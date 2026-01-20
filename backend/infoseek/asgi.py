"""
ASGI config for infoseek project.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'infoseek.settings')

application = get_asgi_application()

