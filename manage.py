import telebot
from telebot import types
import sqlite3
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='university_bot.log'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot('7303895887:AAGWZ83wBKfnAeIT3GrRH1A49E62kAcZTJU')

# Состояния пользователей
user_states = {}

# Подключение к базе данных
def get_db_connection():
    try:
        conn = sqlite3.connect('university.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

# Инициализация базы данных
def init_db():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                role TEXT NOT NULL,
                group_id INTEGER,
                email TEXT,
                phone TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                registration_date TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            )
            ''')

            # Таблица групп
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                faculty TEXT NOT NULL,
                course INTEGER NOT NULL,
                curator_id INTEGER,
                FOREIGN KEY (curator_id) REFERENCES users(id)
            )
            ''')

            # Таблица ключей доступа
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL,
                used_at TEXT
            )
            ''')

            # Таблица расписания
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                time TEXT NOT NULL,
                subject TEXT NOT NULL,
                teacher_id INTEGER NOT NULL,
                classroom TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            )
            ''')

            # Таблица заданий
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                group_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                deadline TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            )
            ''')

            # Таблица успеваемости
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                grade INTEGER,
                submitted_at TEXT,
                teacher_comment TEXT,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
            ''')

            # Создаем тестовые группы
            test_groups = [
                ('ИВТ-2023', 'Информационные технологии', 1),
                ('ПИ-2022', 'Информационные технологии', 2),
                ('ЭК-2023', 'Экономика', 1)
            ]
            
            for name, faculty, course in test_groups:
                cursor.execute("INSERT OR IGNORE INTO groups (name, faculty, course) VALUES (?, ?, ?)", 
                             (name, faculty, course))

            # Тестовые ключи доступа
            test_keys = [
                ('student123', 'student'),
                ('teacher456', 'teacher'),
                ('admin789', 'admin'),
                ('abiturient000', 'abiturient')
            ]
            
            for key, role in test_keys:
                cursor.execute("INSERT OR IGNORE INTO access_keys (key, role, created_at) VALUES (?, ?, ?)", 
                             (key, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # Тестовое расписание
            cursor.execute("SELECT id FROM groups WHERE name = 'ИВТ-2023'")
            group_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1")
            teacher_id = cursor.fetchone()['id'] if cursor.fetchone() else 1
            
            test_schedule = [
                (group_id, 'Понедельник', '09:00', 'Программирование', teacher_id, '304'),
                (group_id, 'Понедельник', '11:00', 'Математика', teacher_id, '412'),
                (group_id, 'Вторник', '10:00', 'Базы данных', teacher_id, '215')
            ]
            
            for item in test_schedule:
                cursor.execute('''
                INSERT OR IGNORE INTO schedule 
                (group_id, day_of_week, time, subject, teacher_id, classroom)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', item)

            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        raise

# Функции работы с базой данных
def get_user_info(chat_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT u.*, g.name as group_name 
            FROM users u
            LEFT JOIN groups g ON u.group_id = g.id
            WHERE u.chat_id = ?
            ''', (chat_id,))
            return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error getting user info: {e}")
        return None

def check_access_key(key, role):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id FROM access_keys 
            WHERE key = ? AND role = ? AND is_used = FALSE
            ''', (key, role))
            return bool(cursor.fetchone())
    except sqlite3.Error as e:
        logger.error(f"Error checking access key: {e}")
        return False

def mark_key_as_used(key):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE access_keys 
            SET is_used = TRUE, used_at = ?
            WHERE key = ?
            ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error marking key as used: {e}")
        raise

def save_user(chat_id, role, full_name=None, group_name=None, is_verified=True):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            group_id = None
            if group_name:
                cursor.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
                group = cursor.fetchone()
                if group:
                    group_id = group['id']
            
            cursor.execute('''
            INSERT OR REPLACE INTO users 
            (chat_id, role, full_name, group_id, is_verified, registration_date, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                chat_id, role, full_name, group_id, is_verified,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving user: {e}")
        raise

def get_group_schedule(group_name):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT s.day_of_week, s.time, s.subject, s.classroom, u.full_name as teacher_name
            FROM schedule s
            JOIN groups g ON s.group_id = g.id
            JOIN users u ON s.teacher_id = u.id
            WHERE g.name = ?
            ORDER BY 
                CASE s.day_of_week
                    WHEN 'Понедельник' THEN 1
                    WHEN 'Вторник' THEN 2
                    WHEN 'Среда' THEN 3
                    WHEN 'Четверг' THEN 4
                    WHEN 'Пятница' THEN 5
                    WHEN 'Суббота' THEN 6
                    ELSE 7
                END,
                s.time
            ''', (group_name,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting group schedule: {e}")
        return None

def get_student_assignments(chat_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT a.title, a.description, a.subject, a.deadline, 
                   ap.grade, ap.submitted_at, ap.teacher_comment,
                   u.full_name as teacher_name
            FROM assignments a
            JOIN users u ON a.teacher_id = u.id
            LEFT JOIN academic_performance ap ON a.id = ap.assignment_id AND ap.student_id = (
                SELECT id FROM users WHERE chat_id = ?
            )
            WHERE a.group_id = (
                SELECT group_id FROM users WHERE chat_id = ?
            )
            ORDER BY a.deadline
            ''', (chat_id, chat_id))
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting student assignments: {e}")
        return None

def get_teacher_groups(teacher_chat_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT g.name, g.faculty, g.course
            FROM groups g
            JOIN users u ON g.curator_id = u.id
            WHERE u.chat_id = ?
            ''', (teacher_chat_id,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting teacher groups: {e}")
        return None

def update_user_last_activity(chat_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE users 
            SET last_activity = ?
            WHERE chat_id = ?
            ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), chat_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error updating user last activity: {e}")

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
        buttons = [
            '🏛 Факультеты',
            '📝 Правила приема',
            '📅 Дни открытых дверей',
            '📞 Контакты'
        ]
    elif role == 'student':
        buttons = [
            '📅 Расписание',
            '📚 Учебные материалы',
            '📝 Мои задания',
            '📊 Успеваемость',
            '🏠 Мой профиль'
        ]
    elif role == 'teacher':
        buttons = [
            '📅 Расписание',
            '👥 Мои группы',
            '📝 Задания',
            '📊 Журнал успеваемости',
            '⚙️ Настройки'
        ]
    elif role == 'admin':
        buttons = [
            '👥 Пользователи',
            '🔑 Управление ключами',
            '📊 Статистика',
            '⚙️ Настройки системы'
        ]

    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    return markup

# Обработчики команд
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)

        if user_info and user_info['is_verified']:
            show_main_menu(chat_id, user_info['role'])
        else:
            bot.send_message(
                chat_id,
                "👋 Добро пожаловать в университетский бот!\nВыберите свою роль:",
                reply_markup=create_role_keyboard()
            )
            user_states[chat_id] = {'state': 'selecting_role'}
    except Exception as e:
        logger.error(f"Start handler error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

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
            show_abiturient_menu(chat_id)
        else:
            msg = bot.send_message(
                chat_id,
                "🔑 Для продолжения введите ключ доступа:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
    except Exception as e:
        logger.error(f"Role selection error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_access_key(message):
    try:
        chat_id = message.chat.id

        if message.text == '⬅️ Назад':
            return start_handler(message)

        role = user_states.get(chat_id, {}).get('role')
        if not role:
            return start_handler(message)

        if check_access_key(message.text, role):
            mark_key_as_used(message.text)

            if role == 'student':
                msg = bot.send_message(
                    chat_id,
                    "✅ Ключ принят! Введите ваше ФИО:",
                    reply_markup=create_back_keyboard()
                )
                bot.register_next_step_handler(msg, process_student_full_name)
            else:
                msg = bot.send_message(
                    chat_id,
                    "✅ Ключ принят! Введите ваше ФИО:",
                    reply_markup=create_back_keyboard()
                )
                bot.register_next_step_handler(msg, process_teacher_full_name)
        else:
            msg = bot.send_message(
                chat_id,
                "❌ Неверный ключ доступа. Пожалуйста, введите правильный ключ:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
    except Exception as e:
        logger.error(f"Access key processing error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_student_full_name(message):
    try:
        chat_id = message.chat.id

        if message.text == '⬅️ Назад':
            return start_handler(message)

        if len(message.text.split()) < 2:
            msg = bot.send_message(
                chat_id,
                "❌ Пожалуйста, введите полное ФИО (например, Иванов Иван Иванович):",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_student_full_name)
            return

        user_states[chat_id]['full_name'] = message.text

        msg = bot.send_message(
            chat_id,
            "📌 Введите название вашей группы (например, ИВТ-2023):",
            reply_markup=create_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_student_group)
    except Exception as e:
        logger.error(f"Student full name processing error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_student_group(message):
    try:
        chat_id = message.chat.id

        if message.text == '⬅️ Назад':
            return start_handler(message)

        save_user(
            chat_id,
            'student',
            full_name=user_states[chat_id]['full_name'],
            group_name=message.text,
            is_verified=True
        )

        bot.send_message(
            chat_id,
            f"🎉 Регистрация завершена, {user_states[chat_id]['full_name']}!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id, 'student')
    except Exception as e:
        logger.error(f"Student group processing error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_teacher_full_name(message):
    try:
        chat_id = message.chat.id

        if message.text == '⬅️ Назад':
            return start_handler(message)

        if len(message.text.split()) < 2:
            msg = bot.send_message(
                chat_id,
                "❌ Пожалуйста, введите полное ФИО (например, Петрова Мария Ивановна):",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_teacher_full_name)
            return

        save_user(
            chat_id,
            'teacher',
            full_name=message.text,
            is_verified=True
        )

        bot.send_message(
            chat_id,
            f"🎉 Регистрация завершена, {message.text}!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id, 'teacher')
    except Exception as e:
        logger.error(f"Teacher full name processing error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

@bot.message_handler(func=lambda m: m.text == '⬅️ Назад')
def back_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)

        if not user_info:
            return start_handler(message)

        show_main_menu(chat_id, user_info['role'])
    except Exception as e:
        logger.error(f"Back handler error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте снова.")

# Меню и информационные разделы
def show_main_menu(chat_id, role):
    try:
        user_info = get_user_info(chat_id)

        greetings = {
            'abiturient': "👋 Добро пожаловать, абитуриент!",
            'student': f"👋 Здравствуйте, {user_info['full_name']}!",
            'teacher': f"👋 Добрый день, {user_info['full_name']}!",
            'admin': "⚙️ Панель администратора"
        }

        bot.send_message(
            chat_id,
            greetings.get(role, "Добро пожаловать!"),
            reply_markup=create_main_menu(role)
        )
        user_states[chat_id] = {'state': 'main_menu'}
        update_user_last_activity(chat_id)
    except Exception as e:
        logger.error(f"Show main menu error: {e}")
        bot.send_message(chat_id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

def show_abiturient_menu(chat_id):
    try:
        bot.send_message(
            chat_id,
            "🎓 Выберите интересующий вас раздел:",
            reply_markup=create_main_menu('abiturient')
        )
        user_states[chat_id] = {'state': 'abiturient_menu'}
        update_user_last_activity(chat_id)
    except Exception as e:
        logger.error(f"Show abiturient menu error: {e}")
        bot.send_message(chat_id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Информационные разделы
ABITURIENT_INFO = {
    '🏛 Факультеты': """
<b>🏛 Факультеты нашего университета:</b>

1. <b>Информационных технологий</b>
   - Компьютерные науки
   - Программная инженерия
   - Искусственный интеллект

2. <b>Экономический</b>
   - Финансы и кредит
   - Бухгалтерский учет
   - Бизнес-аналитика

3. <b>Гуманитарный</b>
   - Психология
   - Лингвистика
   - Международные отношения
""",
    '📝 Правила приема': """
<b>📝 Правила приема 2024:</b>

📅 Сроки подачи документов:
- Начало: 20 июня
- Окончание: 25 июля

📄 Необходимые документы:
- Паспорт (копия)
- Аттестат (оригинал)
- 4 фото 3×4
- Медсправка 086/у

📊 Вступительные испытания:
- Математика
- Русский язык
- Профильный предмет
""",
    '📅 Дни открытых дверей': """
<b>📅 Ближайшие дни открытых дверей:</b>

🗓 15 апреля 2024, 12:00
🗓 20 мая 2024, 12:00
🗓 10 июня 2024, 12:00

📍 Адрес: г. Москва, ул. Университетская, 1, корпус 3, ауд. 101

📌 Для участия необходима предварительная регистрация на сайте university.ru
""",
    '📞 Контакты': """
<b>📞 Контакты приемной комиссии:</b>

☎ Телефон: +7 (495) 123-45-67
📧 Email: admission@university.ru
🌐 Сайт: university.ru

📍 Адрес: г. Москва, ул. Университетская, 1, каб. 205

🕒 Часы работы:
Пн-Пт: 9:00-18:00
Сб: 10:00-15:00
"""
}

STUDENT_INFO = {
    '📅 Расписание': """
<b>📅 Ваше расписание:</b>

Понедельник:
09:00 - Математика (ауд. 304)
11:00 - Программирование (ауд. 412)

Вторник:
10:00 - Физика (ауд. 215)
13:00 - Иностранный язык (ауд. 107)

Полное расписание доступно на сайте schedule.university.ru
""",
    '📚 Учебные материалы': """
<b>📚 Доступные учебные материалы:</b>

1. Математика:
   - Лекции 1-10
   - Практические задания
   - Дополнительная литература

2. Программирование:
   - Лабораторные работы
   - Примеры кода
   - Тестовые задания

Доступ через LMS: lms.university.ru
""",
    '📝 Мои задания': """
<b>📝 Текущие задания:</b>

1. Математика:
   - ДЗ №3 (срок до 15.04)
   - Контрольная работа (до 20.04)

2. Программирование:
   - Лабораторная №2 (срок до 10.04)
   - Курсовой проект (тема утверждена)

🔄 Статус заданий можно проверить в личном кабинете
""",
    '📊 Успеваемость': """
<b>📊 Ваша успеваемость:</b>

Математика:
- Посещаемость: 95%
- Средний балл: 4.7

Программирование:
- Посещаемость: 100%
- Средний балл: 5.0

Полная ведомость доступна в деканате
""",
    '🏠 Мой профиль': """
<b>👤 Ваш профиль:</b>

ФИО: {full_name}
Группа: {group_name}
Роль: Студент
Дата регистрации: {reg_date}

📧 Учебная почта: {email}
📱 Телефон: +7 (XXX) XXX-XX-XX
"""
}

TEACHER_INFO = {
    '📅 Расписание': """
<b>📅 Ваше расписание занятий:</b>

Группа ИВТ-2023:
Пн 09:00 - Программирование (ауд. 412)
Ср 11:00 - Алгоритмы (ауд. 315)

Группа ПИ-2022:
Вт 14:00 - Базы данных (ауд. 204)
Пт 10:00 - Веб-разработка (ауд. 308)
""",
    '👥 Мои группы': """
<b>👥 Ваши группы:</b>

1. ИВТ-2023 (25 студентов)
   - Куратор
   - Основные дисциплины

2. ПИ-2022 (20 студентов)
   - Основные дисциплины

3. КБ-2021 (18 студентов)
   - Консультации
""",
    '📝 Задания': """
<b>📝 Управление заданиями:</b>

1. Создать новое задание
2. Проверить отправленные работы
3. Редактировать существующие задания
4. Установить сроки выполнения

Для управления используйте веб-интерфейс: lms.university.ru/teacher
""",
    '📊 Журнал успеваемости': """
<b>📊 Журнал успеваемости:</b>

Группа ИВТ-2023:
- Средний балл: 4.3
- Посещаемость: 89%

Группа ПИ-2022:
- Средний балл: 4.7
- Посещаемость: 93%

Подробная статистика доступна в электронном журнале
""",
    '⚙️ Настройки': """
<b>⚙️ Настройки профиля:</b>

1. Изменить контактные данные
2. Настройки уведомлений
3. Сменить пароль
4. Подключить двухфакторную аутентификацию
"""
}

# Обработчики информационных разделов
@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                  get_user_info(m.chat.id)['role'] == 'abiturient' and
                                  m.text in ABITURIENT_INFO.keys())
def abiturient_info_handler(message):
    try:
        bot.send_message(
            message.chat.id,
            ABITURIENT_INFO[message.text],
            parse_mode='HTML',
            reply_markup=create_main_menu('abiturient')
        )
        update_user_last_activity(message.chat.id)
    except Exception as e:
        logger.error(f"Abiturient info handler error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                  get_user_info(m.chat.id)['role'] == 'student' and
                                  m.text in STUDENT_INFO.keys())
def student_info_handler(message):
    try:
        user_info = get_user_info(message.chat.id)
        response = STUDENT_INFO[message.text]

        if message.text == '🏠 Мой профиль':
            response = response.format(
                full_name=user_info['full_name'],
                group_name=user_info['group_name'],
                reg_date=user_info['registration_date'],
                email=f"{user_info['group_name'].lower().replace('-', '')}@edu.university.ru"
            )

        bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            reply_markup=create_main_menu('student')
        )
        update_user_last_activity(message.chat.id)
    except Exception as e:
        logger.error(f"Student info handler error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and
                                  get_user_info(m.chat.id)['role'] == 'teacher' and
                                  m.text in TEACHER_INFO.keys())
def teacher_info_handler(message):
    try:
        bot.send_message(
            message.chat.id,
            TEACHER_INFO[message.text],
            parse_mode='HTML',
            reply_markup=create_main_menu('teacher')
        )
        update_user_last_activity(message.chat.id)
    except Exception as e:
        logger.error(f"Teacher info handler error: {e}")
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(func=lambda m: True)
def unknown_handler(message):
    bot.send_message(
        message.chat.id,
        "❌ Извините, я не понимаю эту команду. Пожалуйста, используйте кнопки меню.",
        reply_markup=create_back_keyboard()
    )

# Запуск бота
if __name__ == '__main__':
    try:
        init_db()
        logger.info("Database initialized successfully")
        logger.info("Starting bot...")
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")