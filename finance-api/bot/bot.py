"""
Телеграм-бот «My personal Wallet».

Отдельный клиент того же REST API, что и сайт: логинится тем же email/паролем,
получает JWT-токен и работает с общими данными.
Управление — через кнопки-меню (команды тоже работают как псевдонимы).
"""

import asyncio
import logging
import os
from io import BytesIO

import httpx
import matplotlib
matplotlib.use("Agg")  # рисуем картинки без графического окна
import matplotlib.pyplot as plt
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

# ---------- Настройки ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

sessions: dict[int, str] = {}  # telegram_id -> JWT-токен

# ---------- Тексты кнопок меню ----------
BTN_BALANCE = "💰 Баланс"
BTN_ADD = "➕ Добавить операцию"
BTN_LIST = "📋 Операции"
BTN_CHART = "📊 График"
BTN_CATS = "🗂 Категории"
BTN_DEBTS = "💳 Долги"
BTN_EXPORT = "📄 Excel"
BTN_LOGOUT = "🚪 Выйти"
BTN_LOGIN = "🔐 Войти"
BTN_REGISTER = "🆕 Регистрация"
BTN_BACK = "⬅️ Назад в меню"

# мягкая подсказка при отрицательном балансе
NEG_BALANCE_NOTE = (
    "\n\n⚠️ Похоже, расходы превысили доходы — баланс отрицательный. "
    "Возможно, вы забыли внести какой-то доход. Добавьте операцию дохода "
    "для корректного учёта."
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_ADD)],
            [KeyboardButton(text=BTN_LIST), KeyboardButton(text=BTN_CHART)],
            [KeyboardButton(text=BTN_CATS), KeyboardButton(text=BTN_DEBTS)],
            [KeyboardButton(text=BTN_EXPORT), KeyboardButton(text=BTN_LOGOUT)],
        ],
        resize_keyboard=True,
    )


def login_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_LOGIN), KeyboardButton(text=BTN_REGISTER)]],
        resize_keyboard=True,
    )


def back_menu() -> ReplyKeyboardMarkup:
    # во время диалогов показываем только кнопку возврата
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_BACK)]], resize_keyboard=True)


# ---------- Состояния диалогов (FSM) ----------
class Login(StatesGroup):
    email = State()
    password = State()


class Register(StatesGroup):
    email = State()
    password = State()


class AddTx(StatesGroup):
    amount = State()
    type = State()
    category = State()
    description = State()


class AddCat(StatesGroup):
    name = State()
    type = State()


class AddDebt(StatesGroup):
    counterparty = State()
    amount = State()
    direction = State()


# ---------- Обёртка над запросами к API ----------
async def api(method, path, token=None, json=None, data=None, params=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=API_URL, timeout=10) as client:
        return await client.request(method, path, headers=headers, json=json, data=data, params=params)


def fmt_money(value) -> str:
    n = float(value)
    s = f"{abs(n):,.2f}".replace(",", " ").replace(".", ",")
    return ("−" if n < 0 else "") + s + " ₽"


def fmt_int(value) -> str:
    return f"{int(round(float(value))):,}".replace(",", " ") + " ₽"


def require_login(uid: int):
    return sessions.get(uid)


# ========================= ОБЩИЕ =========================
@dp.message(CommandStart())
@dp.message(Command("help"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if require_login(message.from_user.id):
        await message.answer("Главное меню — выбирай кнопку 👇", reply_markup=main_menu())
    else:
        await message.answer(
            "👋 «My personal Wallet».\n\n"
            "Войдите тем же email и паролем, что на сайте — данные будут общими.\n"
            "Если аккаунта ещё нет — нажмите «🆕 Регистрация».",
            reply_markup=login_menu(),
        )


# Кнопка/команда возврата работает в любом диалоге (зарегистрирована рано)
@dp.message(F.text == BTN_BACK)
@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню 👇", reply_markup=main_menu())


# ========================= ВХОД / ВЫХОД =========================
@dp.message(F.text == BTN_LOGIN)
@dp.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    await state.set_state(Login.email)
    await message.answer("📧 Введите email:", reply_markup=back_menu())


@dp.message(Login.email)
async def login_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip().lower())
    await state.set_state(Login.password)
    await message.answer("🔑 Введите пароль:", reply_markup=back_menu())


@dp.message(Login.password)
async def login_password(message: Message, state: FSMContext):
    data = await state.get_data()
    email = data["email"]
    password = message.text
    await state.clear()
    try:
        resp = await api("POST", "/auth/login", data={"username": email, "password": password})
    except httpx.HTTPError:
        await message.answer("⚠️ Сервер недоступен. Запущен ли uvicorn?", reply_markup=login_menu())
        return
    if resp.status_code == 200:
        sessions[message.from_user.id] = resp.json()["access_token"]
        await message.answer("✅ Вход выполнен!", reply_markup=main_menu())
    else:
        await message.answer("❌ Неверный email или пароль.", reply_markup=login_menu())


@dp.message(F.text == BTN_LOGOUT)
@dp.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext):
    await state.clear()
    sessions.pop(message.from_user.id, None)
    await message.answer("Вы вышли из аккаунта.", reply_markup=login_menu())


# ========================= РЕГИСТРАЦИЯ =========================
@dp.message(F.text == BTN_REGISTER)
@dp.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    await state.set_state(Register.email)
    await message.answer("📧 Придумайте логин — введите email:", reply_markup=back_menu())


@dp.message(Register.email)
async def register_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip().lower())
    await state.set_state(Register.password)
    await message.answer("🔑 Придумайте пароль (не менее 6 символов):", reply_markup=back_menu())


@dp.message(Register.password)
async def register_password(message: Message, state: FSMContext):
    data = await state.get_data()
    email = data["email"]
    password = message.text.strip()
    await state.clear()
    if len(password) < 6:
        await message.answer(
            "❌ Пароль слишком короткий (минимум 6 символов). Нажмите «🆕 Регистрация» ещё раз.",
            reply_markup=login_menu(),
        )
        return
    try:
        resp = await api("POST", "/auth/register", json={"email": email, "password": password})
    except httpx.HTTPError:
        await message.answer("⚠️ Сервер недоступен. Запущен ли uvicorn?", reply_markup=login_menu())
        return
    if resp.status_code == 201:
        # сразу выполняем вход, чтобы пользователю не вводить данные повторно
        login_resp = await api("POST", "/auth/login", data={"username": email, "password": password})
        if login_resp.status_code == 200:
            sessions[message.from_user.id] = login_resp.json()["access_token"]
            await message.answer("✅ Аккаунт создан, вы вошли!", reply_markup=main_menu())
        else:
            await message.answer("✅ Аккаунт создан! Теперь войдите.", reply_markup=login_menu())
    elif resp.status_code == 400:
        await message.answer("❌ Такой email уже зарегистрирован — попробуйте войти.", reply_markup=login_menu())
    elif resp.status_code == 422:
        await message.answer("❌ Похоже, email указан некорректно. Попробуйте ещё раз.", reply_markup=login_menu())
    else:
        await message.answer("❌ Не удалось зарегистрироваться. Попробуйте позже.", reply_markup=login_menu())


# ========================= БАЛАНС =========================
@dp.message(F.text == BTN_BALANCE)
@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/stats/balance", token=token)
    if resp.status_code != 200:
        await message.answer("Сессия истекла, войдите заново.", reply_markup=login_menu())
        return
    b = resp.json()
    text = (
        "📊 Ваш баланс:\n\n"
        f"Доходы:  {fmt_money(b['income'])}\n"
        f"Расходы: {fmt_money(b['expense'])}\n"
        "———\n"
        f"Итого:   {fmt_money(b['balance'])}"
    )
    if float(b["balance"]) < 0:
        text += NEG_BALANCE_NOTE
    await message.answer(text, reply_markup=main_menu())


# ========================= ОПЕРАЦИИ (СПИСОК) =========================
@dp.message(F.text == BTN_LIST)
@dp.message(Command("list"))
async def cmd_list(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/transactions", token=token)
    if resp.status_code != 200:
        await message.answer("Сессия истекла, войдите заново.", reply_markup=login_menu())
        return
    txs = resp.json()
    cresp = await api("GET", "/categories", token=token)
    cats = {c["id"]: c["name"] for c in cresp.json()} if cresp.status_code == 200 else {}
    if not txs:
        await message.answer("Операций пока нет. Нажмите «➕ Добавить операцию».", reply_markup=main_menu())
        return
    lines = ["🧾 Последние операции:\n"]
    for t in txs[:10]:
        sign = "➕" if t["type"] == "income" else "➖"
        cat = cats.get(t["category_id"], "без категории")
        desc = t.get("description") or cat
        lines.append(f"{sign} {fmt_money(t['amount'])} — {desc} ({t['date']})")
    await message.answer("\n".join(lines), reply_markup=main_menu())


# ========================= ГРАФИК =========================
@dp.message(F.text == BTN_CHART)
@dp.message(Command("chart"))
async def cmd_chart(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/stats/by-category", token=token, params={"type": "expense"})
    if resp.status_code != 200:
        await message.answer("Сессия истекла, войдите заново.", reply_markup=login_menu())
        return
    data = resp.json()
    if not data:
        await message.answer("Пока нет расходов для графика.", reply_markup=main_menu())
        return

    # Названия категорий и суммы выносим в легенду сбоку, а не на сам круг —
    # так подписи мелких долек не наслаиваются друг на друга.
    names = [(d["category_name"] or "Без категории") for d in data]
    values = [float(d["total"]) for d in data]
    total = sum(values) or 1.0
    colors = plt.cm.tab20.colors

    fig, ax = plt.subplots(figsize=(8, 6))

    # проценты пишем внутри долек, и только для достаточно крупных,
    # чтобы у тонких секторов не было нечитаемой мешанины
    def _autopct(pct):
        return f"{pct:.1f}%" if pct >= 4 else ""

    wedges, _texts, autotexts = ax.pie(
        values,
        startangle=90,
        counterclock=False,
        colors=colors[: len(values)],
        autopct=_autopct,
        pctdistance=0.78,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(10)
        t.set_fontweight("bold")

    ax.set_title("Расходы по категориям", fontsize=14, fontweight="bold")
    ax.axis("equal")

    legend_labels = [
        f"{name} — {fmt_int(val)} ({val / total * 100:.1f}%)"
        for name, val in zip(names, values)
    ]
    ax.legend(
        wedges,
        legend_labels,
        title="Категории",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=10,
    )

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    await message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="chart.png"),
        caption="📊 Расходы по категориям",
        reply_markup=main_menu(),
    )


# ========================= EXCEL =========================
@dp.message(F.text == BTN_EXPORT)
@dp.message(Command("export"))
async def cmd_export(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/transactions/export", token=token)
    if resp.status_code != 200:
        await message.answer("Не удалось сформировать файл. Войдите заново.", reply_markup=login_menu())
        return
    await message.answer_document(
        BufferedInputFile(resp.content, filename="operations.xlsx"),
        caption="📄 Ваши операции (Excel)",
        reply_markup=main_menu(),
    )


# ========================= КАТЕГОРИИ =========================
@dp.message(F.text == BTN_CATS)
@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/categories", token=token)
    if resp.status_code != 200:
        await message.answer("Сессия истекла, войдите заново.", reply_markup=login_menu())
        return
    cats = resp.json()
    if cats:
        lines = ["🗂 Ваши категории:\n"]
        for c in cats:
            kind = "доход" if c["type"] == "income" else "расход"
            lines.append(f"• {c['name']} ({kind})")
        text = "\n".join(lines)
    else:
        text = "Категорий пока нет."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Новая категория", callback_data="newcat")]])
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "newcat")
async def newcat_start(call: CallbackQuery, state: FSMContext):
    if not require_login(call.from_user.id):
        await call.answer("Сначала войдите", show_alert=True)
        return
    await state.set_state(AddCat.name)
    await call.message.answer("Введите название категории:", reply_markup=back_menu())
    await call.answer()


@dp.message(AddCat.name)
async def newcat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddCat.type)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Доход", callback_data="catype:income"),
        InlineKeyboardButton(text="➖ Расход", callback_data="catype:expense"),
    ]])
    await message.answer("Тип категории:", reply_markup=kb)


@dp.callback_query(AddCat.type, F.data.startswith("catype:"))
async def newcat_type(call: CallbackQuery, state: FSMContext):
    op = call.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    token = require_login(call.from_user.id)
    resp = await api("POST", "/categories", token=token, json={"name": data["name"], "type": op})
    await call.message.edit_text("✅ Категория добавлена!" if resp.status_code == 201 else "❌ Не удалось добавить.")
    await call.message.answer("Главное меню 👇", reply_markup=main_menu())
    await call.answer()


# ========================= ДОЛГИ =========================
@dp.message(F.text == BTN_DEBTS)
@dp.message(Command("debts"))
async def cmd_debts(message: Message):
    token = require_login(message.from_user.id)
    if not token:
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    resp = await api("GET", "/debts", token=token)
    if resp.status_code != 200:
        await message.answer("Сессия истекла, войдите заново.", reply_markup=login_menu())
        return
    debts = resp.json()
    if debts:
        lines = ["💳 Ваши долги:\n"]
        for d in debts:
            arrow = "🔴 я должен" if d["direction"] == "i_owe" else "🟢 мне должны"
            st = " — погашен" if d["is_settled"] else ""
            lines.append(f"{arrow}: {d['counterparty']} — {fmt_money(d['amount'])}{st}")
        text = "\n".join(lines)
    else:
        text = "Долгов пока нет."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Новый долг", callback_data="newdebt")]])
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "newdebt")
async def newdebt_start(call: CallbackQuery, state: FSMContext):
    if not require_login(call.from_user.id):
        await call.answer("Сначала войдите", show_alert=True)
        return
    await state.set_state(AddDebt.counterparty)
    await call.message.answer("Кто или кому (имя):", reply_markup=back_menu())
    await call.answer()


@dp.message(AddDebt.counterparty)
async def newdebt_name(message: Message, state: FSMContext):
    await state.update_data(counterparty=message.text.strip())
    await state.set_state(AddDebt.amount)
    await message.answer("Сумма долга:", reply_markup=back_menu())


@dp.message(AddDebt.amount)
async def newdebt_amount(message: Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число, например 1000")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddDebt.direction)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔴 Я должен", callback_data="ddir:i_owe"),
        InlineKeyboardButton(text="🟢 Мне должны", callback_data="ddir:owed_to_me"),
    ]])
    await message.answer("Направление:", reply_markup=kb)


@dp.callback_query(AddDebt.direction, F.data.startswith("ddir:"))
async def newdebt_dir(call: CallbackQuery, state: FSMContext):
    direction = call.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    token = require_login(call.from_user.id)
    payload = {"counterparty": data["counterparty"], "amount": data["amount"], "direction": direction}
    resp = await api("POST", "/debts", token=token, json=payload)
    await call.message.edit_text("✅ Долг добавлен!" if resp.status_code == 201 else "❌ Не удалось добавить.")
    await call.message.answer("Главное меню 👇", reply_markup=main_menu())
    await call.answer()


# ========================= ДОБАВЛЕНИЕ ОПЕРАЦИИ =========================
@dp.message(F.text == BTN_ADD)
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if not require_login(message.from_user.id):
        await message.answer("Сначала войдите.", reply_markup=login_menu())
        return
    await state.set_state(AddTx.amount)
    await message.answer("💰 Введите сумму операции:", reply_markup=back_menu())


@dp.message(AddTx.amount)
async def add_amount(message: Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число, например 500")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddTx.type)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Доход", callback_data="type:income"),
        InlineKeyboardButton(text="➖ Расход", callback_data="type:expense"),
    ]])
    await message.answer("Это доход или расход?", reply_markup=kb)


@dp.callback_query(AddTx.type, F.data.startswith("type:"))
async def add_type(call: CallbackQuery, state: FSMContext):
    op_type = call.data.split(":")[1]
    await state.update_data(type=op_type)
    token = require_login(call.from_user.id)
    resp = await api("GET", "/categories", token=token)
    cats = [c for c in resp.json() if c["type"] == op_type] if resp.status_code == 200 else []
    rows = [[InlineKeyboardButton(text=c["name"], callback_data=f"cat:{c['id']}")] for c in cats]
    rows.append([InlineKeyboardButton(text="Без категории", callback_data="cat:none")])
    await state.set_state(AddTx.category)
    await call.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@dp.callback_query(AddTx.category, F.data.startswith("cat:"))
async def add_category(call: CallbackQuery, state: FSMContext):
    raw = call.data.split(":")[1]
    category_id = None if raw == "none" else int(raw)
    await state.update_data(category_id=category_id)
    await state.set_state(AddTx.description)
    await call.message.edit_text("Категория выбрана.")
    await call.message.answer("✏️ Введите описание (или «-», чтобы пропустить):", reply_markup=back_menu())
    await call.answer()


@dp.message(AddTx.description)
async def add_description(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    description = None if message.text.strip() == "-" else message.text.strip()
    payload = {"amount": data["amount"], "type": data["type"]}
    if data.get("category_id"):
        payload["category_id"] = data["category_id"]
    if description:
        payload["description"] = description
    token = require_login(message.from_user.id)
    resp = await api("POST", "/transactions", token=token, json=payload)
    if resp.status_code == 201:
        bresp = await api("GET", "/stats/balance", token=token)
        bjson = bresp.json() if bresp.status_code == 200 else None
        bal = fmt_money(bjson["balance"]) if bjson else "—"
        msg = f"✅ Операция добавлена!\nНовый баланс: {bal}\n\nОна уже видна на сайте 🌐"
        if bjson and float(bjson["balance"]) < 0:
            msg += NEG_BALANCE_NOTE
        await message.answer(msg, reply_markup=main_menu())
    else:
        await message.answer("❌ Не удалось добавить операцию.", reply_markup=main_menu())


# ========================= ЗАПУСК =========================
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN. Впишите его в файл .env")
    print("Бот запущен. Откройте его в Telegram и отправьте /start")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
