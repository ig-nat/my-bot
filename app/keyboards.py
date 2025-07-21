from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Основное меню с кнопкой "регистрация экрана"
main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='регистрация экрана')]
    ],
    resize_keyboard=True
)

# Клавиатура для отмены
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

# Клавиатура для администратора
# Обновленная админская клавиатура с кнопками сброса
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔄 Обновить заявки")],
        [KeyboardButton(text="🔁 Сбросить пользователя"), KeyboardButton(text="⚠️ Сбросить всех")],
        [KeyboardButton(text="📄 Экспорт данных"), KeyboardButton(text="🧹 Очистка хранилища")],
        [KeyboardButton(text="🔙 Вернуться")]
    ],
    resize_keyboard=True
)

# Добавьте эту клавиатуру в ваш файл keyboards.py
waiting_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏳ Ожидание проверки")]
    ],
    resize_keyboard=True
)
# Основное меню с кнопками "регистрация экрана" и "замена оборудования"
main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='регистрация экрана')],
        [KeyboardButton(text='замена оборудования')]
    ],
    resize_keyboard=True
)

# Клавиатура выбора типа замены
replacement_type_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='замена OPS')],
        [KeyboardButton(text='замена Телевизора')],
        [KeyboardButton(text='❌ Отмена')]
    ],
    resize_keyboard=True
)
# Клавиатура выбора периода статистики
stats_period_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 За сегодня", callback_data="stats_today"),
            InlineKeyboardButton(text="📊 За все время", callback_data="stats_all_time")
        ],
        [
            InlineKeyboardButton(text="📆 За выбранный период", callback_data="stats_custom_period")
        ]
    ]
)
# Инлайн-клавиатуры для различных сценариев
catalog1 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Сиреневый экран!', callback_data='ура мы дошли до регистрации!')],
        [InlineKeyboardButton(text='Чёрный экран', callback_data='перегрузи')]
    ]
)

catalog2 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='нет', callback_data='проверяй светодиоды')],
        [InlineKeyboardButton(text='да', callback_data='да конечно')],
        [InlineKeyboardButton(text='а как он выглядит???', url='https://www.google.com')]
    ]
)

catalog3 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='проверил. она в порядке', callback_data='разбирайся')],
        [InlineKeyboardButton(text='проверил. она не в порядке', callback_data='доставай')]
    ]
)

catalog4 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text='не знаю распиновку',
            url='https://jeka.by/upload/userfiles/1/images/rj45%20%D0%BF%D0%BE%20%D1%86%D0%B2%D0%B5%D1%82%D0%B0%D0%BC.gif'
        )]
    ]
)

catalog5 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='моргают', callback_data='убедись')],
        [InlineKeyboardButton(text='НЕ моргают', callback_data='меняй провод')]
    ]
)

# Полная клавиатура для модератора
moderator_full = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data="accept_registration"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_registration")
        ],
        [
            InlineKeyboardButton(text="——— ПРОБЛЕМЫ СО СВЯЗЬЮ ———", callback_data="ignore")
        ],
        [
            InlineKeyboardButton(text="🔴 НЕТ СВЯЗИ", callback_data="no_connection"),
            InlineKeyboardButton(text="⚠️ ПЛОХАЯ СВЯЗЬ", callback_data="bad_connection")
        ],
        [
            InlineKeyboardButton(text="🔄 СМЕНА ПОРТА", callback_data="change_port"),
            InlineKeyboardButton(text="🔌 ПЕРЕЗАГРУЗИ ТВ", callback_data="restart_tv")
        ],
        [
            InlineKeyboardButton(text="💬 СВЯЗЬ С МОНТАЖНИКОМ", callback_data="contact_user")
        ]
    ]
)


# Клавиатура для проверки связи
check_connection_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔵 Я ВЫПОЛНИЛ, ПРОВЕРЬТЕ СВЯЗЬ ЕЩЁ РАЗ 🔵", callback_data="check_connection_again")
        ]
    ]
)

# Клавиатура для результата проверки связи
connection_result_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ты молодец! Связь есть", callback_data="connection_restored")
        ],
        [
            InlineKeyboardButton(text="❌ Связь так и не появилась", callback_data="connection_still_bad")
        ]
    ]
)

# Словарь для удобного доступа к клавиатурам
# В словарь kb добавить новые клавиатуры
kb = {
    "main": main,
    "cancel_kb": cancel_kb,
    "admin": admin_kb,
    "replacement_type_kb": replacement_type_kb,  # если есть
    "catalog1": catalog1,
    "catalog2": catalog2,
    "catalog3": catalog3,
    "catalog4": catalog4,
    "catalog5": catalog5,
    "moderator_full": moderator_full,
    "check_connection_kb": check_connection_kb,
    "connection_result_kb": connection_result_kb,
    "stats_period_kb": stats_period_kb  # Добавить эту строку
}

