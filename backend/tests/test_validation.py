from fastapi.testclient import TestClient
from app.main import app
from app.main import Trade,Note
from pydantic import ValidationError
import pytest

client=TestClient(app)
def test_reject_negative_trade_before_db():
    response=client.post('/api/portfolios/1/trades',json={'ticker':'AAPL','quantity':-2,'side':'BUY','request_id':'12345678-1234-1234-1234-123456789012'})
    assert response.status_code==422

def test_reject_unsupported_side():
    with pytest.raises(ValidationError):Trade(ticker='AAPL',side='SHORT',quantity=1,request_id='12345678-1234-1234-1234-123456789012')

def test_note_whitespace():
    with pytest.raises(ValidationError):Note(ticker='AAPL',text='   ')

def test_filter_bounds():
    assert client.get('/api/stocks?limit=100000').status_code==422
    assert client.get('/api/stocks?sort=DROP').status_code==422

def test_date_validation():
    assert client.get('/api/news?start=2020-06-05&end=2019-01-01').status_code==422
