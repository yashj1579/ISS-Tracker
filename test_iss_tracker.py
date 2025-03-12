#!/usr/bin/env python3
import pytest
import math
from datetime import datetime, timedelta
from iss_tracker import speed, process_data, closest_epoch, epoch_range, avg_speed, get_epochs, get_specific_epoch, get_specific_speed, get_now_epoch
import requests

def test_speed():
    assert speed(3, 4, 0) == 5.0
    assert speed(0, 0, 0) == 0.0
    assert abs(speed(1, 2, 2) - 3.0) <= 1e-3


sample_data = [
    {"epoch": datetime(2025, 2, 14, 12, 0, 0), "x": 1., "y": 2., "z": 3., "x_dot": 1., "y_dot": 1., "z_dot": 1.},
    {"epoch": datetime(2025, 2, 14, 12, 5, 0), "x": 2., "y": 3., "z": 4., "x_dot": 2., "y_dot": 2., "z_dot": 2.},
    {"epoch": datetime(2025, 2, 14, 12, 10, 0), "x": 3., "y": 4., "z": 5., "x_dot": 3., "y_dot": 3., "z_dot": 3.},
]

def test_epoch_range():
    first, last, diff = epoch_range(sample_data)
    assert first == datetime(2025, 2, 14, 12, 0, 0)
    assert last == datetime(2025, 2, 14, 12, 10, 0)
    assert diff == timedelta(minutes=10)

def test_avg_speed():
    avg = avg_speed(sample_data)
    expected_avg = (math.sqrt(3) * 6) / 3
    assert abs(avg - expected_avg) <= 1e-2

def test_closest_epoch():
    now = datetime(2025, 2, 14, 12, 6, 0)
    closest = closest_epoch(sample_data)
    assert closest["epoch"] == datetime(2025, 2, 14, 12, 10, 0)
    closest = closest_epoch(sample_data, now)
    assert closest["epoch"] == datetime(2025, 2, 14, 12, 5, 0)

def test_process_data():
    with pytest.raises(Exception):
        process_data("")

def test_get_epochs():
    response = requests.get('http://127.0.0.1:5000/epochs')
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    response = requests.get('http://127.0.0.1:5000/epochs?limit=abc&offset=0')
    assert response.status_code == 400
    response = requests.get('http://127.0.0.1:5000/epochs?limit=2000&offset=-1')
    assert response.status_code == 400
    response = requests.get('http://127.0.0.1:5000/epochs?limit=2&offset=3')
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_specific_epoch():
    response1 = requests.get('http://127.0.0.1:5000/epochs')
    a_representative_epoch = response1.json()
    a_representative_epoch = a_representative_epoch[0]['epoch']
    format = '%a, %d %b %Y %H:%M:%S GMT'
    a_representative_epoch = datetime.strptime(a_representative_epoch, format)
    format = '%Y-%jT%H:%M:%S.%fZ'
    response = requests.get(f'http://127.0.0.1:5000/epochs/{str(a_representative_epoch.strftime(format))}')
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    response = requests.get('http://127.0.0.1:5000/epochs/9999-01-01T00:00:00')
    assert response.status_code == 500


def test_get_specific_speed():
    response1 = requests.get('http://127.0.0.1:5000/epochs')
    a_representative_epoch = response1.json()
    a_representative_epoch = a_representative_epoch[0]['epoch']
    format = '%a, %d %b %Y %H:%M:%S GMT'
    a_representative_epoch = datetime.strptime(a_representative_epoch, format)
    format = '%Y-%jT%H:%M:%S.%fZ'
    response = requests.get(f'http://127.0.0.1:5000/epochs/{str(a_representative_epoch.strftime(format))}/speed')
    assert response.status_code == 200
    assert isinstance(response.json()[0], float)


def test_get_now_epoch():
    response = requests.get('http://127.0.0.1:5000/now')
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    assert len(response.json()) == 2
