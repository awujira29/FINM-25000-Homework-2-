import connector


def test_historical_bars_type_list():
    result = connector.get_bars('AAPL', '1M')

    assert isinstance(result, list)



