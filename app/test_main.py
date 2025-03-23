from functools import wraps
from collections.abc import Callable

import requests
from decouple import config

# https://fastapi.tiangolo.com/tutorial/testing/#testing
from fastapi.testclient import TestClient

from .main import app, custom_openapi
from .settings import (
    DATE_FORMAT,
    METADATA as M,
    STATUS_OK, STATUS_NOK
)


client = TestClient(app)


# def make_assert_decorator(status_code: int, keys: list[str]) -> Callable:
#     """
#     Return assert decorator parametrized with status code of the response
#     and its keys.
#     """
#     def assert_decorator(test: Callable) -> Callable:
#         """
#         Assertions regarding status code of the response and its contents.
#         """
#         @wraps(test)
#         def wrapper(*args, **kwargs) -> None:
#             response, expected_data = test(*args, **kwargs)

#             # check if the response status code matches provided `status_code`
#             assert response.status_code == status_code

#             # check if response contains nothing but keys from the `keys` list
#             response_dict = response.json()
#             assert list(response_dict) == keys

#             # check if the value of the first key in response is as expected
#             assert response_dict[keys[0]] == expected_data
#         return wrapper
#     return assert_decorator


# assert_ok = make_assert_decorator(STATUS_OK, keys=["data", "chart"])
# assert_nok = make_assert_decorator(STATUS_NOK, keys=["errors"])


def assert_ok(test: Callable) -> Callable:
    """Assertions that app is healthy and works well. """
    @wraps(test)
    def wrapper(*args, **kwargs) -> None:
        response, expected_data = test(*args, **kwargs)

        # check if the response status code matches STATUS_OK setting
        assert response.status_code == STATUS_OK

        # check if response contains nothing but the interest schedule
        # and deposit balance progress chart
        response_dict = response.json()
        assert list(response_dict) == ["data", "chart"]

        # check if the interest schedule is as expected
        assert response_dict["data"] == expected_data

        # check if the chart hosted on the S3_ENDPOINT_URL
        chart_url = response_dict["chart"]
        assert chart_url.startswith(config("S3_ENDPOINT_URL"))

        # check if the chart url is responsive and contains a png image
        chart_response = requests.get(chart_url)
        assert chart_response.status_code == 200
        assert chart_response.headers["Content-Type"] == "image/png"
    return wrapper


def assert_nok(test: Callable) -> Callable:
    """Assertions that app fails due to invalid input data. """
    @wraps(test)
    def wrapper(*args, **kwargs) -> None:
        response, expected_data = test(*args, **kwargs)

        # check if the response status code matches STATUS_NOK setting
        assert response.status_code == STATUS_NOK

        # check if response contains nothing but the errors description
        response_dict = response.json()
        assert list(response_dict) == ["errors"]

        # check if the errors description is as expected
        assert response_dict["errors"] == expected_data
    return wrapper


@assert_ok
def test_task_example():
    """
    Standard endpoint.
    Test example given in the task.
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": 7,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "31.01.2021": 10050.0,
        "28.02.2021": 10100.25,
        "31.03.2021": 10150.75,
        "30.04.2021": 10201.51,
        "31.05.2021": 10252.51,
        "30.06.2021": 10303.78,
        "31.07.2021": 10355.29
    }
    return response, expected


@assert_nok
def test_invalid_day():
    """
    endpoint : standard
    `date`   : invalid day
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "32.01.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": f"Value error, time data '32.01.2021' does not match format '{DATE_FORMAT}'"
    }
    return response, expected


@assert_nok
def test_non_existing_day():
    """
    endpoint : standard
    `date`   : non-existing day
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.11.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": "Value error, day is out of range for month"
    }
    return response, expected


@assert_nok
def test_invalid_month():
    """
    endpoint : standard
    `date`   : invalid month
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.13.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": f"Value error, time data '31.13.2021' does not match format '{DATE_FORMAT}'"
    }
    return response, expected


@assert_ok
def test_year_eq_min():
    """
    endpoint : standard
    `date`   : minimum valid value of the year
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.0001",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "31.01.0001": 10050.0,
        "28.02.0001": 10100.25,
        "31.03.0001": 10150.75,
        "30.04.0001": 10201.51,
        "31.05.0001": 10252.51,
        "30.06.0001": 10303.78,
        "31.07.0001": 10355.29,
        "31.08.0001": 10407.07,
        "30.09.0001": 10459.11,
        "31.10.0001": 10511.4,
        "30.11.0001": 10563.96,
        "31.12.0001": 10616.78
    }
    return response, expected


@assert_nok
def test_year_lt_min():
    """
    endpoint : standard
    `date`   : less than minimum valid value of the year
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.0000",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": "Value error, year 0 is out of range"
    }
    return response, expected


@assert_ok
def test_year_eq_max():
    """
    endpoint : standard
    `date`   : maximum valid value of the year
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.9999",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "31.01.9999": 10050.0,
        "28.02.9999": 10100.25,
        "31.03.9999": 10150.75,
        "30.04.9999": 10201.51,
        "31.05.9999": 10252.51,
        "30.06.9999": 10303.78,
        "31.07.9999": 10355.29,
        "31.08.9999": 10407.07,
        "30.09.9999": 10459.11,
        "31.10.9999": 10511.4,
        "30.11.9999": 10563.96,
        "31.12.9999": 10616.78
    }
    return response, expected


@assert_nok
def test_year_gt_max():
    """
    endpoint : standard
    `date`   : year exceeds maximum valid value
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.10000",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": "Value error, unconverted data remains: 0"
    }
    return response, expected


@assert_nok
def test_invalid_date_format():
    """
    endpoint : standard
    `date`   : invalid format
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31/01/2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "date": f"Value error, time data '31/01/2021' does not match format '{DATE_FORMAT}'"
    }
    return response, expected


@assert_ok
def test_leap_year():
    """
    endpoint : standard
    `date`   : leap year
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2020",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "31.01.2020": 10050.0,
        "29.02.2020": 10100.25,
        "31.03.2020": 10150.75,
        "30.04.2020": 10201.51,
        "31.05.2020": 10252.51,
        "30.06.2020": 10303.78,
        "31.07.2020": 10355.29,
        "31.08.2020": 10407.07,
        "30.09.2020": 10459.11,
        "31.10.2020": 10511.4,
        "30.11.2020": 10563.96,
        "31.12.2020": 10616.78
    }
    return response, expected


@assert_ok
def test_day_month_no_zeros():
    """
    endpoint : standard
    `date`   : day and month with no leading zeros
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "1.1.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    expected = {
        "01.01.2021": 10050.0,
        "01.02.2021": 10100.25,
        "01.03.2021": 10150.75,
        "01.04.2021": 10201.51,
        "01.05.2021": 10252.51,
        "01.06.2021": 10303.78,
        "01.07.2021": 10355.29,
        "01.08.2021": 10407.07,
        "01.09.2021": 10459.11,
        "01.10.2021": 10511.4,
        "01.11.2021": 10563.96,
        "01.12.2021": 10616.78
    }
    return response, expected


@assert_ok
def test_int_coercible_float():
    """
    endpoint            : standard
    `periods`, `amount` : float coercible to integer
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": 12.0,
            "amount" : 10000.0,
            "rate"   : 6
        }
    )
    expected = {
        "31.01.2021": 10050.0,
        "28.02.2021": 10100.25,
        "31.03.2021": 10150.75,
        "30.04.2021": 10201.51,
        "31.05.2021": 10252.51,
        "30.06.2021": 10303.78,
        "31.07.2021": 10355.29,
        "31.08.2021": 10407.07,
        "30.09.2021": 10459.11,
        "31.10.2021": 10511.4,
        "30.11.2021": 10563.96,
        "31.12.2021": 10616.78
    }
    return response, expected


@assert_nok
def test_non_coercible_float():
    """
    endpoint            : standard
    `periods`, `amount` : float not coercible to integer
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": 12.1,
            "amount" : 10000.1,
            "rate"   : 6
        }
    )
    expected = {
        "periods": "Input should be a valid integer, got a number with a fractional part",
        "amount" : "Input should be a valid integer, got a number with a fractional part"
    }
    return response, expected


@assert_ok
def test_int_coercible_string():
    """
    endpoint            : standard
    `periods`, `amount` : string coercible to integer
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": "12.0",
            "amount" : "10000.0",
            "rate"   : 6
        }
    )
    expected = {
        "31.01.2021": 10050.0,
        "28.02.2021": 10100.25,
        "31.03.2021": 10150.75,
        "30.04.2021": 10201.51,
        "31.05.2021": 10252.51,
        "30.06.2021": 10303.78,
        "31.07.2021": 10355.29,
        "31.08.2021": 10407.07,
        "30.09.2021": 10459.11,
        "31.10.2021": 10511.4,
        "30.11.2021": 10563.96,
        "31.12.2021": 10616.78
    }
    return response, expected


@assert_ok
def test_treat_true_as_1():
    """
    endpoint          : standard
    `periods`, `rate` : treat `True` as 1
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": True,
            "amount" : 10_000,
            "rate"   : True
        }
    )
    expected = {
        "31.01.2021": 10008.33
    }
    return response, expected


@assert_nok
def test_treat_false_as_0():
    """
    endpoint          : standard
    `periods`, `rate` : treat `False` as 0
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : False
        }
    )
    expected = {
        "rate": "Input should be greater than or equal to 1"
    }
    return response, expected


@assert_nok
def test_all_invalid():
    """
    endpoint                            : standard
    `date`, `periods`, `amount`, `rate` : `None`/`null`
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : None,
            "periods": None,
            "amount" : None,
            "rate"   : None
        }
    )
    expected = {
        "date"   : "Input should be a valid string",
        "periods": "Input should be a valid integer",
        "amount" : "Input should be a valid integer",
        "rate"   : "Input should be a valid number"
    }
    return response, expected


@assert_ok
def test_periods_amount_rate_eq_min():
    """
    endpoint                    : standard
    `periods`, `amount`, `rate` : minimum valid values
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": M["periods"].ge,
            "amount" : M["amount"].ge,
            "rate"   : M["rate"].ge
        }
    )
    expected = {
        "31.01.2021": 10008.33
    }
    return response, expected


@assert_nok
def test_periods_amount_rate_lt_min():
    """
    endpoint                    : standard
    `periods`, `amount`, `rate` : less than minimum valid values
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": M["periods"].ge - 1,
            "amount" : M["amount"].ge  - 1,
            "rate"   : M["rate"].ge    - 0.1
        }
    )
    expected = {
        "periods": f"Input should be greater than or equal to {M["periods"].ge}",
        "amount" : f"Input should be greater than or equal to {M["amount"].ge}",
        "rate"   : f"Input should be greater than or equal to {M["rate"].ge}"
    }
    return response, expected


@assert_ok
def test_periods_amount_rate_eq_max():
    """
    endpoint                    : standard
    `periods`, `amount`, `rate` : maximum valid values
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": M["periods"].le,
            "amount" : M["amount"].le,
            "rate"   : M["rate"].le
        }
    )
    expected = {
        "31.01.2021": 3020000.0,
        "28.02.2021": 3040133.33,
        "31.03.2021": 3060400.89,
        "30.04.2021": 3080803.56,
        "31.05.2021": 3101342.25,
        "30.06.2021": 3122017.87,
        "31.07.2021": 3142831.32,
        "31.08.2021": 3163783.53,
        "30.09.2021": 3184875.42,
        "31.10.2021": 3206107.92,
        "30.11.2021": 3227481.97,
        "31.12.2021": 3248998.52,
        "31.01.2022": 3270658.51,
        "28.02.2022": 3292462.9,
        "31.03.2022": 3314412.65,
        "30.04.2022": 3336508.74,
        "31.05.2022": 3358752.13,
        "30.06.2022": 3381143.81,
        "31.07.2022": 3403684.77,
        "31.08.2022": 3426376.0,
        "30.09.2022": 3449218.51,
        "31.10.2022": 3472213.3,
        "30.11.2022": 3495361.39,
        "31.12.2022": 3518663.8,
        "31.01.2023": 3542121.55,
        "28.02.2023": 3565735.7,
        "31.03.2023": 3589507.27,
        "30.04.2023": 3613437.32,
        "31.05.2023": 3637526.9,
        "30.06.2023": 3661777.08,
        "31.07.2023": 3686188.93,
        "31.08.2023": 3710763.52,
        "30.09.2023": 3735501.94,
        "31.10.2023": 3760405.29,
        "30.11.2023": 3785474.66,
        "31.12.2023": 3810711.15,
        "31.01.2024": 3836115.9,
        "29.02.2024": 3861690.0,
        "31.03.2024": 3887434.6,
        "30.04.2024": 3913350.83,
        "31.05.2024": 3939439.84,
        "30.06.2024": 3965702.77,
        "31.07.2024": 3992140.79,
        "31.08.2024": 4018755.06,
        "30.09.2024": 4045546.76,
        "31.10.2024": 4072517.07,
        "30.11.2024": 4099667.19,
        "31.12.2024": 4126998.3,
        "31.01.2025": 4154511.62,
        "28.02.2025": 4182208.37,
        "31.03.2025": 4210089.76,
        "30.04.2025": 4238157.02,
        "31.05.2025": 4266411.4,
        "30.06.2025": 4294854.14,
        "31.07.2025": 4323486.51,
        "31.08.2025": 4352309.75,
        "30.09.2025": 4381325.15,
        "31.10.2025": 4410533.98,
        "30.11.2025": 4439937.54,
        "31.12.2025": 4469537.12
    }
    return response, expected


@assert_nok
def test_periods_amount_rate_gt_max():
    """
    endpoint                    : standard
    `periods`, `amount`, `rate` : exceed maximum valid values
    """
    response = client.post(
        url="/standard",
        json={
            "date"   : "31.01.2021",
            "periods": M["periods"].le + 1,
            "amount" : M["amount"].le  + 1,
            "rate"   : M["rate"].le    + 0.1
        }
    )
    expected = {
        "periods": f"Input should be less than or equal to {M["periods"].le}",
        "amount" : f"Input should be less than or equal to {M["amount"].le}",
        "rate"   : f"Input should be less than or equal to {M["rate"].le}"
    }
    return response, expected


@assert_ok
def test_special_endpoint():
    """
    Special endpoint.
    1-year correctness test.
    """
    response = client.post(
        url="/special",
        json={
            "date"   : "31.01.2021",
            "periods": 12,
            "amount" : 10_000,
            "rate"   : 6
        }
    )
    # Special endpoint:
    #   - floors amount to a full cent;
    #   - applies 5% bonus to the balance in the summer months of 2021.
    expected = {
        "31.01.2021": 10049.99,  # 10000    * (1 + 6/1200) = 10049.(9)      -> 10049.99
        "28.02.2021": 10100.23,  # 10049.99 * (1 + 6/1200) = 10100.23995    -> 10100.23
        "31.03.2021": 10150.73,  # 10100.23 * (1 + 6/1200) = 10150.73114(9) -> 10150.73
        "30.04.2021": 10201.48,  # 10150.73 * (1 + 6/1200) = 10201.48364(9) -> 10201.48
        "31.05.2021": 10252.48,  # 10201.48 * (1 + 6/1200) = 10252.4873(9)  -> 10252.48

        # summer
        "30.06.2021": 10818.92,  # 10252.48 * (1 + 6/1200) * 1.05 = 10818.92952  -> 10818.92
        "31.07.2021": 11416.66,  # 10818.92 * (1 + 6/1200) * 1.05 = 11416.66533  -> 11416.66
        "31.08.2021": 12047.43,  # 11416.66 * (1 + 6/1200) * 1.05 = 12047.430465 -> 12047.43

        "30.09.2021": 12107.66,  # 12047.43 * (1 + 6/1200) = 12107.66715 -> 12107.66
        "31.10.2021": 12168.19,  # and so on
        "30.11.2021": 12229.03,
        "31.12.2021": 12290.17
    }
    return response, expected


def test_redirect_to_docs():
    """Test redirect from root to FastAPI Swagger docs. """
    response = client.get("/")
    assert response.status_code == STATUS_OK
    assert str(response.url).endswith("/docs")


def test_custom_openapi():
    """Test `custom_openapi` works as expected. """
    # check if the app.openapi method is customized
    assert app.openapi == custom_openapi

    # check there's currently no OpenAPI schema
    assert app.openapi_schema is None

    # produce the schema and check it's there
    app.openapi()
    assert app.openapi_schema is not None

    app.openapi()
    # custom_openapi's first return statement
    # returns previously produced schema,
    # so the statement is now fully covered
