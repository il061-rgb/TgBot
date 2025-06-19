import telebot
from telebot import types
import sqlite3
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot('7977985505:AAFBX8fS6X8nE2Vg7bJ1elajMWotQSmr1vU')

# Состояния пользователей
user_states = {}

# Подключение к базе данных
def get_db_connection():
    conn = None
    try:
        conn = sqlite3.connect('university.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        if conn:
            conn.close()
        raise

# Инициализация базы данных
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT NOT NULL,
            group_name TEXT,
            is_verified BOOLEAN DEFAULT FALSE,
            registration_date TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_keys (
            key TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            is_used BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Добавляем тестовые данные
        cursor.execute("SELECT 1 FROM access_keys WHERE key = 'student123'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO access_keys (key, role) VALUES (?, ?)", 
                         ('student123', 'student'))
        
        cursor.execute("SELECT 1 FROM access_keys WHERE key = 'teacher456'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO access_keys (key, role) VALUES (?, ?)", 
                         ('teacher456', 'teacher'))
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

# Получение информации о пользователе
def get_user_info(chat_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT role, group_name, full_name, is_verified 
        FROM users 
        WHERE chat_id = ?
        ''', (chat_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения данных пользователя: {e}")
        return None
    finally:
        if conn:
            conn.close()

# Проверка и использование ключа доступа
def check_and_use_key(key, role):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT 1 FROM access_keys 
        WHERE key = ? AND role = ? AND is_used = FALSE
        ''', (key, role))
        
        if cursor.fetchone():
            cursor.execute('''
            UPDATE access_keys 
            SET is_used = TRUE 
            WHERE key = ?
            ''', (key,))
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Ошибка проверки ключа: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Сохранение пользователя
def save_user(chat_id, role, full_name=None, group_name=None, is_verified=True):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (chat_id, role, full_name, group_name, is_verified, registration_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            chat_id, 
            role, 
            full_name, 
            group_name, 
            is_verified,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
        raise
    finally:
        if conn:
            conn.close()

# Клавиатуры
def create_role_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👨🎓 Абитуриент'),
        types.KeyboardButton('👨🎓 Студент'),
        types.KeyboardButton('👨🏫 Преподаватель')
    )
    return markup

def create_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('⬅️ Назад'))
    return markup

def create_main_menu(role, full_name=""):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if role == 'abituirent':
        buttons = [
            '📚 Информация о факультетах',
            '📝 Правила приема',
            '📅 Дни открытых дверей',
            '📞 Контакты приемной комиссии'
        ]
    elif role == 'student':
        buttons = [
            '📅 Расписание',
            '📝 Задания',
            '📊 Успеваемость',
            'ℹ️ Помощь'
        ]
    elif role == 'teacher':
        buttons = [
            '📅 Расписание',
            '📝 Задания',
            '👥 Группы',
            '📊 Успеваемость',
            'ℹ️ Помощь'
        ]
    
    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    markup.add(types.KeyboardButton('⬅️ Назад'))
    return markup

# Обработчики сообщений
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        chat_id = message.chat.id
        bot.send_message(
            chat_id,
            "Здравствуйте, выберите свой профиль!",
            reply_markup=create_role_keyboard()
        )
        user_states[chat_id] = {'state': 'selecting_role'}
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(func=lambda m: m.text in ['👨🎓 Абитуриент', '👨🎓 Студент', '👨🏫 Преподаватель'])
def role_selection_handler(message):
    try:
        chat_id = message.chat.id
        role_map = {
            '👨🎓 Абитуриент': 'abituirent',
            '👨🎓 Студент': 'student',
            '👨🏫 Преподаватель': 'teacher'
        }
        
        role = role_map[message.text]
        user_states[chat_id] = {'role': role}
        
        if role == 'abituirent':
            save_user(chat_id, role)
            show_abituirent_menu(chat_id)
        else:
            msg = bot.send_message(
                chat_id,
                "Для дальнейшего использования введите ключ доступа:",
                reply_markup=create_back_keyboard()
            )
            bot.register_next_step_handler(msg, process_access_key)
    except Exception as e:
        logger.error(f"Ошибка выбора роли: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_access_key(message):
    try:
        chat_id = message.chat.id
        
        if message.text == '⬅️ Назад':
            return start_handler(message)
        
        role = user_states.get(chat_id, {}).get('role')
        if not role:
            return start_handler(message)
        
        if check_and_use_key(message.text, role):
            save_user(chat_id, role, is_verified=True)
            
            if role == 'student':
                msg = bot.send_message(
                    chat_id,
                    "Ключ принят! Теперь введите ваше ФИО:",
                    reply_markup=create_back_keyboard()
                )
                bot.register_next_step_handler(msg, process_student_full_name)
            else:
                msg = bot.send_message(
                    chat_id,
                    "Ключ принят! Теперь введите ваше ФИО:",
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
        logger.error(f"Ошибка обработки ключа: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_student_full_name(message):
    try:
        chat_id = message.chat.id
        
        if message.text == '⬅️ Назад':
            return start_handler(message)
        
        user_states[chat_id]['full_name'] = message.text
        
        msg = bot.send_message(
            chat_id,
            "Теперь введите название вашей группы:",
            reply_markup=create_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_student_group)
    except Exception as e:
        logger.error(f"Ошибка ввода ФИО студента: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

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
            "✅ Регистрация завершена!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id)
    except Exception as e:
        logger.error(f"Ошибка ввода группы студента: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def process_teacher_full_name(message):
    try:
        chat_id = message.chat.id
        
        if message.text == '⬅️ Назад':
            return start_handler(message)
        
        save_user(
            chat_id,
            'teacher',
            full_name=message.text,
            is_verified=True
        )
        
        bot.send_message(
            chat_id,
            "✅ Регистрация завершена!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        show_main_menu(chat_id)
    except Exception as e:
        logger.error(f"Ошибка ввода ФИО преподавателя: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

@bot.message_handler(func=lambda m: m.text == '⬅️ Назад')
def back_handler(message):
    try:
        chat_id = message.chat.id
        user_info = get_user_info(chat_id)
        
        if not user_info:
            return start_handler(message)
        
        show_main_menu(chat_id)
    except Exception as e:
        logger.error(f"Ошибка обработки кнопки Назад: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

# Меню и информационные разделы
def show_main_menu(chat_id):
    try:
        user_info = get_user_info(chat_id)
        if not user_info:
            return start_handler(chat_id)
        
        role = user_info['role']
        full_name = user_info['full_name'] or ""
        
        if role == 'abituirent':
            text = "Мы рады новым учащимся. Выберите какую информацию хотите получить:"
        elif role == 'student':
            text = f"Главное меню студента {full_name}"
        else:
            text = f"Главное меню преподавателя {full_name}"
        
        bot.send_message(
            chat_id,
            text,
            reply_markup=create_main_menu(role, full_name)
        )
        user_states[chat_id] = {'state': 'main_menu'}
    except Exception as e:
        logger.error(f"Ошибка показа главного меню: {e}")
        bot.send_message(chat_id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

def show_abituirent_menu(chat_id):
    try:
        bot.send_message(
            chat_id,
            "Мы рады новым учащимся. Выберите какую информацию хотите получить:",
            reply_markup=create_main_menu('abituirent')
        )
        user_states[chat_id] = {'state': 'abituirent_menu'}
    except Exception as e:
        logger.error(f"Ошибка показа меню абитуриента: {e}")
        bot.send_message(chat_id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

ABITURIENT_INFO = {
    '📚 Информация о факультетах': """
📚 <b>Информация о факультетах</b>:

1. <b>Факультет информационных технологий</b>
   - Компьютерные науки
   - Программная инженерия
   - Кибербезопасность

2. <b>Экономический факультет</b>
   - Финансы и кредит
   - Бухгалтерский учет
   - Менеджмент

3. <b>Гуманитарный факультет</b>
   - Психология
   - Филология
   - История
    """,
    '📝 Правила приема': """
📝 <b>Правила приема</b>:

1. Подача документов: с 1 июня по 15 июля
2. Вступительные испытания: с 20 июля по 5 августа
3. Необходимые документы:
   - Паспорт
   - Аттестат
   - 4 фотографии 3x4
   - Медицинская справка
    """,
    '📅 Дни открытых дверей': """
📅 <b>Дни открытых дверей</b>:

- 15 апреля 2024, 12:00
- 20 мая 2024, 12:00
- 10 июня 2024, 12:00

Адрес: г. Москва, ул. Университетская, д.1, ауд. 101
    """,
    '📞 Контакты приемной комиссии': """
📞 <b>Контакты приемной комиссии</b>:

Телефон: +7 (495) 123-45-67
Email: admission@university.ru
Адрес: г. Москва, ул. Университетская, д.1, каб. 205

Часы работы: Пн-Пт с 9:00 до 18:00
    """
}

@bot.message_handler(func=lambda m: get_user_info(m.chat.id) and 
                   get_user_info(m.chat.id)['role'] == 'abituirent' and
                   m.text in ABITURIENT_INFO.keys())
def abituirent_info_handler(message):
    try:
        bot.send_message(
            message.chat.id,
            ABITURIENT_INFO[message.text],
            parse_mode='HTML',
            reply_markup=create_back_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка показа информации для абитуриентов: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(func=lambda m: True)
def unknown_handler(message):
    bot.send_message(
        message.chat.id,
        "Извините, я не понимаю эту команду. Пожалуйста, используйте кнопки меню.",
        reply_markup=create_back_keyboard()
    )

# Инициализация и запуск
if __name__ == '__main__':
    try:
        init_db()
        logger.info("База данных инициализирована")
        logger.info("Запуск бота...")
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")