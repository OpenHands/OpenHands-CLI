from openhands.workspace import OpenHandsCloudWorkspace
import os

workspace = OpenHandsCloudWorkspace(
    cloud_api_url="https://app.all-hands.dev",
    cloud_api_key=os.getenv("OH_API_KEY", ""),
    keep_alive=True,
    sandbox_id=sandbox_id,
)