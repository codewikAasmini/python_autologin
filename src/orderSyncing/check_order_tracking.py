import urllib.parse
import os , time, requests
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


ORDER_HISTORY_URL = "https://www.cchobby.nl/sales/order/history/"

# BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")
BACKEND_URL = os.getenv("BACKEND_URL", "http://31.97.78.137:3005")


def extract_tracking_id(href):
    try:
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        return query.get("id", [None])[0]
    except:
        return None


def check_order_tracking(driver, supplier_order_number):
    wait = WebDriverWait(driver, 20)

    driver.get(ORDER_HISTORY_URL)

    found = False

    rows = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
    )

    for row in rows:
        try:
            order_cell = row.find_element(By.CSS_SELECTOR, "td.col.id")
            order_number = order_cell.text.strip()

            # ❌ REMOVE noisy print OR keep as debug:
            # print("Checking Ordernr:", order_number)

            if supplier_order_number == order_number:
                view_btn = row.find_element(By.CSS_SELECTOR, "a.action.view")
                driver.execute_script("arguments[0].click();", view_btn)
                found = True
                break

        except Exception:
            continue

    if not found:
        return {
            "supplierOrderNumber": supplier_order_number,
            "trackingGenerated": False,
            "reason": "Order not found in table",
        }

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".track-order")))

    try:
        btn = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".track-order .track-button a")
            )
        )

        if btn.get_attribute("disabled"):
            return {
                "supplierOrderNumber": supplier_order_number,
                "trackingGenerated": False,
                "reason": "Tracking button disabled",
            }

        href = btn.get_attribute("href")

        if not href:
            return {
                "supplierOrderNumber": supplier_order_number,
                "trackingGenerated": False,
                "reason": "No tracking link",
            }

        tracking_id = extract_tracking_id(href)

        if not tracking_id:
            return {
                "supplierOrderNumber": supplier_order_number,
                "trackingGenerated": False,
                "reason": "Tracking ID not found",
            }
        try:
            res = requests.post(
                f"{BACKEND_URL}/v1/order-history/save-tracking-id",
                json={
                    "supplierOrderNumber": supplier_order_number,
                    "trackingNumber": tracking_id,
                },
                headers={
                    "Content-Type": "application/json",
                },
                timeout=15,
            )

            print("📡 SYNC STATUS:", res.status_code)
            print("📡 SYNC BODY:", res.text)

            res.raise_for_status()

        except Exception as e:
            print("❌ ORDER SYNC FAILED:", repr(e))

        return {
            "supplierOrderNumber": supplier_order_number,
            "trackingGenerated": True,
            "trackingNumber": tracking_id,
            "trackingUrl": f"/tracking?id={tracking_id}",
        }

    except Exception as e:
        return {
            "supplierOrderNumber": supplier_order_number,
            "trackingGenerated": False,
            "reason": str(e),
        }
