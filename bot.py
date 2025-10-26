import pandas as pd
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# === Настройки ===
TOKEN = "8291705742:AAH1cgkPmJWVZLum7U8CwF84dCGJIau7XuY"
CSV_FILE = "bonds.csv"

# Хранилище фильтров по пользователям
user_filters = {}

def load_bonds():
    df = pd.read_csv(CSV_FILE, sep=";", on_bad_lines='skip', dtype=str)
    numeric_cols = [
        "Эффективная доходность (YTM), %",
        "Кредитное качество (число, max=10)",
        "Коэф. Ликвидности (max=100)",
        "Лет до даты",
        "Купон (раз/год)",
        "чистая прибыль",
        "ROI (всего)"  # <-- новый столбец
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    return df

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используйте /filter для подбора облигаций.")

async def show_filter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    chat_id = chat_id or update.effective_chat.id
    if chat_id not in user_filters:
        user_filters[chat_id] = {
            "sort_by": "чистая прибыль"
        }

    filters = user_filters[chat_id]
    text = "📊 Выберите фильтр:\n\n"
    for key, val in filters.items():
        if key != "sort_by":
            text += f"✅ {key}: {val}\n"
    text += f"\nСортировка: {filters['sort_by']}"

    keyboard = [
        [InlineKeyboardButton("YTM", callback_data="filter_ytm")],
        [InlineKeyboardButton("Кредитное качество (число)", callback_data="filter_rating")],
        [InlineKeyboardButton("Ликвидность", callback_data="filter_liquidity")],
        [InlineKeyboardButton("Срок (Лет до даты)", callback_data="filter_years")],
        [InlineKeyboardButton("Тип купона", callback_data="filter_coupon_type")],
        [InlineKeyboardButton("Купон (раз/год)", callback_data="filter_freq")],
        [InlineKeyboardButton("Сортировка", callback_data="filter_sort")],
        [InlineKeyboardButton("🔄 Сбросить фильтры", callback_data="reset_filters")],
        [InlineKeyboardButton("✅ Показать топ-20", callback_data="show_top20")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    except:
        pass

# Обработка выбора фильтра
async def handle_filter_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "show_top20":
        await show_top20(update, context)
        return

    if data == "reset_filters":
        chat_id = query.message.chat.id
        user_filters[chat_id] = {"sort_by": "чистая прибыль"}
        await show_filter_menu(update, context, chat_id)
        return

    if data == "filter_sort":
        keyboard = [
            [InlineKeyboardButton("По чистой прибыли", callback_data="sort_profit")],
            [InlineKeyboardButton("По YTM", callback_data="sort_ytm")],
            [InlineKeyboardButton("По ROI (всего)", callback_data="sort_roi")],
            [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]
        ]
        await query.edit_message_text("Выберите сортировку:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    filter_names = {
        "filter_ytm": "YTM",
        "filter_rating": "Кредитное качество (число)",
        "filter_liquidity": "Ликвидность",
        "filter_years": "Срок (Лет до даты)",
        "filter_coupon_type": "Тип купона",
        "filter_freq": "Купон (раз/год)"
    }

    descriptions = {
        "YTM": "Введите диапазон YTM в формате: от-до\nПример: 25-40",
        "Кредитное качество (число)": "Введите диапазон (1–10):\nПример: 5-10",
        "Ликвидность": "Введите диапазон (0–100):\nПример: 40-100",
        "Срок (Лет до даты)": "Введите диапазон срока:\nПример: 0-2",
        "Тип купона": "Введите тип купона:\nПример: фиксированный",
        "Купон (раз/год)": "Введите число выплат в год:\nПример: 12"
    }

    context.user_data['awaiting_filter'] = filter_names[data]
    await query.edit_message_text(
        text=descriptions[filter_names[data]],
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])
    )

# Обработка текстового ввода значения фильтра
async def handle_filter_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'awaiting_filter' not in context.user_data:
        return

    chat_id = update.effective_chat.id
    filter_name = context.user_data['awaiting_filter']
    value = update.message.text.strip()

    if chat_id not in user_filters:
        user_filters[chat_id] = {"sort_by": "чистая прибыль"}
    user_filters[chat_id][filter_name] = value
    del context.user_data['awaiting_filter']

    await show_filter_menu(update, context, chat_id)

# Обработка выбора сортировки
async def handle_sort_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if chat_id not in user_filters:
        user_filters[chat_id] = {"sort_by": "чистая прибыль"}

    if query.data == "sort_profit":
        user_filters[chat_id]["sort_by"] = "чистая прибыль"
    elif query.data == "sort_ytm":
        user_filters[chat_id]["sort_by"] = "Эффективная доходность (YTM), %"
    elif query.data == "sort_roi":
        user_filters[chat_id]["sort_by"] = "ROI (всего)"

    await show_filter_menu(update, context, chat_id)

# Назад в меню
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_filter_menu(update, context)

# Показ топ-20
async def show_top20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    filters = user_filters.get(chat_id, {"sort_by": "чистая прибыль"})
    df = load_bonds()

    try:
        if "YTM" in filters:
            low, high = map(float, filters["YTM"].split('-'))
            df = df[(df["Эффективная доходность (YTM), %"] >= low) & (df["Эффективная доходность (YTM), %"] <= high)]

        if "Кредитное качество (число)" in filters:
            low, high = map(float, filters["Кредитное качество (число)"].split('-'))
            df = df[(df["Кредитное качество (число, max=10)"] >= low) & (df["Кредитное качество (число, max=10)"] <= high)]

        if "Ликвидность" in filters:
            low, high = map(float, filters["Ликвидность"].split('-'))
            df = df[(df["Коэф. Ликвидности (max=100)"] >= low) & (df["Коэф. Ликвидности (max=100)"] <= high)]

        if "Срок (Лет до даты)" in filters:
            low, high = map(float, filters["Срок (Лет до даты)"].split('-'))
            df = df[(df["Лет до даты"] >= low) & (df["Лет до даты"] <= high)]

        if "Тип купона" in filters:
            coupon_type = filters["Тип купона"]
            df = df[df["Тип купона"].str.contains(coupon_type, case=False, na=False)]

        if "Купон (раз/год)" in filters:
            freq = int(filters["Купон (раз/год)"])
            df = df[df["Купон (раз/год)"] == freq]

        sort_col = filters["sort_by"]
        df = df.sort_values(by=sort_col, ascending=False).head(20)

        if df.empty:
            text = "❌ Нет облигаций по заданным фильтрам."
        else:
            text = "🏆 Топ-20 облигаций:\n\n"
            for _, row in df.iterrows():
                name = row["Название"]
                isin = row["ISIN"]
                ytm = row["Эффективная доходность (YTM), %"]
                rating = row["Кредитное качество (число, max=10)"]
                liq = row["Коэф. Ликвидности (max=100)"]
                years = row["Лет до даты"]
                coupon_type = row["Тип купона"]
                freq = row["Купон (раз/год)"]
                profit = row["чистая прибыль"]
                roi = row["ROI (всего)"]

                # Форматирование ROI в %
                roi_str = f"{roi:.1%}" if pd.notna(roi) else "—"

                text += (
                    f"• {name} ({isin})\n"
                    f"  YTM: {ytm:.1f}% | Качество: {rating} | Ликв: {liq}\n"
                    f"  Срок: {years:.1f} лет | ROI: {roi_str}\n"
                    f"  Купон: {coupon_type}, {freq}/год\n"
                    f"  Прибыль: {profit:.0f} руб.\n\n"
                )
            if len(text) > 4090:
                text = text[:4090] + "…"

        keyboard = [[InlineKeyboardButton("← Назад к фильтрам", callback_data="back_to_menu")]]
        await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        await update.callback_query.edit_message_text(
            text=f"Ошибка в фильтрах: {e}\nПопробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])
        )

# Запуск
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filter", show_filter_menu))
    app.add_handler(CallbackQueryHandler(handle_filter_choice, pattern="^filter_"))
    app.add_handler(CallbackQueryHandler(handle_sort_choice, pattern="^sort_"))
    app.add_handler(CallbackQueryHandler(show_top20, pattern="^show_top20$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(handle_filter_choice, pattern="^reset_filters$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_filter_value))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
