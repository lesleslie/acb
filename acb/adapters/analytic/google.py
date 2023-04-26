from addict import Dict as adict
from . import GoogleSettings


class AnalyticsSettings(GoogleSettings):
    view_id = None
    tracker = None
    measurement_id = None
    api_scope = "https://www.googleapis.com/auth/analytics.readonly"
    days_line = [30, 365]
    dimensions_table = [
        "region",
        "city",
        "mobileDeviceInfo",
        "screenResolution",
        "browser",
        "operatingSystem",
    ]
    universal = adict(tracker="UA-128993722-2", measurement_id="G-1TXCMM7BVP")


# def get_analytics_access_token():
#   return ServiceAccountCredentials.from_json_keyfile_name(
#       data() / 'splashstand-255421-4ab14a09d305.json',
#       'https://www.googleapis.com/auth/analytics.readonly').get_access_token().access_token

# creds = ServiceAccountCredentials.from_json().get_access_token().access_token
