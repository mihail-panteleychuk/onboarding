from .models import Country
from django.contrib.gis.geoip2 import GeoIP2


def detect_country_by_ip(request):
    """
    Detecting request country by customer IP
    """
    g = GeoIP2()
    ip = request.META.get('HTTP_X_FORWARDED_FOR')
    if not ip:
        return None
    country = g.country(ip.split(',')[0])
    country = Country.objects.filter(name=country['country_name']).first()
    return country
