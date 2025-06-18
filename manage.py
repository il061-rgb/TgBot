import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime
import hashlib

# Конфигурация
BOT_TOKEN = '7977985505:AAFBX8fS6X8nE2Vg7bJ1elajMWotQSmr1vU'
DATABASE_NAME = 'university_bot.db'

bot = telebot.TeleBot(BOT_TOKEN)


# Инициализация БД
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        role TEXT CHECK(role IN ('student', 'teacher', 'abituirent')),
        group_name TEXT,
        register_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Таблица расписания
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        day TEXT,
        time TEXT,
        subject TEXT,
        teacher TEXT,
        classroom TEXT
    )
    ''')

    # Таблица заданий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        subject TEXT,
        task_text TEXT,
        deadline TEXT,
        teacher TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


# Проверка регистрации пользователя
def is_user_registered(telegram_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None


# Регистрация пользователя
def register_user(telegram_id, full_name, role, group_name=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO users (telegram_id, full_name, role, group_name)
    VALUES (?, ?, ?, ?)
    ''', (telegram_id, full_name, role, group_name))
    conn.commit()
    conn.close()


# Получение расписания
def get_schedule(group_name, day=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    if day:
        cursor.execute('''
        SELECT * FROM schedule 
        WHERE group_name = ? AND day = ?
        ORDER BY time
        ''', (group_name, day))
    else:
        cursor.execute('''
        SELECT * FROM schedule 
        WHERE group_name = ?
        ORDER BY day, time
        ''', (group_name,))

    schedule = cursor.fetchall()
    conn.close()
    return schedule


# Получение заданий
def get_assignments(group_name, subject=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    if subject:
        cursor.execute('''
        SELECT * FROM assignments 
        WHERE group_name = ? AND subject = ?
        ORDER BY deadline
        ''', (group_name, subject))
    else:
        cursor.execute('''
        SELECT * FROM assignments 
        WHERE group_name = ?
        ORDER BY deadline
        ''', (group_name,))

    assignments = cursor.fetchall()
    conn.close()
    return assignments


# Основные команды
@bot.message_handler(commands=['start'])
def start(message):
    if is_user_registered(message.chat.id):
        show_main_menu(message.chat.id)
    else:
        bot.send_message(
            message.chat.id,
            "👋 Добро пожаловать в университетский бот!\n\n"
            "Для начала работы вам нужно зарегистрироваться.\n"
            "Выберите вашу роль:",
            reply_markup=create_role_keyboard()
        )


def create_role_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👨‍🎓 Я студент'),
        types.KeyboardButton('👨‍🏫 Я преподаватель'),
        types.KeyboardButton('👨‍💼 Я абитуирент')
    )
    return markup


@bot.message_handler(
    func=lambda message: message.text in ['👨‍🎓 Я студент', '👨‍🏫 Я преподаватель', '👨‍💼 Я абитуриент'])
def process_role(message):
    role_map = {
        '👨‍🎓 Я студент': 'student',
        '👨‍🏫 Я преподаватель': 'teacher',
        '👨‍💼 Я абитуирент': 'abituirent'
    }

    role = role_map[message.text]

    if role == 'student':
        msg = bot.send_message(
            message.chat.id,
            "Введите ваше ФИО:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, lambda m: process_student_name(m, role))
    else:
        msg = bot.send_message(
            message.chat.id,
            "Введите ваш секретный ключ доступа:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, lambda m: process_teacher_auth(m, role))


def process_student_name(message, role):
    full_name = message.text
    msg = bot.send_message(
        message.chat.id,
        "Введите название вашей группы:"
    )
    bot.register_next_step_handler(msg, lambda m: process_student_group(m, role, full_name))


def process_student_group(message, role, full_name):
    group_name = message.text
    register_user(message.chat.id, full_name, role, group_name)
    bot.send_message(
        message.chat.id,
        f"✅ Регистрация завершена!\n\n"
        f"ФИО: {full_name}\n"
        f"Роль: {role}\n"
        f"Группа: {group_name}",
        reply_markup=types.ReplyKeyboardRemove()
    )
    show_main_menu(message.chat.id)


def process_teacher_auth(message, role):
    # В реальном приложении нужно использовать хэширование и хранить ключи в БД
    valid_keys = {
        'teacher': 'teacher123',
        # 'abituirent': 'abituirent123'
    }

    if message.text.strip() == valid_keys[role]:
        msg = bot.send_message(
            message.chat.id,
            "Введите ваше ФИО:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, lambda m: process_teacher_name(m, role))
    else:
        bot.send_message(
            message.chat.id,
            "❌ Неверный ключ доступа. Попробуйте снова.",
            reply_markup=create_role_keyboard()
        )


def process_teacher_name(message, role):
    full_name = message.text
    register_user(message.chat.id, full_name, role)
    bot.send_message(
        message.chat.id,
        f"✅ Регистрация завершена!\n\n"
        f"ФИО: {full_name}\n"
        f"Роль: {role}",
        reply_markup=types.ReplyKeyboardRemove()
    )
    show_main_menu(message.chat.id)


# Главное меню
def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE telegram_id = ?', (chat_id,))
    role = cursor.fetchone()[0]
    conn.close()

    if role == 'student':
        markup.add(
            types.KeyboardButton('📅 Расписание'),
            types.KeyboardButton('📝 Задания'),
            types.KeyboardButton('📊 Успеваемость'),
            types.KeyboardButton('ℹ️ Помощь')
        )
    elif role == 'teacher':
        markup.add(
            types.KeyboardButton('📅 Расписание'),
            types.KeyboardButton('📝 Задания'),
            types.KeyboardButton('👥 Группы'),
            types.KeyboardButton('ℹ️ Помощь')
        )
    else:  # admin
        markup.add(
            types.KeyboardButton('📅 Управление расписанием'),
            types.KeyboardButton('📝 Управление заданиями'),
            types.KeyboardButton('👥 Управление пользователями'),
            types.KeyboardButton('⚙️ Настройки системы')
        )

    bot.send_message(
        chat_id,
        "Главное меню:",
        reply_markup=markup
    )


# Обработка расписания
@bot.message_handler(func=lambda message: message.text == '📅 Расписание')
def handle_schedule(message):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT role, group_name FROM users WHERE telegram_id = ?', (message.chat.id,))
    user_data = cursor.fetchone()
    conn.close()

    role, group_name = user_data

    if role == 'student':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('Сегодня'),
            types.KeyboardButton('Завтра'),
            types.KeyboardButton('Неделя'),
            types.KeyboardButton('Назад')
        )
        bot.send_message(
            message.chat.id,
            f"Расписание для группы {group_name}:",
            reply_markup=markup
        )
    else:  # teacher
        # Для преподавателя можно добавить выбор группы
        show_teacher_schedule_options(message.chat.id)


def show_teacher_schedule_options(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('Мое расписание'),
        types.KeyboardButton('Расписание группы'),
        types.KeyboardButton('Назад')
    )
    bot.send_message(
        chat_id,
        "Выберите вариант просмотра расписания:",
        reply_markup=markup
    )


# Обработка заданий
@bot.message_handler(func=lambda message: message.text == '📝 Задания')
def handle_assignments(message):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT role, group_name FROM users WHERE telegram_id = ?', (message.chat.id,))
    user_data = cursor.fetchone()
    conn.close()

    role, group_name = user_data

    if role == 'student':
        assignments = get_assignments(group_name)
        if assignments:
            response = "📚 Ваши задания:\n\n"
            for task in assignments:
                response += (f"📌 {task[2]} ({task[1]})\n"
                             f"📝 {task[3]}\n"
                             f"⏰ До {task[4]}\n"
                             f"👨‍🏫 Преподаватель: {task[5]}\n\n")
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "У вас пока нет заданий.")
    else:  # teacher
        show_teacher_assignment_options(message.chat.id)


def show_teacher_assignment_options(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('Мои задания'),
        types.KeyboardButton('Добавить задание'),
        types.KeyboardButton('Назад')
    )
    bot.send_message(
        chat_id,
        "Выберите действие с заданиями:",
        reply_markup=markup
    )


# Запуск бота
if __name__ == '__main__':
    if not os.path.exists(DATABASE_NAME):
        init_db()
        print("База данных инициализирована")

    print("Бот запущен...")
    bot.polling(none_stop=True)