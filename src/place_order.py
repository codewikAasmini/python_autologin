import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")


def fetch_order_data(order_id):
    """
    🔥 Internal backend call (NO AUTH REQUIRED)
    """
    res = requests.get(
        f"{BACKEND_URL}/v1/order-history/internal/{order_id}",
        timeout=15,
    )
    res.raise_for_status()

    order = res.json()

    return {
        "sku": order["product"]["articleNo"],
        "qty": order.get("quantity", 1),
    }


def place_order(driver, order_id):
    print("Placing order:", order_id)
    wait = WebDriverWait(driver, 40)

    try:
        order = fetch_order_data(order_id)
        sku = order["sku"]
        qty = order["qty"]

        # Home
        driver.get("https://www.cchobby.nl/")
        time.sleep(2)

        # Search SKU
        search = wait.until(EC.presence_of_element_located((By.NAME, "q")))
        search.clear()
        search.send_keys(sku)
        search.submit()

        # Product
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-item-link"))
        ).click()

        # Quantity
        try:
            qty_input = wait.until(EC.presence_of_element_located((By.NAME, "qty")))
            qty_input.clear()
            qty_input.send_keys(str(qty))
        except:
            pass

        # Add to cart
        wait.until(
            EC.element_to_be_clickable((By.ID, "product-addtocart-button"))
        ).click()

        # Cart → Checkout
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.action.showcart"))
        ).click()

        wait.until(
            EC.element_to_be_clickable((By.ID, "top-cart-btn-checkout"))
        ).click()

        # Place order
        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.action.primary.checkout")
            )
        ).click()

        # Order number
        order_number_el = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                "//*[contains(text(),'Ordernummer') or contains(text(),'Order number')]"
            ))
        )

        supplier_order_no = order_number_el.text.strip()
        print("SUPPLIER ORDER:", supplier_order_no)

        return supplier_order_no

    except Exception as e:
        print("PLACE ORDER FAILED:", e)
        driver.save_screenshot("place_order_failed.png")
        return None
