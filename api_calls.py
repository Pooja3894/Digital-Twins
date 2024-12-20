# Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import time

import requests
from celery import states
from geopandas import GeoDataFrame

"""A script to help guide people in how to use the APIs. Just for documentation and reference"""

# You must have the celery worker running to use most of these API endpoints
# (any that are marked with @check_celery_active in app.py)

# Set backend url to point at backend.
# This may be a different host than localhost if you are trying to reach the server from an external source
backend_url = "http://localhost:5000"


def perform_health_check():
    # Run health-check - to verify if backend server is running,
    health_check_response = requests.get(f"{backend_url}/health-check")
    # This health_check will respond in one of 3 ways.
    # Either 200: Healthy, 600: Celery workers are not active,
    # or it will not respond with either of these if there is a problem with the server
    print(f"Status: {health_check_response.status_code}, body: {health_check_response.text}")
    # Raises error if the status is not 200
    health_check_response.raise_for_status()


def generate_flood_model() -> str:
    # Create request data for getting flood model data from a region over Kaiapoi
    request_data = {
        "bbox": {
            "lat1": -43.370613130921434,
            "lng1": 172.65156000179044,
            "lng2": 172.71678302522903,
            "lat2": -43.400136655560765
        },
        "scenarioOptions": {
            "projectedYear": 2050,
            "sspScenario": "SSP2-4.5",
            "confidenceLevel": "medium",
            "addVerticalLandMovement": True,
            "percentile": 50
        }
    }
    print(f"Requesting backend to generate flood model for {request_data}")
    generate_model_response = requests.post(f"{backend_url}/models/generate", json=request_data)
    # Check for errors (400/500 codes)
    generate_model_response.raise_for_status()
    # Load the body JSON into a python dict
    response_body = json.loads(generate_model_response.text)
    # Read the task id
    return response_body["taskId"]


def poll_for_completion(task_id: str) -> int:
    """Returns task value of completed task e.g. generate model task -> model output id"""
    # Retry forever until the task is complete
    task_status = None
    while task_status != states.SUCCESS:
        # 5 Second delay before retrying
        time.sleep(5)
        print("Polling backend for task completion...")
        # Get status of a task
        task_status_response = requests.get(f"{backend_url}/tasks/{task_id}")
        response_body = task_status_response.json()
        print(response_body)
        task_status_response.raise_for_status()
        # Load the body JSON into a python dict
        task_status = response_body["taskStatus"]
    task_value = response_body['taskValue']
    print(f"Task completed with value {task_value}")
    return task_value


def get_building_statuses(model_id: int) -> GeoDataFrame:
    # Retrieve building statuses
    building_response = requests.get(f"{backend_url}/models/{model_id}/buildings")
    # Check for errors (400/500 codes)
    building_response.raise_for_status()
    # Read response GeoJSON into python dict
    building_json = building_response.json()
    # Build gdf from GeoJSON Features
    return GeoDataFrame.from_features(building_json["features"])


def get_depths_at_point(task_id: str):
    point = {"lat": -43.39, "lng": 172.65}
    # Send a request to get the depths at a point for a flood model associated with a task
    print(f"requesting depths for point {point}")
    depths_response = requests.get(f"{backend_url}/tasks/{task_id}/model/depth", params=point)

    # Check for errors (400/500 codes)
    depths_response.raise_for_status()
    # Load the body JSON into a python dict
    response_body = depths_response.json()
    print(response_body)


def fetch_new_dataset_table():
    # Update LiDAR datasets, takes a long time.
    print("Refreshing LiDAR OpenTopography URLs to get newest LiDAR data")
    update_datasets_response = requests.post(f"{backend_url}/datasets/update")
    # Check for errors (400/500 codes)
    update_datasets_response.raise_for_status()
    # Load the body JSON into a python dict
    response_body = json.loads(update_datasets_response.text)
    # Read the task id
    return response_body["taskId"]


def stop_task(task_id: str):
    # Send a request to stop the task
    requests.delete(f"{backend_url}/tasks/{task_id}")


def main():
    perform_health_check()
    flood_generation_task_id = generate_flood_model()
    model_output_id = poll_for_completion(flood_generation_task_id)
    get_building_statuses(model_output_id)
    get_depths_at_point(flood_generation_task_id)


if __name__ == '__main__':
    main()
