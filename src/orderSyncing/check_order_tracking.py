import urllib.parse
import os
import time
import requests

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


ORDER_HISTORY_URL = "https://www.cchobby.nl/sales/order/history/"
BACKEND_URL = os.getenv("BACKEND_URL", "http://31.97.78.137:3005")


# ✅ Extract tracking ID from different URL formats
def extract_tracking_id(href):
    try:
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)

        # Handle multiple possible query params
        for key in ["id", "match", "tracking", "trackingNumber"]:
            if key in query and query[key]:
                return query[key][0]

        # Fallback → last part of path
        path_parts = parsed.path.split("/")
        if path_parts and path_parts[-1]:
            return path_parts[-1]

        return None

    except Exception as e:
        print("❌ extract_tracking_id error:", e)
        return None


# ✅ Main function
def check_order_tracking(driver, supplier_order_number):
    wait = WebDriverWait(driver, 20)

    driver.get(ORDER_HISTORY_URL)

    found = False

    rows = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
    )

    # 🔍 Find correct order
    for row in rows:
        try:
            order_cell = row.find_element(By.CSS_SELECTOR, "td.col.id")
            order_number = order_cell.text.strip()

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

    # ⏳ Wait for tracking section
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".track-order")))

    try:
        # ✅ Get ALL tracking buttons
        buttons = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".track-order .track-button a")
            )
        )

        tracking_ids = set()  # ✅ avoid duplicates

        for btn in buttons:
            href = btn.get_attribute("href")

            if not href:
                continue

            print("🔗 Found URL:", href)

            tracking_id = extract_tracking_id(href)

            if tracking_id:
                tracking_ids.add(tracking_id)

        if not tracking_ids:
            return {
                "supplierOrderNumber": supplier_order_number,
                "trackingGenerated": False,
                "reason": "No tracking IDs found",
            }

        # 🚀 Send each tracking ID separately
        for tracking_id in tracking_ids:
            try:
                res = requests.post(
                    f"{BACKEND_URL}/v1/order-history/save-tracking-id",
                    json={
                        "supplierOrderNumber": supplier_order_number,
                        "trackingNumber": tracking_id,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=15,
                )

                print(f"📦 Sent tracking: {tracking_id}")
                print("📡 STATUS:", res.status_code)
                print("📡 RESPONSE:", res.text)

            except Exception as e:
                print(f"❌ FAILED for {tracking_id}:", repr(e))

            # ⚠️ prevent rate limit
            time.sleep(0.5)

        return {
            "supplierOrderNumber": supplier_order_number,
            "trackingGenerated": True,
            "trackingNumbers": list(tracking_ids),
        }

    except Exception as e:
        return {
            "supplierOrderNumber": supplier_order_number,
            "trackingGenerated": False,
            "reason": str(e),
        }