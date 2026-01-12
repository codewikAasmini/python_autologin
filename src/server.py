from fastapi import FastAPI
from src.login import login
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
