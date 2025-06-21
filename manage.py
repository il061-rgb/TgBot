import telebot
from telebot import types
import sqlite3
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='university_bot.log',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot('7303895887:AAGWZ83wBKfnAeIT3GrRH1A49E62kAcZTJU')

# Фиксированные ключи доступа
STUDENT_KEY = "ITHub2025"
TEACHER_KEY = "IThubTeacher2025"

# Состояния пользователей
user_states = {}


# Подключение к базе данных
def get_db_connection():
    conn = sqlite3.connect('university.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# Инициализация базы данных
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL,
            group_name TEXT,
            registration_date TEXT NOT NULL
        )
        ''')

        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        conn.close()


# Функции работы с пользователями
def get_user_info(chat_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE chat_id = ?', (chat_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None
    finally:
        conn.close()


def save_user(chat_id, role, full_name=None, group_name=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (chat_id, role, full_name, group_name, registration_date)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            chat_id, role, full_name, group_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
        raise
    finally:
        conn.close()


# Клавиатуры
def create_role_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🎓 Абитуриент'),
        types.KeyboardButton('👨🎓 Студент'),
        types.KeyboardButton('👨🏫 Преподаватель')
    )
    return markup


def create_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('⬅️ Назад'))
    return markup


def create_main_menu(role):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    if role == 'abiturient':
        buttons = ['🏛 Факультеты', '📝 Правила', '📅 Мероприятия', '📞 Контакты']
    elif role == 'student':
        buttons = ['📅 Расписание', '📚 Материалы', '📝 Задания', '📊 Успеваемость', '👤 Профиль']
    elif role == 'teacher':
        buttons = ['📅 Расписание', '👥 Группы', '📝 Задания', '📊 Журнал', '⚙️ Настройки']

    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    return markup


# Обработчики команд
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)

        if user_info:
            show_main_menu(chat_id, user_info['role'])
        else:
            bot.send_message(
                chat_id,
                "👋 Добро пожаловать в университетский бот!\nВыберите свою роль:",
                reply_markup=create_role_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте позже.")


@bot.message_handler(func=lambda m: m.text in ['🎓 Абитуриент', '👨🎓 Студент', '👨🏫 Преподаватель'])
def role_selection_handler(message):
    try:
        chat_id = message.chat.id
        role_map = {
            '🎓 Абитуриент': 'abiturient',
            '👨🎓 Студент': 'student',
            '👨🏫 Преподаватель': 'teacher'
        }

        role = role_map[message.text]
        user_states[chat_id] = {'role': role}

        if role == 'abiturient':
            save_user(chat_id, role)
            show_main_menu(chat_id, role)
        else:
            msg = bot.send_message(
                chat_id,
                "🔑 Введите ваш ключ доступа:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
    except Exception as e:
        logger.error(f"Ошибка выбора роли: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте снова.")


def process_access_key(message):
    try:
        chat_id = message.chat.id
        if message.text == '⬅️ Назад':
            return start_handler(message)

        role = user_states[chat_id]['role']

        # Проверка ключа
        if (role == 'student' and message.text == STUDENT_KEY) or \
                (role == 'teacher' and message.text == TEACHER_KEY):

            msg = bot.send_message(
                chat_id,
                "✅ Ключ принят! Теперь введите ваше ФИО:",
                reply_markup=create_back_keyboard()
            )

            if role == 'student':
                bot.register_next_step_handler(msg, process_student_full_name)
            else:
                bot.register_next_step_handler(msg, process_teacher_full_name)
        else:
            msg = bot.send_message(
                chat_id,
                "❌ Неверный ключ доступа. Попробуйте еще раз:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
    except Exception as e:
        logger.error(f"Ошибка обработки ключа: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте снова.")


def process_student_full_name(message):
    try:
        chat_id = message.chat.id
        if message.text == '⬅️ Назад':
            msg = bot.send_message(
                chat_id,
                "🔑 Введите ваш ключ доступа:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
            return

        if len(message.text.split()) < 2:
            msg = bot.send_message(
                chat_id,
                "❌ Введите полное ФИО (например, Иванов Иван Иванович):",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_student_full_name)
            return

        user_states[chat_id]['full_name'] = message.text

        msg = bot.send_message(
            chat_id,
            "📌 Введите вашу группу (например, ИВТ-2023):",
            reply_markup=create_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_student_group)
    except Exception as e:
        logger.error(f"Ошибка ввода ФИО: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте снова.")


def process_student_group(message):
    try:
        chat_id = message.chat.id
        if message.text == '⬅️ Назад':
            msg = bot.send_message(
                chat_id,
                "Введите ваше ФИО полностью:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_student_full_name)
            return

        save_user(
            chat_id,
            'student',
            full_name=user_states[chat_id]['full_name'],
            group_name=message.text
        )

        bot.send_message(
            chat_id,
            f"🎉 Регистрация завершена, {user_states[chat_id]['full_name']}!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id, 'student')
    except Exception as e:
        logger.error(f"Ошибка ввода группы: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте снова.")


def process_teacher_full_name(message):
    try:
        chat_id = message.chat.id
        if message.text == '⬅️ Назад':
            msg = bot.send_message(
                chat_id,
                "🔑 Введите ваш ключ доступа:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
            return

        if len(message.text.split()) < 2:
            msg = bot.send_message(
                chat_id,
                "❌ Введите полное ФИО (например, Петрова Мария Ивановна):",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_teacher_full_name)
            return

        save_user(
            chat_id,
            'teacher',
            full_name=message.text
        )

        bot.send_message(
            chat_id,
            f"🎉 Регистрация завершена, {message.text}!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id, 'teacher')
    except Exception as e:
        logger.error(f"Ошибка ввода ФИО: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте снова.")


# Обработчики для функционала студентов и преподавателей
@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                    get_user_info(m.chat.id)['role'] == 'student' and
                                    m.text in ['📅 Расписание', '📚 Материалы', '📝 Задания', '📊 Успеваемость',
                                               '👤 Профиль'])
def student_features_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)

        if message.text == '📅 Расписание':
            bot.send_message(chat_id, "🔄 Загрузка расписания...")
            # Здесь можно добавить реальное расписание
            bot.send_message(chat_id,
                             "📅 Ваше расписание на неделю:\nПн: Математика 10:00-11:30\nВт: Физика 9:00-10:30\nСр: Программирование 11:00-12:30")

        elif message.text == '📚 Материалы':
            bot.send_message(chat_id, "🔄 Загрузка материалов...")
            bot.send_message(chat_id,
                             "📚 Доступные материалы:\n1. Лекция по математике\n2. Практикум по физике\n3. Лабораторная по программированию")

        elif message.text == '📝 Задания':
            bot.send_message(chat_id, "🔄 Загрузка заданий...")
            bot.send_message(chat_id,
                             "📝 Текущие задания:\n1. Реферат по истории (до 15.05)\n2. Задачи по физике (до 20.05)")

        elif message.text == '📊 Успеваемость':
            bot.send_message(chat_id, "🔄 Загрузка успеваемости...")
            bot.send_message(chat_id, "📊 Ваша успеваемость:\nМатематика: 4.5\nФизика: 5.0\nПрограммирование: 4.8")

        elif message.text == '👤 Профиль':
            response = f"👤 Ваш профиль:\nФИО: {user_info['full_name']}\nГруппа: {user_info['group_name']}\nРоль: Студент"
            bot.send_message(chat_id, response)

    except Exception as e:
        logger.error(f"Ошибка обработки запроса студента: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте позже.")


@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                    get_user_info(m.chat.id)['role'] == 'teacher' and
                                    m.text in ['📅 Расписание', '👥 Группы', '📝 Задания', '📊 Журнал', '⚙️ Настройки'])
def teacher_features_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)

        if message.text == '📅 Расписание':
            bot.send_message(chat_id, "🔄 Загрузка расписания...")
            bot.send_message(chat_id,
                             "📅 Ваше расписание занятий:\nПн: Лекция по математике (ИВТ-2023) 10:00-11:30\nВт: Практика по физике (ИВТ-2023) 9:00-10:30")

        elif message.text == '👥 Группы':
            bot.send_message(chat_id, "🔄 Загрузка списка групп...")
            bot.send_message(chat_id, "👥 Ваши учебные группы:\n1. ИВТ-2023\n2. ИВТ-2022")

        elif message.text == '📝 Задания':
            bot.send_message(chat_id, "🔄 Загрузка заданий...")
            bot.send_message(chat_id, "📝 Управление заданиями:\n1. Добавить новое задание\n2. Проверить выполненные")

        elif message.text == '📊 Журнал':
            bot.send_message(chat_id, "🔄 Загрузка журнала...")
            bot.send_message(chat_id,
                             "📊 Журнал успеваемости:\nГруппа ИВТ-2023:\n- Иванов И.И.: 4.5\n- Петров П.П.: 5.0")

        elif message.text == '⚙️ Настройки':
            bot.send_message(chat_id, "⚙️ Настройки профиля:\n1. Изменить контактные данные\n2. Настройки уведомлений")

    except Exception as e:
        logger.error(f"Ошибка обработки запроса преподавателя: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте позже.")


# Обработчик для абитуриентов
@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                    get_user_info(m.chat.id)['role'] == 'abiturient' and
                                    m.text in ['🏛 Факультеты', '📝 Правила', '📅 Мероприятия', '📞 Контакты'])
def abiturient_features_handler(message):
    try:
        chat_id = message.chat.id

        if message.text == '🏛 Факультеты':
            response = "🏛 Факультеты нашего университета:\n1. Информационных технологий\n2. Инженерный\n3. Экономический"
            bot.send_message(chat_id, response)

        elif message.text == '📝 Правила':
            response = "📝 Правила приема:\n1. Подача документов до 20 июля\n2. Вступительные испытания с 25 июля\n3. Список рекомендованных - 10 августа"
            bot.send_message(chat_id, response)

        elif message.text == '📅 Мероприятия':
            response = "📅 Ближайшие мероприятия:\n- День открытых дверей: 15 мая\n- Олимпиада для абитуриентов: 20 июня"
            bot.send_message(chat_id, response)

        elif message.text == '📞 Контакты':
            response = "📞 Контакты приемной комиссии:\nТелефон: +7 (123) 456-78-90\nEmail: admission@university.edu\nАдрес: ул. Университетская, 1"
            bot.send_message(chat_id, response)

    except Exception as e:
        logger.error(f"Ошибка обработки запроса абитуриента: {e}")
        bot.reply_to(message, "⚠️ Ошибка. Попробуйте позже.")


# Основные функции
def show_main_menu(chat_id, role):
    try:
        greetings = {
            'abiturient': "🎓 Добро пожаловать, абитуриент!",
            'student': f"👋 Здравствуйте, {get_user_info(chat_id)['full_name']}!",
            'teacher': f"👨🏫 Добрый день, {get_user_info(chat_id)['full_name']}!"
        }

        bot.send_message(
            chat_id,
            greetings.get(role, "Добро пожаловать!"),
            reply_markup=create_main_menu(role)
        )
    except Exception as e:
        logger.error(f"Ошибка показа меню: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка. Попробуйте позже.")


@bot.message_handler(func=lambda m: True)
def unknown_handler(message):
    bot.send_message(
        message.chat.id,
        "❌ Неизвестная команда. Используйте кнопки меню.",
        reply_markup=create_back_keyboard() if get_user_info(message.chat.id) else None
    )


# Запуск бота
if __name__ == '__main__':
    init_db()
    logger.info("Бот запущен")
    bot.infinity_polling()