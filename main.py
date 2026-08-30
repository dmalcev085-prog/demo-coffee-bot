import os
import asyncio
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
    SERVICES
)

async def handle(request):
    return web.Response(text="Demo Bot is running!")

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
    waiting_for_service = State()
    waiting_for_phone = State()

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Наше меню та ціни", callback_data="services")
    builder.button(text="🛒 Зробити замовлення", callback_data="start_order")
    builder.button(text="📍 Де нас знайти", callback_data="location")
    builder.adjust(1)
    return builder.as_markup()

def services_menu():
    builder = InlineKeyboardBuilder()
    for key, data in SERVICES.items():
        builder.button(text=f"☕ {data[0]} — {data[1]} грн", callback_data=key)
    builder.button(text="⬅️ Головне меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def phone_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Надіслати номер для зв'язку", request_contact=True)
    builder.button(text="❌ Скасувати")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Вітаємо у затишній кав'ярні **{COMPANY_NAME}**! 🥐\nОберіть потрібний розділ:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(
            "Головне меню:",
            reply_markup=main_menu()
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "services")
async def show_services(callback: types.CallbackQuery):
    try:
        menu_text = f"📋 **Меню нашої кав'ярні:**\n\n"
        for key, data in SERVICES.items():
            menu_text += f"🔹 **{data[0]}** — {data[1]} грн\n"
        menu_text += "\nОберіть позицію нижче:"

        await callback.message.edit_text(
            menu_text,
            parse_mode="Markdown",
            reply_markup=services_menu()
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "location")
async def show_location(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            f"📍 **Адреса:**\n{COMPANY_ADDRESS}\n\n"
            f"⏰ **Графік роботи:**\n{WORKING_HOURS}\n\n"
            f"📞 **Телефон:** {ADMIN_PHONE}",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data == "start_order")
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_service)
    try:
        await callback.message.edit_text(
            "Оберіть позицію з меню, яку бажаєте замовити:",
            reply_markup=services_menu()
        )
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("select_service_"))
async def service_selected(callback: types.CallbackQuery, state: FSMContext):
    service_info = SERVICES.get(callback.data)
    selected_name = f"{service_info[0]} ({service_info[1]} грн)" if service_info else "Позиція"
    
    await state.update_data(chosen_service=selected_name)
    await state.set_state(OrderState.waiting_for_phone)
    
    await callback.message.answer(
        f"Ви обрали: **{selected_name}**.\n\n"
        "Для підтвердження замовлення поділіться номером телефону:",
        parse_mode="Markdown",
        reply_markup=phone_menu()
    )
    await callback.answer()

@dp.message(F.text == "❌ Скасувати")
async def cancel_order(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Замовлення скасовано.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer("Головне меню:", reply_markup=main_menu())

@dp.message(OrderState.waiting_for_phone, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    chosen_service = user_data.get("chosen_service", "Не вказано")
    
    contact = message.contact
    user = message.from_user
    
    await message.answer(
        "✅ **Дякуємо за замовлення!**\n"
        "Бариста вже готує, а менеджер зв'яжеться з вами за хвилину.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    admin_text = (
        f"☕ **НОВЕ ЗАМОВЛЕННЯ З ДЕМО-БОТА!**\n\n"
        f"🛒 **Позиція:** {chosen_service}\n"
        f"👤 **Клієнт:** {user.full_name}\n"
        f"📞 **Телефон:** `{contact.phone_number}`\n"
        f"📱 **Telegram:** @{user.username if user.username else 'немає'}"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
    await state.clear()

async def main():
    await web_server()
    print("Демо-бот кав'ярні запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
