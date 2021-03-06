import pytest
from rest_framework.test import APIClient

from .utils import token_authenticate


@pytest.fixture(autouse=True)
def no_more_mark_django_db(transactional_db):
    pass


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def monitoring_api_client(user_factory):
    api_client = APIClient()
    user = user_factory()
    user.groups.get_or_create(name='monitoring')
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def user_api_client(user_factory):
    api_client = APIClient()
    user = user_factory()  # don't use the same user as operator_api_client
    token_authenticate(api_client, user)
    return api_client


@pytest.fixture
def staff_api_client(staff_user):
    api_client = APIClient()
    token_authenticate(api_client, staff_user)
    return api_client


@pytest.fixture
def operator_api_client(operator):
    api_client = APIClient()
    token_authenticate(api_client, operator.user)
    api_client.operator = operator
    return api_client


@pytest.fixture
def operator_2(operator, operator_factory):
    return operator_factory()


@pytest.fixture
def operator_2_api_client(operator_2):
    api_client = APIClient()
    token_authenticate(api_client, operator_2.user)
    api_client.operator = operator_2
    return api_client
