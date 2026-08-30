import os
import asyncio
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN, 
    ADMIN_ID, 
    COMPANY_NAME, 
    COMPANY_ADDRESS, 
    WORKING_HOURS, 
    ADMIN_PHONE, 
    INITIAL_SERVICES,
    PAYMENT_PROVIDER_TOKEN,
    LANGUAGES
)

def init_db():
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'uk'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            delivery_type TEXT,
            address TEXT,
            items TEXT,
            total INTEGER,
            status TEXT DEFAULT 'Нове'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] == 0:
        for name, price in INITIAL_SERVICES.items():
            cursor.execute("INSERT OR IGNORE INTO services (name, price) VALUES (?, ?)", (name, price))
            
    conn.commit()
    conn.close()

init_db()

async def handle(request):
    return web.Response(text="Pro Max Coffee Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_user_lang(user_id):
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'uk'

def main_menu(user_id):
    is_admin = (user_id == ADMIN_ID)
    lang = get_user_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES['uk'])
    
    builder = InlineKeyboardBuilder()
    builder.button(text=t["menu"], callback_data="services")
    builder.button(text=t["order"], callback_data="start_order")
    builder.button(text=t["location"], callback_data="location")
    builder.button(text=t["profile"], callback_data="profile")
    builder.button(text="🌐 Змінити мову / Language", callback_data="change_lang")
    if is_admin:
        builder.button(text=t["admin"], callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                   (user.id, user.username or "", user.full_name))
    conn.commit()
    conn.close()

    lang = get_user_lang(user.id)
    t = LANGUAGES.get(lang, LANGUAGES['uk'])

    await message.answer(
        f"{t['welcome']} {COMPANY_NAME}! ☕🥐\nОберіть дію нижче:",
        reply_markup=main_menu(user.id)
    )

@dp.callback_query(F.data == "change_lang")
async def change_lang_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇦 Українська", callback_data="set_lang_uk")
    builder.button(text="🇬🇧 English", callback_data="set_lang_en")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    try:
        await callback.message.edit_text("Оберіть мову / Choose language:", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("set_lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

    try:
        await callback.message.edit_text("Головне меню:", reply_markup=main_menu(user_id))
    except TelegramBadRequest:
        pass
    await callback.answer("Мову змінено! ✅")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("Головне меню:", reply_markup=main_menu(callback.from_user.id))
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    balance = res[0] if res else 0
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")

    await callback.message.edit_text(
        f"👤 Ваш профіль:\n\n"
        f"ID: {user_id}\n"
        f"💰 Бонусний кешбек: {balance} грн\n"
        f"(Ви можете використовувати бонуси для оплати замовлень)",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "services")
async def show_services(callback: types.CallbackQuery):
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM services")
    items = cursor.fetchall()
    conn.close()

    menu_text = "📋 Актуальне меню:\n\n"
    for name, price in items:
        menu_text += f"🔹 {name} — {price} грн\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    
    try:
        await callback.message.edit_text(menu_text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "location")
async def show_location(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            f"📍 Адреса:\n{COMPANY_ADDRESS}\n\n"
            f"⏰ Графік:\n{WORKING_HOURS}\n\n"
            f"📞 Контакти: {ADMIN_PHONE}",
            reply_markup=main_menu(callback.from_user.id)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "start_order")
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await show_cart_selection(callback.message, state, edit=True)
    await callback.answer()

async def show_cart_selection(message: types.Message, state: FSMContext, edit=False):
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM services")
    items = cursor.fetchall()
    conn.close()

    data = await state.get_data()
    cart = data.get("cart", [])

    cart_text = "🛒 Ваш кошик замовлень:\n"
    total = 0
    if cart:
        for item in cart:
            cart_text += f"• {item['name']} — {item['price']} грн\n"
            total += item['price']
        cart_text += f"\nЗагалом: {total} грн\n\n"
    else:
        cart_text += "Кошик порожній. Оберіть позиції нижче:\n\n"

    builder = InlineKeyboardBuilder()
    for item_id, name, price in items:
        builder.button(text=f"➕ {name} ({price} грн)", callback_data=f"add_to_cart_{item_id}")
    
    if cart:
        builder.button(text="✅ Продовжити (Вибір доставки)", callback_data="choose_delivery")
    
    builder.button(text="🗑 Очистити кошик", callback_data="clear_cart")
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    builder.adjust(1)

    if edit:
        try:
            await message.edit_text(cart_text, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            pass
    else:
        await message.answer(cart_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("add_to_cart_"))
async def add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[3])
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM services WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if item:
        data = await state.get_data()
        cart = data.get("cart", [])
        cart.append({"name": item[0], "price": item[1]})
        await state.update_data(cart=cart)

    await show_cart_selection(callback.message, state, edit=True)
    await callback.answer("Додано!")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await show_cart_selection(callback.message, state, edit=True)
    await callback.answer("Очищено.")

@dp.callback_query(F.data == "choose_delivery")
async def choose_delivery(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏃 Самовивіз (з кав'ярні)", callback_data="delivery_pickup")
    builder.button(text="🚗 Кур'єром на адресу", callback_data="delivery_courier")
    builder.button(text="⬅️ Назад до кошика", callback_data="start_order")
    builder.adjust(1)
    
    try:
        await callback.message.edit_text("📦 Оберіть спосіб отримання замовлення:", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "delivery_pickup")
async def set_pickup(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(delivery_type="Самовивіз", address="Самовивіз з кав'ярні")
    await request_phone(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "delivery_courier")
async def set_courier(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(delivery_type="Доставка кур'єром")
    await callback.message.edit_text("✍️ Введіть вашу адресу (Вулиця, будинок, квартира):")
    await callback.answer()

class OrderProcess(StatesGroup):
    waiting_for_address = State()

@dp.message(F.text, OrderProcess.waiting_for_address)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await request_phone(message, state)

async def request_phone(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Надіслати номер телефону", request_contact=True)
    builder.button(text="❌ Скасувати")
    builder.adjust(1)

    await message.answer(
        "Нам потрібен ваш номер телефону для зв'язку:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )

@dp.message(F.text == "❌ Скасувати")
async def cancel_order(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано.", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Головне меню:", reply_markup=main_menu(message.from_user.id))

@dp.message(F.contact)
async def get_contact_and_pay(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    delivery_type = data.get("delivery_type", "Самовивіз")
    address = data.get("address", "-")
    contact = message.contact
    user = message.from_user

    total = sum([i['price'] for i in cart])
    items_str = ", ".join([f"{i['name']} ({i['price']}грн)" for i in cart])

    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, username, full_name, phone, delivery_type, address, items, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user.id, user.username or "", user.full_name, contact.phone_number, delivery_type, address, items_str, total))
    
    cashback = int(total * 0.05)
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (cashback, user.id))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ Замовлення успішно оформлене!\n"
        f"🎁 Вам нараховано кешбек: +{cashback} грн на баланс!\n\n"
        f"Бариста вже прийняв замовлення в роботу.",
        reply_markup=types.ReplyKeyboardRemove()
    )

    admin_text = "НОВЕ ЗАМОВЛЕННЯ #PRO!\nТип: " + delivery_type + "\nАдреса: " + address + "\nТовари: " + items_str + "\nСума: " + str(total) + " грн\nКлієнт: " + user.full_name + "\nТелефон: " + contact.phone_number
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text)

    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"rate_{i}")
    builder.adjust(1)

    await message.answer("Будь ласка, оцініть якість нашого сервісу:", reply_markup=builder.as_markup())
    await state.clear()

@dp.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: types.CallbackQuery):
    rating = int(callback.data.split("_")[1])
    user = callback.from_user
    
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, rating, comment) VALUES (?, ?, ?)", (user.id, rating, "Оцінка зірочками"))
    conn.commit()
    conn.close()

    try:
        await callback.message.edit_text(f"Дякуємо за вашу оцінку ({rating} ⭐)! Це допомагає нам ставати кращими.")
    except TelegramBadRequest:
        pass
    
    await callback.message.answer("Головне меню:", reply_markup=main_menu(user.id))
    await callback.answer()

@dp.callback_query(F.data == "admin_panel", F.from_user.id == ADMIN_ID)
async def admin_panel(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Переглянути замовлення", callback_data="admin_orders")
    builder.button(text="⭐ Переглянути відгуки", callback_data="admin_reviews")
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    builder.adjust(1)
    
    try:
        await callback.message.edit_text("⚙️ Професійна панель керування:", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "admin_orders", F.from_user.id == ADMIN_ID)
async def admin_view_orders(callback: types.CallbackQuery):
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, phone, delivery_type, items, total FROM orders ORDER BY id DESC LIMIT 5")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Історія замовлень порожня.", show_alert=True)
        return

    text = "📋 Останні замовлення:\n\n"
    for o in orders:
        text += f"🆔 Замовлення #{o[0]}\n👤 {o[1]} ({o[2]})\n📦 {o[3]} | Адреса: {o[4]}\n🛒 {o[5]}\n💰 Сума: {o[6]} грн\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в адмінку", callback_data="admin_panel")

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "admin_reviews", F.from_user.id == ADMIN_ID)
async def admin_view_reviews(callback: types.CallbackQuery):
    conn = sqlite3.connect("coffee_shop_pro.db")
    cursor = conn.cursor()
    cursor.execute("SELECT rating, comment FROM reviews ORDER BY id DESC LIMIT 5")
    reviews = cursor.fetchall()
    conn.close()

    if not reviews:
        await callback.answer("Поки немає відгуків.", show_alert=True)
        return

    text = "⭐ Останні відгуки клієнтів:\n\n"
    for r in reviews:
        text += f"Оцінка: {'⭐' * r[0]}\nКоментар: {r[1]}\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в адмінку", callback_data="admin_panel")

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

async def main():
    await web_server()
    print("PRO MAX Bot запущено версія 2!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
