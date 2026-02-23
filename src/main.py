import sys
from login import login
from place_order import place_order

def main():
    if len(sys.argv) < 2:
        print("ORDER_FAILED")
        sys.exit(1)

    order_id = sys.argv[1]
    print("Processing Order ID:", order_id)

    driver = None

    try:
        driver = login()
        supplier_no = place_order(driver, order_id)

        if supplier_no:
            print(f"SUPPLIER_ORDER_NUMBER:{supplier_no}")
            sys.exit(0)
        else:
            print("ORDER_FAILED")
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