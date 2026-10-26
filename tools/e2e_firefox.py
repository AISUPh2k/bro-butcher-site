"""Сквозная проверка корзины в настоящем Firefox по file://.  pip install selenium;  python3 tools/e2e_firefox.py file://$PWD/dist"""
import sys, time
from selenium import webdriver
from selenium.webdriver.common.by import By

base = sys.argv[1]  # file:///.../dist
opts = webdriver.FirefoxOptions()
opts.add_argument('-headless')
d = webdriver.Firefox(options=opts)
res = []
def ok(c, m): res.append(('PASS ' if c else 'FAIL ') + m)
try:
    d.get(base + '/catalog.html')
    card = d.find_element(By.CSS_SELECTOR, '.pcard[data-slug="miks-sanek"]')
    card.find_element(By.CSS_SELECTOR, '.opt[data-opt="0,5 кг"]').click()
    add = card.find_element(By.CSS_SELECTOR, '[data-add]')
    add.click(); time.sleep(1.5); add.click(); time.sleep(0.3)
    ok(d.find_element(By.CSS_SELECTOR, '[data-cart-count]').text == '2', 'badge 2 in catalog')
    # переход по ссылке в шапке, как делает человек
    d.find_element(By.CSS_SELECTOR, '.header-actions a[href$="cart.html"]').click(); time.sleep(1)
    items = d.find_elements(By.CSS_SELECTOR, '.cart-item')
    ok(len(items) == 1, f'cart shows {len(items)} item(s) after header link')
    ok('Санёк' in d.page_source and '0,5 кг' in items[0].text if items else False, 'item is Санёк 0,5 кг')
    # удаляем на странице корзины, идём на товар, проверяем, что не воскресло
    if items:
        items[0].find_element(By.CSS_SELECTOR, '[data-qty-inc]').click(); time.sleep(0.2)
        q = d.find_element(By.CSS_SELECTOR, '.cart-item [data-qty-input]').get_attribute('value')
        ok(q == '3', 'qty +1 = 3')
    d.find_element(By.CSS_SELECTOR, '.main-nav a[href$="catalog.html"]').click(); time.sleep(1)
    ok(d.find_element(By.CSS_SELECTOR, '[data-cart-count]').text == '3', 'catalog sees qty 3 after cart edit')
    d.find_element(By.CSS_SELECTOR, '.pcard[data-slug="miks-lyalya"] h3 a').click(); time.sleep(1)
    d.find_element(By.CSS_SELECTOR, '.product-info [data-add]').click(); time.sleep(0.3)
    ok(d.find_element(By.CSS_SELECTOR, '[data-cart-count]').text == '4', 'product page add -> 4')
    d.find_element(By.CSS_SELECTOR, '.header-actions a[href$="cart.html"]').click(); time.sleep(1)
    ok(len(d.find_elements(By.CSS_SELECTOR, '.cart-item')) == 2, 'cart has 2 lines')
    # оформление: добираем до минимума, проверяем согласие на обработку ПД
    js = d.execute_script
    for _ in range(12): js("document.querySelector('.cart-item [data-qty-inc]').click()")
    js("window.__opened=null; window.open=function(u){window.__opened=u; return {}}")
    d.find_element(By.ID, 'f-name').send_keys('Анна')
    d.find_element(By.ID, 'f-phone').send_keys('+7 916 123-45-67')
    d.find_element(By.ID, 'f-addr').send_keys('Москва, ул. Пушкина 1')
    js("document.getElementById('checkout').requestSubmit()"); time.sleep(0.3)
    err = d.find_element(By.ID, 'formError')
    ok(js('return window.__opened') is None and 'согласие' in err.text, 'blocked without consent')
    js("document.getElementById('f-consent').click(); document.getElementById('checkout').requestSubmit()"); time.sleep(0.3)
    ok((js('return window.__opened') or '').startswith('https://wa.me/'), 'sent with consent')
    d.get(d.current_url.rsplit('/', 1)[0] + '/privacy/index.html'); time.sleep(1)
    ok(d.current_url.endswith('/privacy.html') and 'Яндекс Метрика' in d.page_source, 'old /privacy redirects to policy')
finally:
    d.quit()
print('\n'.join(res))
