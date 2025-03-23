import json
import os
from typing import Annotated

from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, Field
from starlette.responses import RedirectResponse

from .handlers import (
    AmountHandler, BypassAmountHandler, FloorAmountHandler,
    DateTime
)
from .settings import METADATA as M, STATUS_OK, STATUS_NOK
from .tools import Plotter


app = FastAPI()


def custom_openapi():
    """
    Generate the OpenAPI custom schema of the application.
    https://fastapi.tiangolo.com/how-to/extending-openapi/#extending-openapi
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Compound Interest Calculator",
        version="0.1.0",
        routes=app.routes,
        contact={
            "name" : "Evgeny Meredelin",
            "email": "eimeredelin@sberbank.ru"
        }
    )

    here = os.path.abspath(os.path.dirname(__file__))

    for path in ("/standard", "/special"):
        # load response example
        example_json = f"{here}/examples/{path.removeprefix("/")}.json"
        with open(example_json, "r", encoding="utf-8") as file:
            example = json.load(file)

        # status code 200: set loaded example and schema
        responses = openapi_schema["paths"][path]["post"]["responses"]
        ok, nok = responses["200"], responses["422"]

        ok_content = ok["content"]["application/json"]
        ok_content["example"] = example
        ok_content["schema"] = {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "additionalProperties": {"type": "number"}
                },
                "chart": {"type": "string"}
            },
            "required": ["data", "chart"]
        }

        # status code 422: set example, schema and replace 422 with STATUS_NOK
        nok_content = nok["content"]["application/json"]
        nok_content["example"] = {
            "errors": {
                "date"   : "Input should be a valid string",
                "periods": "Input should be a valid integer",
                "amount" : "Input should be a valid integer",
                "rate"   : "Input should be a valid number"
            }
        }
        nok_content["schema"] = {
            "type": "object",
            "properties": {
                "errors": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["errors"]
        }
        responses[str(STATUS_NOK)] = nok
        del responses["422"]

    # remove unused schemas
    for error in ("HTTPValidationError", "ValidationError"):
        del openapi_schema["components"]["schemas"][error]

    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi


@app.exception_handler(RequestValidationError)
async def validation_errors_handler(
    request: Request, exc: RequestValidationError
):
    """
    Validation errors handler.
    Response contains errors summary matching pattern
    {"field_name_1": "description of the error",... }.
    """
    errors_summary = {
        error["loc"][1]: error["msg"]
        for error in exc.errors()
    }
    return JSONResponse(
        status_code=STATUS_NOK,
        content={"errors": errors_summary}
    )


class CompoundInterestCalculator(BaseModel):
    """
    Compound interest calculator with monthly schedule.
    """

    # date of the first interest accrual
    date: Annotated[str, AfterValidator(DateTime.parse)]

    periods: int = Field(
        ge=M["periods"].ge,
        le=M["periods"].le,  # inclusive range
        description="Investment length, months"
    )
    amount: int = Field(
        ge=M["amount"].ge,
        le=M["amount"].le,   # inclusive range
        description="Initial investment, unit of currency"
    )
    rate: float = Field(
        ge=M["rate"].ge,
        le=M["rate"].le,     # inclusive range
        description="Annual interest rate, percent"
    )
    # example value for the OpenAPI
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date"   : "31.01.2021",
                    "periods": 12,
                    "amount" : 10_000,
                    "rate"   : 6
                }
            ]
        }
    }

    def calculate_interest(
        self, amount_handler: AmountHandler = BypassAmountHandler()
    ) -> dict[str, dict[str, float] | str]:
        """
        Calculate monthly interest schedule with provided amount handler.
        `amount_handler` defaults to `BypassAmountHandler` instance.
        """
        date, periods, amount, rate = self.model_dump(warnings=False).values()
        monthly_schedule = {}

        for months in range(periods):
            # incrementing date in-place, one month per iteration,
            # leads to wrong results, e.g. 31.01 -> 28.02 -> 28.03
            next_date = date + relativedelta(months=months)
            amount *= 1 + rate / 12 / 100
            amount = amount_handler.handle(next_date, amount)
            monthly_schedule[str(next_date)] = round(amount, 2)

        url = Plotter(monthly_schedule).upload_chart()
        return {"data": monthly_schedule, "chart": url}


@app.get("/", status_code=STATUS_OK)
async def redirect_from_root_to_docs():
    """Redirect from root to FastAPI Swagger docs. """
    return RedirectResponse(url="/docs")


@app.post("/standard", status_code=STATUS_OK)
async def standard_interest_scenario(
    calculator: CompoundInterestCalculator
):
    """Standard scenario of interest accumulation. """
    return calculator.calculate_interest()


@app.post("/special", status_code=STATUS_OK)
async def special_interest_scenario(
    calculator: CompoundInterestCalculator
):
    """
    Special scenario of interest accumulation:
    5% bonus to the balance in the summer months of 2021.
    """
    summer_bonus = FloorAmountHandler(
        start_date="01.06.2021",
        end_date="31.08.2021",
        scale=1.05
    )
    return calculator.calculate_interest(summer_bonus)
