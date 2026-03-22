import sys
from syncingLogin import login
from check_order_tracking import check_order_tracking
from selenium.webdriver.support.ui import WebDriverWait
import time
import json

def main():
    if len(sys.argv) < 2:
        print("ORDER_FAILED")
        sys.exit(1)

    supplier_order_number = sys.argv[1]
    print("Processing Supplier Order Number:", supplier_order_number)

    driver = None

    try:
        driver = login()
        time.sleep(3)

        WebDriverWait(driver, 20).until(
            lambda d: "login" not in d.current_url.lower()
        )

        result = check_order_tracking(
            driver,
            supplier_order_number=supplier_order_number
        )
        print("JSON_RESULT:" + json.dumps(result))
        if result.get("trackingGenerated"):
            print(f"TRACKING_READY:{result.get('supplierOrderNumber')}")
            print(result)
            sys.exit(0)
        else:
            print(f"TRACKING_NOT_READY:{supplier_order_number}")
            print(result)
            sys.exit(1)

    except Exception as e:
        print("MAIN ERROR:", e)
        print("ORDER_FAILED")
        sys.exit(1)

    finally:
        if driver:
            print("🧹 Closing browser...")
            driver.quit()


if __name__ == "__main__":
    main()