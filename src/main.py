import sys
from login import login
from place_order import place_order


def main():
    if len(sys.argv) < 2:
        print("ORDER_FAILED")
        return

    order_id = sys.argv[1]
    print("Processing Order ID:", order_id)

    driver = None

    try:
        driver = login()
        supplier_no = place_order(driver, order_id)

        if supplier_no:
            print(f"SUPPLIER_ORDER_NUMBER:{supplier_no}")
        else:
            print("ORDER_FAILED")

    except Exception as e:
        print("MAIN ERROR:", str(e))
        print("ORDER_FAILED")

    finally:
        if driver:
            driver.quit()
            print("Driver closed")


if __name__ == "__main__":
    main()
