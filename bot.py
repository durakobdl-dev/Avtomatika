"""Бот-помощник техникума: разделы, подтемы и вопросы кнопками."""
import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import faq

router = Router()


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows])


# ---------- экраны: возвращают (текст, список рядов кнопок) ----------
def main_menu():
    rows = [[(title, f"s:{i}")] for i, (title, _) in enumerate(faq.SECTIONS)]
    return faq.WELCOME, rows


def section_view(si):
    title, topics = faq.SECTIONS[si]
    if len(topics) == 1:                      # одна подтема: сразу показываем вопросы
        return topic_view(si, 0)
    rows = [[(t_title, f"t:{si}:{ti}")] for ti, (t_title, _) in enumerate(topics)]
    rows.append([("⬅️ В меню", "menu")])
    return f"<b>{title}</b>\n\nВыберите тему:", rows


def topic_view(si, ti):
    s_title, topics = faq.SECTIONS[si]
    t_title, questions = topics[ti]
    rows = [[(q, f"q:{si}:{ti}:{qi}")] for qi, (q, _, _) in enumerate(questions)]
    back = "menu" if len(topics) == 1 else f"s:{si}"
    rows.append([("⬅️ Назад", back), ("🏠 В меню", "menu")])
    return f"<b>{t_title}</b>\n\nВыберите вопрос:", rows


def answer_view(si, ti, qi):
    _, topics = faq.SECTIONS[si]
    _, questions = topics[ti]
    q, a, verified = questions[qi]
    text = f"❓ <b>{q}</b>\n\n{a}" + ("" if verified else faq.CHECK_NOTE)
    rows = [[("⬅️ К вопросам", f"t:{si}:{ti}"), ("🏠 В меню", "menu")]]
    return text, rows


# ---------- отправка ----------
async def show(call: CallbackQuery, text, rows):
    try:
        await call.message.edit_text(text, reply_markup=kb(rows), disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await call.message.answer(text, reply_markup=kb(rows), disable_web_page_preview=True)
    await call.answer()


@router.message(CommandStart())
@router.message(Command("menu"))
@router.message(Command("help"))
async def cmd_start(m: Message):
    text, rows = main_menu()
    await m.answer(text, reply_markup=kb(rows))


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    await show(call, *main_menu())


@router.callback_query(F.data.startswith("s:"))
async def cb_section(call: CallbackQuery):
    await show(call, *section_view(int(call.data.split(":")[1])))


@router.callback_query(F.data.startswith("t:"))
async def cb_topic(call: CallbackQuery):
    _, si, ti = call.data.split(":")
    await show(call, *topic_view(int(si), int(ti)))


@router.callback_query(F.data.startswith("q:"))
async def cb_question(call: CallbackQuery):
    _, si, ti, qi = call.data.split(":")
    await show(call, *answer_view(int(si), int(ti), int(qi)))


@router.message(F.text)
async def fallback(m: Message):
    """Любой текст, которого нет в списке: предлагаем сайт и контакты, плюс меню."""
    _, rows = main_menu()
    await m.answer(faq.NOT_FOUND, reply_markup=kb(rows), disable_web_page_preview=True)


# ---------- запуск (веб-сервер нужен, чтобы Render видел, что сервис жив) ----------
async def health_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ok"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "10000"))).start()


async def main():
    logging.basicConfig(level=logging.INFO)
    await health_server()
    bot = Bot(os.environ["BOT_TOKEN"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
