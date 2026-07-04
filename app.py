from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uuid import uuid4
import time
import base64
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 57
RATE_LIMIT = 15
WINDOW = 10

orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

idempotency_store = {}
client_requests = {}


def rate_limit(client_id: str):
    now = time.time()

    history = client_requests.get(client_id, [])
    history = [t for t in history if now - t < WINDOW]

    if len(history) >= RATE_LIMIT:
        retry_after = max(
            1,
            math.ceil(WINDOW - (now - history[0]))
        )

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded"
            },
            headers={
                "Retry-After": str(retry_after)
            },
        )

    history.append(now)
    client_requests[client_id] = history

    return None


@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header(..., alias="X-Client-Id"),
):

    limited = rate_limit(x_client_id)
    if limited is not None:
        return limited

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order


@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: str | None = None,
    x_client_id: str = Header(..., alias="X-Client-Id"),
):

    limited = rate_limit(x_client_id)
    if limited is not None:
        return limited

    start = 0

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }


@app.get("/")
def root():
    return {
        "message": "Orders API Running"
    }
