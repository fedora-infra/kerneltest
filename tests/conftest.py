import pytest
import responses


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture(autouse=True)
def mock_oidc():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.get("https://id.example.com/openidc/.well-known/openid-configuration", json={})
        yield
