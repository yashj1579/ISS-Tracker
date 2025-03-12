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

app = Flask(__name__)



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

def process_data(url: str) -> List[dict]:
    """
    Takes url string (XML data) and extracts the useful information from it
    Useful information is epoch (changed format), x, y, z (positions), x_dot, y_dot, and z_dot (velocities)
    :param url: website that we are getting data from
    :return: information stored in data
    """
    try:
        xml_data = requests.get(url)
        xml_data.raise_for_status()
        xml_data = xml_data.text
    except:
        logging.error("Failed to get data")
        raise TypeError

    root = ET.fromstring(xml_data)
    state_vectors = []
    for state_vector in root.findall(".//stateVector"):
        epoch = datetime.strptime(state_vector.find("EPOCH").text, "%Y-%jT%H:%M:%S.%fZ")
        x = float(state_vector.find("X").text)
        y = float(state_vector.find("Y").text)
        z = float(state_vector.find("Z").text)
        x_dot = float(state_vector.find("X_DOT").text)
        y_dot = float(state_vector.find("Y_DOT").text)
        z_dot = float(state_vector.find("Z_DOT").text)
        state_vectors.append({"epoch": epoch, "x": x, "y": y, "z": z, "x_dot": x_dot, "y_dot": y_dot, "z_dot": z_dot})

    return state_vectors


def closest_epoch(state_vectors: List[dict], dateTime: datetime =datetime.now()) -> dict:
    """
    Find the state vector closest to the dateTime time
    :param state_vectors: list of state vectors (typically that of the data that was requested)
    :param dateTime: date and time to be compared to
    :return: state vector closest to the current time
    """
    if len(state_vectors) <= 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError
    now = dateTime
    closest_vector = state_vectors[0]
    for i in range(len(state_vectors)):
        if abs(closest_vector["epoch"] - now) >= abs(state_vectors[i]["epoch"] - now):
            closest_vector = state_vectors[i]
    logging.info(f"closest vector: {closest_vector}")
    return closest_vector

def epoch_range(state_vectors: List[Dict[str, float]]) -> (float, float, float):
    """
    Determines range of data using first and last epochs
    :param state_vectors: list of state vectors (typically that of the data that was requested)
    :return: First and last epoch values as well as difference between first and last epochs
    """
    if len(state_vectors) <= 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError

    first_epoch = state_vectors[0]["epoch"]
    last_epoch = state_vectors[-1]["epoch"]
    logging.info(f"Data covers: {first_epoch} to {last_epoch}")

    return first_epoch, last_epoch, (last_epoch - first_epoch)

def avg_speed(state_vectors: List[Dict[str, float]]) -> float:
    """
    Calculates the average speed of the object for all epochs given their velocities in each direction (labeled x_dot, y_dot, and z_dot).
    :param state_vectors: list of state vectors (typically that of the data that was requested)
    :return: average speed of all objects combined
    """
    if len(state_vectors) <= 0:
        logging.error(f'encountered empty list in tot_dist_from')
        raise ValueError

    avg = 0.0
    for state_vector in state_vectors:
        avg += speed(state_vector["x_dot"], state_vector["y_dot"], state_vector["z_dot"])
    avg = avg / len(state_vectors)
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
    #print("get_condensed_epochs()")
    limit = request.args.get('limit')
    offset = request.args.get('offset')
    if limit is None or offset is None:
        return process_data("https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml")
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

    state_vectors = process_data("https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml")
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
    :param epoch: dateTime of epoch that the user wants information about
    :return: state information for a specific Epoch from the data set
    """
    epoch = datetime.strptime(epoch, "%Y-%jT%H:%M:%S.%fZ")
    state_vectors = process_data("https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml")
    epoch_vector = closest_epoch(state_vectors, epoch)
    if epoch_vector["epoch"] != epoch:
        logging.error("Failed to find that epoch value in our dataset")
        raise BadRequest()
    return epoch_vector

@app.route('/epochs/<epoch>/speed', methods = ['GET'])
def get_specific_speed(epoch: str) -> list:
    """
    Get instananeous speed for a specific Epoch from the data set
    :param epoch: dateTime of epoch that the user wants information about
    :return: instantaneous speed for a specific Epoch in list format with 0 index as a list
    """
    epoch_vector = get_specific_epoch(epoch)
    return [speed(epoch_vector["x_dot"], epoch_vector["y_dot"], epoch_vector["z_dot"])]

@app.route('/now', methods = ['GET'])
def get_now_epoch() -> dict:
    """
    Gets state vector information closest to now as well as speed information in dictionary format.
    :param epoch: dateTime of epoch that the user wants information about
    :return: return {"state_vector" : state vectors (dict), "speed" : instantaneous speed (float)} for epoch that is closest to now
    """
    state_vectors = process_data("https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml")
    epoch_vector = closest_epoch(state_vectors)
    return {"state_vector": epoch_vector, "speed": speed(epoch_vector["x_dot"], epoch_vector["y_dot"], epoch_vector["z_dot"])}

def main():
    state_vectors = process_data("https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml")
    #print(state_vectors)
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loglevel', type=str, required=False, default='WARNING', help='set log level to DEBUG, INFO, WARNING, ERROR, or CRITICAL')
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    first_epoch, last_epoch, diff = epoch_range(state_vectors)
    print(f"Data covers information from {first_epoch} to {last_epoch}")
    print(f"Which is {diff} apart")

    closest_vector = closest_epoch(state_vectors)
    print(f"Closest state vector: {closest_vector}")

    avg_sp = avg_speed(state_vectors)
    clos_speed = speed(closest_vector["x_dot"], closest_vector["y_dot"], closest_vector["z_dot"])
    print(f"Average speed of all objects: {avg_sp}")
    print(f"Speed of closest object: {clos_speed}")

    logging.info(f"Done with {len(state_vectors)} state vectors")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
    main()
