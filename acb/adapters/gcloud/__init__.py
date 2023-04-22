from addict import Dict as adict
from ...config import AppSettings


class GoogleSettings(AppSettings):
    project = ac.app.project
    location = "us-central1"
    user_project: str = ac.app.name
    service_account: str = ac.secrets.google_service_account
    service_account_json: str = ac.secrets.google_service_account_json
    upload_json: str = ac.secrets.google_upload_json
    maps_api_key: str = ac.secrets.google_maps_api_key
    maps_dev_api_key: str = ac.secrets.google_maps_dev_api_key
    tasks_api_scope = "https://www.googleapis.com/auth/tasks"
    fonts = adict(primary="Poppins", secondary="Poppins", effects="3d-float")
