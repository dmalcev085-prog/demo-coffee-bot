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
    INITIAL_SERVICES
)

# === БАЗА ДАНИХ ===
def init_db():
    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    # Таблиця товарів/меню
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER
        )
    """)
    # Таблиця замовлень
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            items TEXT,
            total INTEGER
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] == 0:
        for name, price in INITIAL_SERVICES.items():
            cursor.execute("INSERT OR IGNORE INTO services (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    conn.close()

init_db()

# Вебсервер для Render
async def handle(request):
    return web.Response(text="Pro Demo Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Вебсервер запущено на порту {port}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class OrderState(StatesGroup):
    waiting_for_phone = State()
    admin_add_name = State()
    admin_add_price = State()

class AdminState(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_product_price = State()

# Головне меню
def main_menu(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Наше меню та ціни", callback_data="services")
    builder.button(text="🛒 Зробити замовлення", callback_data="start_order")
    builder.button(text="📍 Де нас знайти", callback_data="location")
    if is_admin:
        builder.button(text="⚙️ Адмін-панель", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer(
        f"Вітаємо у затишній кав'ярні **{COMPANY_NAME}**! ☕🥐\nОберіть потрібний розділ:",
        parse_mode="Markdown",
        reply_markup=main_menu(is_admin)
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    is_admin = (callback.from_user.id == ADMIN_ID)
    try:
        await callback.message.edit_text("Головне меню:", reply_markup=main_menu(is_admin))
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "services")
async def show_services(callback: types.CallbackQuery):
    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM services")
    items = cursor.fetchall()
    conn.close()

    menu_text = f"📋 **Меню нашої кав'ярні:**\n\n"
    for name, price in items:
        menu_text += f"🔹 **{name}** — {price} грн\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    
    try:
        await callback.message.edit_text(menu_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "location")
async def show_location(callback: types.CallbackQuery):
    is_admin = (callback.from_user.id == ADMIN_ID)
    try:
        await callback.message.edit_text(
            f"📍 **Адреса:**\n{COMPANY_ADDRESS}\n\n"
            f"⏰ **Графік роботи:**\n{WORKING_HOURS}\n\n"
            f"📞 **Телефон:** {ADMIN_PHONE}",
            parse_mode="Markdown",
            reply_markup=main_menu(is_admin)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

# === ЛОГІКА КОШИКА ===
@dp.callback_query(F.data == "start_order")
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await show_cart_selection(callback.message, state, edit=True)
    await callback.answer()

async def show_cart_selection(message: types.Message, state: FSMContext, edit=False):
    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM services")
    items = cursor.fetchall()
    conn.close()

    data = await state.get_data()
    cart = data.get("cart", [])

    cart_text = "🛒 **Ваше замовлення (Кошик):**\n"
    total = 0
    if cart:
        for item in cart:
            cart_text += f"• {item['name']} — {item['price']} грн\n"
            total += item['price']
        cart_text += f"\n**Загалом до сплати:** {total} грн\n\n"
    else:
        cart_text += "Кошик порожній. Оберить позиції нижче:\n\n"

    builder = InlineKeyboardBuilder()
    for item_id, name, price in items:
        builder.button(text=f"➕ {name} ({price} грн)", callback_data=f"add_to_cart_{item_id}")
    
    if cart:
        builder.button(text="✅ Підтвердити замовлення", callback_data="checkout")
    
    builder.button(text="🗑 Очистити кошик", callback_data="clear_cart")
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    builder.adjust(1)

    if edit:
        try:
            await message.edit_text(cart_text, parse_mode="Markdown", reply_markup=builder.as_markup())
        except TelegramBadRequest:
            pass
    else:
        await message.answer(cart_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("add_to_cart_"))
async def add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[3])
    conn = sqlite3.connect("coffee_shop.db")
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
    await callback.answer("Додано до кошика! 🛒")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await show_cart_selection(callback.message, state, edit=True)
    await callback.answer("Кошик очищено.")

@dp.callback_query(F.data == "checkout")
async def checkout(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.answer("Кошик порожній!", show_alert=True)
        return

    await state.set_state(OrderState.waiting_for_phone)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Надіслати номер телефону", request_contact=True)
    builder.button(text="❌ Скасувати")
    builder.adjust(1)

    await callback.message.answer(
        "Для завершення замовлення поділіться номером телефону:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await callback.answer()

@dp.message(F.text == "❌ Скасувати")
async def cancel_order(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer("Замовлення скасовано.", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Головне меню:", reply_markup=main_menu(is_admin))

@dp.message(OrderState.waiting_for_phone, F.contact)
async def get_contact_checkout(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    contact = message.contact
    user = message.from_user

    items_str = ", ".join([f"{i['name']} ({i['price']}грн)" for i in cart])
    total = sum([i['price'] for i in cart])

    # Зберігаємо замовлення в БД
    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, username, full_name, phone, items, total)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user.id, user.username or "", user.full_name, contact.phone_number, items_str, total))
    conn.commit()
    conn.close()

    await message.answer(
        "✅ **Дякуємо за замовлення!**\nБариста вже готує, а менеджер зв'яжеться з вами.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

    admin_text = (
        f"🚨 **НОВЕ ЗАМОВЛЕННЯ (КОШИК)!**\n\n"
        f"🛒 **Товари:** {items_str}\n"
        f"💰 **Сума:** {total} грн\n"
        f"👤 **Клієнт:** {user.full_name}\n"
        f"📞 **Телефон:** `{contact.phone_number}`\n"
        f"📱 **Telegram:** @{user.username if user.username else 'немає'}"
    )
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
    await state.clear()
    is_admin = (user.id == ADMIN_ID)
    await message.answer("Головне меню:", reply_markup=main_menu(is_admin))

# === АДМІН-ПАНЕЛЬ ===
@dp.callback_query(F.data == "admin_panel", F.from_user.id == ADMIN_ID)
async def admin_panel(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Додати товар у меню", callback_data="admin_add")
    builder.button(text="📋 Переглянути історію замовлень", callback_data="admin_orders")
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    builder.adjust(1)
    
    try:
        await callback.message.edit_text("⚙️ **Панель керування закладом:**", parse_mode="Markdown", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "admin_add", F.from_user.id == ADMIN_ID)
async def admin_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_product_name)
    await callback.message.answer("Введіть назву нового товару (або напишіть 'скасувати'):")
    await callback.answer()

@dp.message(AdminState.waiting_for_product_name, F.from_user.id == ADMIN_ID)
async def admin_get_product_name(message: types.Message, state: FSMContext):
    if message.text.lower() == 'скасувати':
        await state.clear()
        await message.answer("Скасовано.")
        return
    await state.update_data(new_name=message.text)
    await state.set_state(AdminState.waiting_for_product_price)
    await message.answer("Введіть ціну товару у гривнях (тільки число):")

@dp.message(AdminState.waiting_for_product_price, F.from_user.id == ADMIN_ID)
async def admin_get_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Будь ласка, введіть ціну числом!")
        return
    
    data = await state.get_data()
    name = data.get("new_name")
    price = int(message.text)

    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO services (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Успішно додано товар: **{name}** за ціною **{price} грн**!", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_orders", F.from_user.id == ADMIN_ID)
async def admin_view_orders(callback: types.CallbackQuery):
    conn = sqlite3.connect("coffee_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, phone, items, total FROM orders ORDER BY id DESC LIMIT 5")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Історія замовлень поки порожня.", show_alert=True)
        return

    text = "📋 **Останні 5 замовлень:**\n\n"
    for o in orders:
        text += f"🆔 Замовлення #{o[0]}\n👤 Клієнт: {o[1]} ({o[2]})\n🛒 {o[3]}\n💰 Сума: {o[4]} грн\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в адмінку", callback_data="admin_panel")

    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass
    await callback.answer()

async def main():
    await web_server()
    print("Прокачаний демо-бот запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
