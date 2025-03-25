#!/usr/bin/env python3
import argparse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import math
import logging
from typing import List, Dict
from flask import Flask, request
from werkzeug.exceptions import BadRequest
import redis
import time
from astropy import coordinates
from astropy import units
from astropy.time import Time
from geopy.geocoders import Nominatim


app = Flask(__name__)
redis_client = redis.Redis(host='redis-db', port=6379, db=0, decode_responses=True)
iss_data = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
logging.basicConfig(level=logging.DEBUG)



def speed(x_dot: float, y_dot: float, z_dot: float) -> float:
    """
    Calculates the speed of the object given their velocities in each direction
    :param x_dot: x velocity component of the x-axis
    :param y_dot:y velocity component of the y-axis
    :param z_dot:z velocity component of the z-axis
    :return:
    """
    try:
        return math.sqrt(x_dot * x_dot + y_dot * y_dot + z_dot * z_dot)
    except TypeError as e:
        raise ValueError

def process_data(url: str) -> None:
    """
    Takes url string (XML data) and extracts the useful information from it
    Useful information is epoch (changed format), x, y, z (positions), x_dot, y_dot, and z_dot (velocities)
    Stored in redis dataset
    :param url: website that we are getting data from
    :return: none
    """
    try:
        xml_data = requests.get(url)
        xml_data.raise_for_status()
        xml_data = xml_data.text
    except:
        logging.error("Failed to get data")
        raise TypeError

    root = ET.fromstring(xml_data)
    for state_vector in root.findall(".//stateVector"):
        epoch_str = str(state_vector.find("EPOCH").text)
        x = float(state_vector.find("X").text)
        y = float(state_vector.find("Y").text)
        z = float(state_vector.find("Z").text)
        x_dot = float(state_vector.find("X_DOT").text)
        y_dot = float(state_vector.find("Y_DOT").text)
        z_dot = float(state_vector.find("Z_DOT").text)
        redis_client.hset("iss_data", epoch_str.split('.')[0], str({"x": x, "y": y, "z": z, "x_dot": x_dot, "y_dot": y_dot, "z_dot": z_dot}))


def get_iss_data() -> List[dict]:
    """
    Returns dataset or creates data set if not already initialized
    Useful information is epoch (changed format), x, y, z (positions), x_dot, y_dot, and z_dot (velocities)
    :return: dataset containing the useful information
    """
    if redis_client.hlen("iss_data") == 0:
        process_data(iss_data)

    def normalize_epoch(epoch):
        """
        Converts string to datetime format
        :param epoch: takes in a string of epoch and converts it to a datetime object
        :return: datetime object
        """
    return [{"epoch": epoch.split('.')[0], **eval(data)} for epoch, data in redis_client.hgetall("iss_data").items()] #Help from GPT taking information from redis and turning it into proper format

def closest_epoch(dateTime: datetime = datetime.now()) -> dict:
    """
    Find the state vector closest to the dateTime time given from the List[dict] of state vectors
    :param dateTime: date and time to be compared to
    :return: state vector closest to the current time
    """
    if redis_client.hlen("iss_data") == 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError
    now = dateTime
    closest_vector = None
    min_diff = float("inf")
    for epoch, data in redis_client.hgetall("iss_data").items():
        try:
            epoch_time = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            epoch_time = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S")
        if abs(epoch_time - now).total_seconds() < min_diff:
            min_diff = abs(epoch_time - now).total_seconds()
            closest_vector = {"epoch": epoch_time, **eval(data)}

    logging.info(f"Closest vector: {closest_vector}")
    return closest_vector

def epoch_range() -> (datetime, datetime, datetime):
    """
    Determines range of data using first and last epochs
    :return: First and last epoch values as well as difference between first and last epochs
    """
    if redis_client.hlen("iss_data") == 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError

    epochs = []
    for epoch, data in redis_client.hgetall("iss_data").items():
        try:
            epoch_time = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            epoch_time = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S")
        epochs.append(epoch_time)

    epochs.sort()

    first_epoch = epochs[0]
    last_epoch = epochs[-1]
    logging.info(f"Data covers: {first_epoch} to {last_epoch}")
    return first_epoch, last_epoch, (last_epoch - first_epoch)

def avg_speed() -> float:
    """
    Calculates the average speed of the object for all epochs given their velocities in each direction (labeled x_dot, y_dot, and z_dot).
    :return: average speed of all objects combined
    """
    count = 0
    avg = 0.0
    for epoch, data in redis_client.hgetall("iss_data").items():
        data = eval(data)
        count += 1
        avg += speed(float(data["x_dot"]), float(data["y_dot"]), float(data["z_dot"]))
    if count <= 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError
    avg = avg / count
    logging.info(f"average speed: {avg}")
    return avg

@app.route('/epochs', methods = ['GET'])
def get_epochs() -> List[dict]:
    """
    Flask route to return a portion of the dataset
    :param limit: the number of entries desired
    :param offset: the initial position (0-indexing) for starting to process data
    :return: condensed dataset based on limit and offset as a list of dicts
    """
    limit = request.args.get('limit')
    offset = request.args.get('offset')
    if limit is None or offset is None:
        return get_iss_data()
    try:
        limit = int(limit)
    except ValueError as e:
        logging.error(str(e) + " limit")
        #raise ValueError
        raise BadRequest()
    try:
        offset = int(offset)
    except ValueError as e:
        logging.error(str(e) + " offset")
        # raise ValueError
        raise BadRequest()

    state_vectors = get_iss_data()
    new_vector = []
    print(len(state_vectors))
    if offset <= 0 or offset >= len(state_vectors):
        raise BadRequest()
    if limit <= 0 or limit + offset >= len(state_vectors):
        limit = len(state_vectors)

    for i in range(offset, offset + limit):
        new_vector.append(state_vectors[i])
    return new_vector

@app.route('/epochs/<epoch>', methods = ['GET'])
def get_specific_epoch(epoch: str) -> dict:
    """
    Return state information for a specific Epoch from the data set
    :param epoch: dateTime of epoch that the user wants information about in format ex. 2025-061T20:10:30.000000Z
    :return: state information for a specific Epoch from the data set
    """
    converted_epoch = epoch.split('.')[0]
    data = redis_client.hget("iss_data", converted_epoch)
    if not data:
        logging.error("Failed to find that epoch value in our dataset")
        raise BadRequest()
    return {"epoch": epoch, **eval(data)}

@app.route('/epochs/<epoch>/speed', methods = ['GET'])
def get_specific_speed(epoch: str) -> list:
    """
    Get instananeous speed for a specific Epoch from the data set
    :param epoch: dateTime of epoch that the user wants information about
    :return: instantaneous speed for a specific Epoch in list format with 0 index as a list
    """
    epoch_vector = get_specific_epoch(epoch)
    return [speed(float(epoch_vector["x_dot"]), float(epoch_vector["y_dot"]), float(epoch_vector["z_dot"]))]


@app.route('/epochs/<epoch>/location', methods = ['GET'])
def compute_location_astropy(epoch: str) -> dict:
    """
    Used the provided code from Dr Allen
    Determine the location of the object in the current epoch
    :param epoch: dateTime of epoch that the user wants information about
    :return: latitude, longitude, and height of the object in the current epoch as well as geoposition
    """
    sv = get_specific_epoch(epoch)
    x = float(sv['x'])
    y = float(sv['y'])
    z = float(sv['z'])

    this_epoch=time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(epoch, '%Y-%jT%H:%M:%S.%fZ'))
    cartrep = coordinates.CartesianRepresentation([x, y, z], unit=units.km)
    gcrs = coordinates.GCRS(cartrep, obstime=this_epoch)
    itrs = gcrs.transform_to(coordinates.ITRS(obstime=this_epoch))
    loc = coordinates.EarthLocation(*itrs.cartesian.xyz)
    geocoder = Nominatim(user_agent='iss_tracker')
    geoloc = geocoder.reverse((loc.lat.value, loc.lon.value), zoom=15, language='en')

    return {"lat": loc.lat.value, "lon": loc.lon.value, "height": loc.height.value, "location" : str(geoloc)}

@app.route('/now', methods = ['GET'])
def get_now_epoch() -> dict:
    """
    Gets state vector information closest to now as well as speed information in dictionary format.
    :return: return {"state_vector" : state vectors (dict), "speed" : instantaneous speed (float)} for epoch that is closest to now
    """
    epoch_vector = closest_epoch()
    return {"state_vector": epoch_vector, "speed": speed(float(epoch_vector["x_dot"]), float(epoch_vector["y_dot"]), float(epoch_vector["z_dot"]))}

def main():
    state_vectors = get_iss_data()
    #print(state_vectors)
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loglevel', type=str, required=False, default='WARNING', help='set log level to DEBUG, INFO, WARNING, ERROR, or CRITICAL')
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    first_epoch, last_epoch, diff = epoch_range()
    print(f"Data covers information from {first_epoch} to {last_epoch}")
    print(f"Which is {diff} apart")

    closest_vector = closest_epoch()
    print(f"Closest state vector: {closest_vector}")

    avg_sp = avg_speed()
    clos_speed = speed(closest_vector["x_dot"], closest_vector["y_dot"], closest_vector["z_dot"])
    print(f"Average speed of all objects: {avg_sp}")
    print(f"Speed of closest object: {clos_speed}")

    logging.info(f"Done with {len(state_vectors)} state vectors")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
    #main()
