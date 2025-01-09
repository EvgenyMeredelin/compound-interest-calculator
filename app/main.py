# standard library
import json
import os
import uuid
from io import BytesIO
from typing import Annotated

# 3rd party libraries
import boto3

# select Anti-Grain Geometry backend to prevent "UserWarning:
# Starting a Matplotlib GUI outside of the main thread will likely fail."
# https://matplotlib.org/stable/users/explain/figure/backends.html#backends
import matplotlib
matplotlib.use("agg")

import matplotlib.pyplot as plt
import mplcyberpunk
plt.style.use("cyberpunk")

from dateutil.relativedelta import relativedelta

# from dotenv import load_dotenv
# load_dotenv()

from fastapi import (
    FastAPI,
    Request
)
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import (
    AfterValidator,
    BaseModel,
    Field
)
from starlette.responses import RedirectResponse

# user modules
from .handlers import *
from .settings import (
    METADATA as M,
    MPL_RUNTIME_CONFIG,
    S3_URL_LIFESPAN,
    STATUS_OK,
    STATUS_NOK
)
plt.rcParams.update(MPL_RUNTIME_CONFIG)


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
            "name": "Evgeny Meredelin",
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
                "date":    "Input should be a valid string",
                "periods": "Input should be a valid integer",
                "amount":  "Input should be a valid integer",
                "rate":    "Input should be a valid number"
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
    return app.openapi_schema


app.openapi = custom_openapi


@app.exception_handler(RequestValidationError)
async def validation_errors_handler(
    request: Request, exc: RequestValidationError
):
    """
    Validation errors handler.
    Response contains errors summary matching pattern
    {"field_name1": "description of the error1",... }.
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
                    "date":    "31.01.2021",
                    "periods": 12,
                    "amount":  10_000,
                    "rate":    6
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

        image_buffer = self.__class__.plot_chart(monthly_schedule)
        url = self.__class__.upload_chart_and_get_link(image_buffer)
        image_buffer.close()
        return {"data": monthly_schedule, "chart": url}

    @staticmethod
    def plot_chart(schedule: dict[str, float]) -> BytesIO:
        """
        Plot deposit balance progress chart for provided interest schedule.
        """
        # stretch chart depending on data
        data_size = len(schedule)
        fig, ax = plt.subplots(figsize=(data_size, 6))

        # plot bars and add amount labels
        dates, amounts = map(list, (schedule, schedule.values()))
        bars = plt.bar(dates, amounts, color="C3")
        mplcyberpunk.add_bar_gradient(bars=bars)
        label_size = 9 if amounts[0] < 100_000 else 8
        ax.bar_label(ax.containers[0], fmt="%.2f", size=label_size)

        # add xticks and title
        plt.xticks(rotation=90, ha="center")
        ax.tick_params(axis="x", pad=-55)
        ax.set_axisbelow(True)
        title_size = clamp(data_size * 3, low=15, high=72, warn=False)
        plt.title("Deposit balance progress", size=title_size)

        # save chart to bytes buffer
        image_buffer = BytesIO()
        plt.savefig(image_buffer, bbox_inches="tight", format="png")
        plt.close(fig)
        return image_buffer

    @staticmethod
    def upload_chart_and_get_link(image_buffer: BytesIO) -> str:
        """
        Upload deposit balance progress chart to S3 bucket and generate
        a presigned direct link.
        """
        image_buffer.seek(0)
        chart_name = f"{uuid.uuid4()}.png"  # generate unique chart name
        bucket = os.environ["S3_BUCKET_NAME"]
        tenant_id = os.environ["S3_TENANT_ID"]
        key_id = os.environ["S3_KEY_ID"]

        # run boto3 session
        session = boto3.session.Session(
            aws_access_key_id=f"{tenant_id}:{key_id}",
            aws_secret_access_key=os.environ["S3_KEY_SECRET"],
            region_name=os.environ["S3_REGION_NAME"]
        )
        # get S3 client
        client = session.client(
            service_name="s3",
            endpoint_url=os.environ["S3_ENDPOINT_URL"]
        )
        # upload chart to bucket
        client.put_object(
            Bucket=bucket,
            Key=chart_name,
            ContentType="image/png",
            Body=image_buffer
        )
        # generate link to chart
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": chart_name},
            ExpiresIn=S3_URL_LIFESPAN  # seconds
        )
        return url


@app.get("/", status_code=STATUS_OK)
async def redirect_from_root_to_docs():
    """
    Redirect from root to FastAPI Swagger docs.
    """
    return RedirectResponse(url="/docs")


@app.post("/standard", status_code=STATUS_OK)
async def standard_interest_scenario(
    calculator: CompoundInterestCalculator
):
    """
    Standard scenario of interest accumulation.
    """
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
