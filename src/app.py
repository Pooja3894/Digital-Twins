# -*- coding: utf-8 -*-
"""The main web application that serves the Digital Twin to the web through a Rest API."""

import logging
import pathlib
from functools import wraps
from http.client import OK, ACCEPTED, BAD_REQUEST, INTERNAL_SERVER_ERROR, NOT_FOUND, SERVICE_UNAVAILABLE
from typing import Callable, Dict, Tuple

import requests
from celery import result, states
from flask import Flask, Response, jsonify, make_response, send_file, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from kombu.exceptions import OperationalError
from shapely import box

from src import tasks
from src.config import EnvVariable

# Initialise flask server object
app = Flask(__name__)
CORS(app)


def check_celery_alive(f: Callable[..., Response]) -> Callable[..., Response]:
    """
    Check if the Celery workers are running and return INTERNAL_SERVER_ERROR if they are down using function decorator.

    Parameters
    ----------
    f : Callable[..., Response]
        The view function that is being decorated.

    Returns
    -------
    Callable[..., Response]
        Response is SERVICE_UNAVAILABLE if the celery workers are down, otherwise continue to function f
    """

    @wraps(f)
    def decorated_function(*args: Tuple, **kwargs: Dict) -> Response:
        """
        Before function `f` is called, check if Celery workers are down, and return and error response if so.
        If Celery workers are running, then continue with calling `f` with original arguments.

        Parameters
        ----------
        args : Tuple
            The original arguments for function `f`.
        kwargs : Dict
            The original keyword arguments for function `f`.

        Returns
        -------
        Response
            SERVICE_UNAVAILABLE if Celery workers are down, otherwise response from function `f`.
        """
        try:
            ping_celery_response = tasks.app.control.ping()
            if len(ping_celery_response) == 0:
                logging.warning("Celery workers not active, may indicate a fault")
                return make_response("Celery workers not active", SERVICE_UNAVAILABLE)
        except OperationalError:
            logging.warning("Celery workers not active, may indicate a fault")
            return make_response("Celery workers not active", SERVICE_UNAVAILABLE)
        return f(*args, **kwargs)

    return decorated_function


# Serve API documentation
SWAGGER_URL = "/swagger"
API_URL = "/static/api_documentation.yml"
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Flood Resilience Digital Twin (FReDT)"}
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)


@app.route('/')
def index() -> Response:
    """
    Ping this endpoint to check that the flask app is running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("""
    Backend is receiving requests.
    GET /health-check to check if celery workers active.
    GET /swagger to get API documentation.
    """, OK)


@app.route('/health-check')
@check_celery_alive
def health_check() -> Response:
    """
    Ping this endpoint to check that the server is up and running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("Healthy", OK)


@app.route('/tasks/<task_id>', methods=["GET"])
def get_status(task_id: str) -> Response:
    """
    Retrieve status of a particular Celery backend task.
    Supported methods: GET

    Parameters
    ----------
    task_id : str
        The id of the Celery task to retrieve status from

    Returns
    -------
    Response
        JSON response containing taskStatus
    """
    task_result = result.AsyncResult(task_id, app=tasks.app)
    status = task_result.status
    http_status = OK
    if status == states.SUCCESS:
        task_value = task_result.get()
    elif status == states.FAILURE:
        http_status = INTERNAL_SERVER_ERROR
        is_debug_mode = EnvVariable.DEBUG_TRACEBACK
        task_value = task_result.traceback if is_debug_mode else None
    else:
        task_value = None

    return make_response(jsonify({
        "taskId": task_result.id,
        "taskStatus": status,
        "taskValue": task_value
    }), http_status)


@app.route('/tasks/<task_id>', methods=["DELETE"])
def remove_task(task_id: str) -> Response:
    """
    Delete and stop a particular Celery backend task.
    Supported methods: DELETE

    Parameters
    ----------
    task_id : str
        The id of the Celery task to remove

    Returns
    -------
    Response
        ACCEPTED is the expected response
    """
    task_result = result.AsyncResult(task_id, app=tasks.app)
    task_result.revoke()
    return make_response("Task removed", ACCEPTED)


@app.route('/models/generate', methods=["POST"])
@check_celery_alive
def generate_model() -> Response:
    """
    Generate a flood model for a given area.
    Supported methods: POST
    POST values: {"bbox": {"lat1": number, "lat2": number, "lng1": number, "lng2": number}}

    Returns
    -------
    Response
        ACCEPTED is the expected response. Response body contains Celery taskId
    """
    try:
        bbox = request.get_json()["bbox"]
        lat1 = float(bbox.get("lat1"))
        lng1 = float(bbox.get("lng1"))
        lat2 = float(bbox.get("lat2"))
        lng2 = float(bbox.get("lng2"))
        scenario_options = request.get_json()["scenarioOptions"]
    except ValueError:
        return make_response(
            "JSON values for bbox: lat1, lng1, lat2, lng2 must be valid floats", BAD_REQUEST
        )
    if any(coord is None for coord in [lat1, lng1, lat2, lng2]):
        return make_response("JSON body parameters bbox: {lat1, lng1, lat2, lng2} mandatory", BAD_REQUEST)
    if not valid_coordinates(lat1, lng1) or not valid_coordinates(lat2, lng2):
        return make_response("lat & lng must fall in the range -90 < lat <= 90, -180 < lng <= 180", BAD_REQUEST)
    if (lat1, lng1) == (lat2, lng2):
        return make_response("lat1, lng1 must not equal lat2, lng2", BAD_REQUEST)

    bbox_wkt = create_wkt_from_coords(lat1, lng1, lat2, lng2)
    task = tasks.create_model_for_area(bbox_wkt, scenario_options)

    return make_response(
        jsonify({"taskId": task.id}),
        ACCEPTED
    )


def create_wkt_from_coords(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
    """
    Create a WKT bbox string from two points.

    Parameters
    ----------
    lat1 : float
        latitude of first point
    lng1: float
        longitude of first point
    lat2 : float
        latitude of second point
    lng2: float
        longitude of second point

    Returns
    -------
    str
        bbox in wkt form generated from the two coordinates
    """
    xmin = min([lng1, lng2])
    ymin = min([lat1, lat2])
    xmax = max([lng1, lng2])
    ymax = max([lat1, lat2])
    return box(xmin, ymin, xmax, ymax).wkt


@app.route('/tasks/<task_id>/model/depth', methods=["GET"])
@check_celery_alive
def get_depth_at_point(task_id: str) -> Response:
    """
    Find the depths and times at a particular point for a given completed model output task.
    Supported methods: GET
    Required query param values: "lat": float, "lng": float

    Parameters
    ----------
    task_id : str
        The id of the completed task for generating a flood model.

    Returns
    -------
    Response
        Returns JSON response in the form {"depth": Array<number>,  "time": Array<number>} representing the values
        for the given point.
    """
    try:
        lat = request.args.get("lat", type=float)
        lng = request.args.get("lng", type=float)
    except ValueError:
        return make_response("Query parameters lat & lng must be valid floats", BAD_REQUEST)
    if lat is None or lng is None:
        return make_response("Query parameters mandatory: lat & lng", BAD_REQUEST)
    if not valid_coordinates(lat, lng):
        return make_response("Query parameters lat & lng must fall in the range -90 < lat <= 90, -180 < lng <= 180",
                             BAD_REQUEST)
    model_task_result = result.AsyncResult(task_id, app=tasks.app)
    status = model_task_result.status
    if status != states.SUCCESS:
        response = make_response(f"Task {task_id} has status {status}, not {states.SUCCESS}", BAD_REQUEST)
        # Explicitly set content-type because task_id may make browsers visiting this endpoint vulnerable to XSS
        # For more info: SonarCloud RuleID pythonsecurity:S5131
        response.mimetype = "text/plain"
        return response

    model_id = model_task_result.get()
    depth_task = tasks.get_depth_by_time_at_point.delay(model_id, lat, lng)
    depths, times = depth_task.get()

    return make_response(jsonify({
        'depth': depths,
        'time': times
    }), OK)


@app.route('/scenarios/medusa/<int:scenario_id>', methods=["GET"])
@check_celery_alive
def get_rainfall_information(scenario_id: int) -> Response:
    """
    Find a list of parameters below at a particular point for a given completed model output task:
        - antecedent_dry_days
        - average_rain_intensity
        - event_duration
        - rainfall_ph

    Supported methods: GET
    Required query param values: "scenario_id": str

    Parameters
    ----------
    scenario_id: int
        The scenario ID of the pollution model run

    Returns
    -------
    Response
        Returns JSON response in the form below:
        {
            "antecedent_dry_days": int,
            "average_rain_intensity": int,
            "event_duration": int,
            "rainfall_ph": int
            "created_at": datetime.datetime,
            "geometry": polygon
        }
        representing the values for the given point.
    """  # noqa: D400
    # Get medusa rainfall information
    medusa_rainfall_dictionary = tasks.retrieve_medusa_input_parameters.delay(scenario_id).get()

    # Check if the scenario exists
    if medusa_rainfall_dictionary is None:
        return make_response(f"Could not find rainfall scenario {scenario_id}", NOT_FOUND)
    else:
        return make_response(jsonify(medusa_rainfall_dictionary), OK)


@app.route('/models/<int:model_id>/buildings', methods=["GET"])
@check_celery_alive
def retrieve_building_flood_status(model_id: int) -> Response:
    """
    Retrieve information on building flood status, for a given flood model output ID.
    It is recommended to use the geoserver API if it is possible, since this is a proxy around that.

    Parameters
    ----------
    model_id: int
        The ID of the flood output model to be queried

    Returns
    -------
    Response
        Returns GeoJSON building layer for the area of the flood model output.
        Has a property "is_flooded" to designate if a building is flooded in that scenario or not
    """
    # Set output crs argument from request args
    crs = request.args.get("crs", type=int, default=4326)

    try:
        # Get bounding box of model output to filter vector data to that area
        bbox = tasks.get_model_extents_bbox.delay(model_id).get()
    except FileNotFoundError:
        return make_response(f"Could not find flood model output {model_id}", NOT_FOUND)

    # Geoserver workspace is dependant on environment variables
    db_name = EnvVariable.POSTGRES_DB
    workspace_name = f"{db_name}-buildings"
    store_name = f"{db_name} PostGIS"
    # Set up geoserver request parameters
    geoserver_host = EnvVariable.GEOSERVER_HOST
    geoserver_port = EnvVariable.GEOSERVER_PORT
    request_url = f"{geoserver_host}:{geoserver_port}/geoserver/{workspace_name}/ows"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": f"{store_name}:building_flood_status",
        "outputFormat": "application/json",
        "srsName": f"EPSG:{crs}",  # Set output CRS
        "viewParams": f"scenario:{model_id}",  # Choose scenario for flooded_buildings
        "cql_filter": f"bbox(geometry,{bbox},'EPSG:2193')"  # Filter output to be only geometries inside the model bbox
    }
    # Request building statuses from geoserver
    geoserver_response = requests.get(request_url, params)
    # Serve those building statuses
    return Response(
        geoserver_response.text,
        status=geoserver_response.status_code,
        content_type=geoserver_response.headers['content-type']
    )


@app.route('/models/<int:model_id>', methods=['GET'])
@check_celery_alive
def serve_model_output(model_id: int) -> Response:
    """
    Serve the specified model output as a raw file.

    Parameters
    ----------
    model_id: int
        The ID of the model output to be served.

    Returns
    -------
    Response
        HTTP Response containing the model output file.
    """
    try:
        model_filepath = tasks.get_model_output_filepath_from_model_id.delay(model_id).get()
        return send_file(pathlib.Path(model_filepath))
    except FileNotFoundError:
        return make_response(f"Could not find flood model output {model_id}", NOT_FOUND)


@app.route('/datasets/update', methods=["POST"])
@check_celery_alive
def refresh_lidar_data_sources() -> Response:
    """
    Update LiDAR data sources to the most recent.
    Web-scrape OpenTopography metadata to update the datasets table containing links to LiDAR data sources.
    Takes a long time to run but needs to be run periodically so that the datasets are up to date.
    Supported methods: POST

    Returns
    -------
    Response
        ACCEPTED is the expected response. Response body contains Celery taskId
    """
    # Start task to refresh lidar datasets
    task = tasks.refresh_lidar_datasets.delay()
    # Return HTTP Response with task id so it can be monitored with get_status(taskId)
    return make_response(
        jsonify({"taskId": task.id}),
        ACCEPTED
    )


def valid_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate that coordinates are within the valid range of WGS84,
    (-90 < latitude <= 90) and (-180 < longitude <= 180).

    Parameters
    ----------
    latitude : float
        The latitude part of the coordinate
    longitude : float
        The longitude part of the coordinate

    Returns
    -------
    bool
        True if both latitude and longitude are within their valid ranges.
    """  # noqa: D400
    return (-90 < latitude <= 90) and (-180 < longitude <= 180)


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
