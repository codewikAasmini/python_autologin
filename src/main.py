import sys
from src.login import login
from src.place_order import place_order

def main():
    if len(sys.argv) < 2:
        print("ORDER_FAILED")
        return

    order_id = sys.argv[1]

    driver = login()
    supplier_no = place_order(driver, order_id)

    if supplier_no:
        print(f"SUPPLIER_ORDER_NUMBER:{supplier_no}")
    else:
        print("ORDER_FAILED")

    driver.quit()

if __name__ == "__main__":
    main()
