import time
from selenium.webdriver.common.by import By

def place_order(driver, order_id):
    order = fetch_order_data(order_id)

    driver.get(order["product_url"])
    time.sleep(2)

    driver.find_element(By.NAME, "quantity").clear()
    driver.find_element(By.NAME, "quantity").send_keys(str(order["qty"]))
    driver.find_element(By.ID, "add-to-cart").click()

    driver.get("https://supplier-portal/checkout")

    fill_address(driver, order["shipping"])

    driver.find_element(By.ID, "submit-order").click()
    time.sleep(5)

    supplier_no = driver.find_element(By.ID, "order-number").text

    return supplier_no 
