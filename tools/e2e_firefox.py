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

# покупатель сначала отвечает на плашку cookie; на file:// у каждой страницы своё хранилище — плашка может появиться снова
_get = d.get
def get_and_answer_cookie(url):
    _get(url); time.sleep(.4)
    d.execute_script("var b=document.querySelector('#cookieBar .cookie-no'); if (b) b.click();")
d.get = get_and_answer_cookie
_click = webdriver.remote.webelement.WebElement.click
def click_after_cookie(el):
    el.parent.execute_script("var b=document.querySelector('#cookieBar .cookie-no'); if (b) b.click();")
    _click(el)
webdriver.remote.webelement.WebElement.click = click_after_cookie
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

    # добавки: овощи + масло + «в рубленом виде» на странице товара, отдельная строка в корзине, подпункты в заказе
    d.get(base + '/cart.html'); js("localStorage.clear(); window.name='';")
    d.get(base + '/p/obrez-govyazhya-v-kubikah.html')
    info = d.find_element(By.CSS_SELECTOR, '.product-info')
    vegs = info.find_elements(By.CSS_SELECTOR, '.veg')
    vegs[0].click(); vegs[2].click()
    for _ in range(3): info.find_element(By.CSS_SELECTOR, '[data-oil-inc]').click()
    price = lambda: info.find_element(By.CSS_SELECTOR, '[data-price-out]').text.replace(' ', ' ')
    ok(price() == '410 ₽', f'veg + 3 oil: 320 + 30 + 60 = 410 (got {price()})')
    ok('Все овощные порции ≈ 15%' in info.find_element(By.CSS_SELECTOR, '[data-addon="veg"]').text, 'veg tile says ≈ 15%')
    ok('от щенков до средних пород' in info.find_element(By.CSS_SELECTOR, '[data-addon="chop"]').text, 'chop tile says puppies to medium breeds')
    chop = info.find_element(By.CSS_SELECTOR, '[data-chop]'); chop.click()
    ok(price() == '440 ₽' and 'Выбрано' in chop.text, 'chop +30 = 440, button says Выбрано')
    info.find_element(By.CSS_SELECTOR, '.opt[data-opt="0,5 кг"]').click()
    ok(price() == '305 ₽', f'0,5 кг: 185 + 30 + 60 + 30 = 305 (got {price()})')
    info.find_element(By.CSS_SELECTOR, '.opt[data-opt="1 кг"]').click()
    info.find_element(By.CSS_SELECTOR, '[data-add]').click(); time.sleep(0.3)
    d.get(base + '/catalog.html')
    ok(not d.find_elements(By.CSS_SELECTOR, '.pcard[data-slug="miks-rublenyj-bez-ovoshej"] [data-addons]'), 'chopped product has no addons')
    card = d.find_element(By.CSS_SELECTOR, '.pcard[data-slug="obrez-govyazhya-v-kubikah"]')
    ok(not card.find_element(By.CSS_SELECTOR, '[data-addons]').is_displayed(), 'catalog addons folded')
    card.find_element(By.CSS_SELECTOR, '[data-addons-toggle]').click()
    ok(card.find_element(By.CSS_SELECTOR, '[data-addons]').is_displayed(), 'catalog addons unfold')
    card.find_element(By.CSS_SELECTOR, '[data-add]').click(); time.sleep(0.3)  # та же фасовка без добавок — своя строка
    d.find_element(By.CSS_SELECTOR, '.header-actions a[href$="cart.html"]').click(); time.sleep(1)
    lines = d.find_elements(By.CSS_SELECTOR, '.cart-item')
    ok(len(lines) == 2, f'same pack with/without addons = 2 lines (got {len(lines)})')
    ok(lines and '440' in lines[0].find_element(By.CSS_SELECTOR, '.sum').text and 'морковь, тыква' in lines[0].text, 'cart line shows addons and 440')
    ok('до подъезда' in d.find_element(By.CSS_SELECTOR, '.deliv-note').text, 'checkout says до подъезда')
    for _ in range(8): js("document.querySelectorAll('.cart-item [data-qty-inc]')[1].click()")
    js("window.__opened=null; window.open=function(u){window.__opened=u; return {}}")
    d.find_element(By.ID, 'f-name').send_keys('Анна')
    d.find_element(By.ID, 'f-phone').send_keys('+7 916 123-45-67')
    d.find_element(By.ID, 'f-addr').send_keys('Москва, ул. Пушкина 1')
    js("document.getElementById('f-consent').click(); document.getElementById('checkout').requestSubmit()"); time.sleep(0.3)
    import urllib.parse
    msg = urllib.parse.unquote((js('return window.__opened') or '').partition('text=')[2])
    ok('+ Овощи: морковь, тыква' in msg and 'Лососевое масло 5 мл × 3' in msg and '+ В рубленом виде' in msg and 'все овощные порции ≈ 15%' in msg, 'WhatsApp text lists addons as sub-items')
    ok('Товары: 3 320' in msg.replace(' ', ' '), 'total 440 + 320 × 9 = 3 320')
finally:
    d.quit()
print('\n'.join(res))
