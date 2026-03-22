from fastapi import FastAPI
from src.login import login
from src.check_order_tracking import check_order_tracking
from src.place_order import place_order

app = FastAPI()

@app.post("/place-order")
def place_order_api(order_id: str):
    driver = login()
    supplier_no = place_order(driver, order_id)
    driver.quit()

    if supplier_no:
        return {
            "success": True,
            "supplierOrderNumber": supplier_no
        }

    return { "success": False }


@app.post("/check-order-tracking")
def check_order_tracking_api(
    order_id: str,
    supplier_order_number: str | None = None,
    target_date: str | None = None,
):
    driver = login()

    try:
        result = check_order_tracking(
            driver=driver,
            order_id=order_id,
            supplier_order_number=supplier_order_number,
            do_sync=True,
            target_date=target_date,
        )
        return {"success": True, **result}
    finally:
        driver.quit()
