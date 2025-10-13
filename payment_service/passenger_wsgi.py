import sys, os

# Adjust path if necessary
project_home = '/home/yourusername/payment_service'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

os.environ['DJANGO_SETTINGS_MODULE'] = 'payment_service.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
