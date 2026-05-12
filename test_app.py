import pytest
from app import app, _build_analysis

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert b'ok' in response.data

def test_analyse_valid(client):
    data = {'numbers': [1, 2, 3, 4, 5, 6], 'bonus': 7, 'tse': '27'}
    response = client.post('/api/analyse', json=data)
    assert response.status_code == 200
    assert b'ok' in response.get_json()['ok']

def test_analyse_invalid_numbers(client):
    data = {'numbers': [1, 2, 3], 'bonus': 7}
    response = client.post('/api/analyse', json=data)
    assert response.status_code == 400

def test_build_analysis():
    result = _build_analysis([1, 2, 3, 4, 5, 6], 7, '27')
    assert 'sets' in result
    assert 'S1' in result['sets']