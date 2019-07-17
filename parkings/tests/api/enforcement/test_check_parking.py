# -*- coding: utf-8 -*-

import datetime

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse
from django.utils import timezone
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from parkings.api.monitoring.region import WGS84_SRID
from parkings.models import ParkingCheck, PaymentZone, Permit, PermitArea
from parkings.models.constants import GK25FIN_SRID
from parkings.tests.api.utils import check_required_fields

from ...utils import approx

list_url = reverse("enforcement:v1:check_parking")


PARKING_DATA = {
    "registration_number": "ABC-123",
    "location": {"longitude": 24.9, "latitude": 60.2},
}

INVALID_PARKING_DATA = {
    "registration_number": "ABC-123",
    "location": {"longitude": 24.9, "latitude": 60.4},
}


def create_area_geom():
    area_wgs84 = [
        Point(x, srid=WGS84_SRID)
        for x in [
            (24.8, 60.3),  # North West corner
            (25.0, 60.3),  # North East corner
            (25.0, 60.1),  # South East corner
            (24.8, 60.1),  # South West corner
        ]
    ]
    area_gk25fin = [
        x.transform(GK25FIN_SRID, clone=True) for x in area_wgs84
    ]
    points = area_gk25fin
    points.append(area_gk25fin[0])
    polygons = Polygon(points)

    return MultiPolygon(polygons)


def test_check_parking_required_fields(staff_api_client):
    expected_required_fields = {"registration_number", "location"}
    check_required_fields(staff_api_client, list_url, expected_required_fields)


def test_check_parking_valid_parking(operator, staff_api_client, parking_factory):
    area = create_area_geom()
    PaymentZone.objects.create(number=1, name="Maksuvyöhyke 1", geom=area)
    parking = parking_factory(registration_number="ABC-123", operator=operator, zone=1)

    response = staff_api_client.post(list_url, data=PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["allowed"] is True
    assert response.data["end_time"] == parking.time_end


def test_check_parking_invalid_time_parking(operator, staff_api_client, history_parking_factory):
    area = create_area_geom()
    PaymentZone.objects.create(number=1, name="Maksuvyöhyke 1", geom=area)
    history_parking_factory(registration_number="ABC-123", operator=operator, zone=1)

    response = staff_api_client.post(list_url, data=PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["allowed"] is False


def test_check_parking_invalid_zone_parking(operator, staff_api_client, parking_factory):
    area = create_area_geom()
    PaymentZone.objects.create(number=1, name="Maksuvyöhyke 1", geom=area)
    parking_factory(registration_number="ABC-123", operator=operator, zone=2)

    response = staff_api_client.post(list_url, data=PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["allowed"] is False


def test_check_parking_valid_permit(staff_api_client, permit_series_factory):
    area = create_area_geom()
    PermitArea.objects.create(name="Kamppi", identifier="A", geom=area)
    permit_series = permit_series_factory(active=True)

    end_time = timezone.now() + datetime.timedelta(days=1)
    start_time = timezone.now()

    subjects = [
        {
            "end_time": str(end_time),
            "start_time": str(start_time),
            "registration_number": "ABC-123",
        }
    ]
    areas = [{"area": "A", "end_time": str(end_time), "start_time": str(start_time)}]

    Permit.objects.create(
        series=permit_series, external_id=12345, subjects=subjects, areas=areas
    )

    response = staff_api_client.post(list_url, data=PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["allowed"] is True


def test_check_parking_invalid_time_permit(staff_api_client, permit_series_factory):
    area = create_area_geom()
    PermitArea.objects.create(name="Kamppi", identifier="A", geom=area)
    permit_series = permit_series_factory(active=True)

    end_time = timezone.now()
    start_time = timezone.now() - datetime.timedelta(days=1)

    subjects = [
        {
            "end_time": str(end_time),
            "start_time": str(start_time),
            "registration_number": "ABC-123",
        }
    ]
    areas = [{"area": "A", "end_time": str(end_time), "start_time": str(start_time)}]

    Permit.objects.create(
        series=permit_series, external_id=12345, subjects=subjects, areas=areas
    )

    response = staff_api_client.post(list_url, data=PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["allowed"] is False


def test_check_parking_invalid_location(staff_api_client, permit_series_factory):
    area = create_area_geom()
    PermitArea.objects.create(name="Kamppi", identifier="A", geom=area)
    permit_series = permit_series_factory(active=True)

    end_time = timezone.now() + datetime.timedelta(days=1)
    start_time = timezone.now()

    subjects = [
        {
            "end_time": str(end_time),
            "start_time": str(start_time),
            "registration_number": "ABC-123",
        }
    ]
    areas = [{"area": "A", "end_time": str(end_time), "start_time": str(start_time)}]

    Permit.objects.create(
        series=permit_series, external_id=12345, subjects=subjects, areas=areas
    )

    response = staff_api_client.post(list_url, data=INVALID_PARKING_DATA)

    assert response.status_code == HTTP_200_OK
    assert response.data["location"] == {
        'payment_zone': None, 'permit_area': None}
    assert response.data["allowed"] is False


def test_returned_data_has_correct_schema(staff_api_client):
    response = staff_api_client.post(list_url, data=PARKING_DATA)

    data = response.data
    assert isinstance(data, dict)
    assert sorted(data.keys()) == ["allowed", "end_time", "location", "time"]
    assert isinstance(data["allowed"], bool)
    assert data["end_time"] is None
    assert isinstance(data["location"], dict)
    assert sorted(data["location"].keys()) == ["payment_zone", "permit_area"]
    assert isinstance(data["time"], datetime.datetime)


def test_requested_time_must_have_timezone(staff_api_client):
    naive_dt = datetime.datetime(2011, 1, 31, 12, 34, 56, 123456)
    input_data = dict(PARKING_DATA, time=naive_dt)
    response = staff_api_client.post(list_url, data=input_data)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data["time"] == ["Timezone is required"]


def test_time_is_honored(staff_api_client):
    dt = datetime.datetime(2011, 1, 31, 12, 34, 56, 123456,
                           tzinfo=datetime.timezone.utc)
    input_data = dict(PARKING_DATA, time=dt)
    response = staff_api_client.post(list_url, data=input_data)

    assert (response.status_code, response.data["time"]) == (HTTP_200_OK, dt)


def test_action_is_logged(staff_api_client):
    response = staff_api_client.post(list_url, data={
        "registration_number": "XYZ-555",
        "location": {"longitude": 24.1234567, "latitude": 60.2987654},
    })

    assert response.status_code == HTTP_200_OK
    assert ParkingCheck.objects.count() == 1
    recorded_check = ParkingCheck.objects.first()
    assert recorded_check.registration_number == "XYZ-555"
    assert recorded_check.location.coords == approx(
        (24.1234567, 60.2987654), abs=1e-10)
    assert recorded_check.time == response.data["time"]
    assert recorded_check.time_overridden is False