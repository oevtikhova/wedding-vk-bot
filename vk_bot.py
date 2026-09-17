import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import schedule
import time

# --- НАСТРОЙКИ ---
VK_TOKEN = os.environ.get("VK_TOKEN", "")
GROUP_ID = int(os.environ.get("GROUP_ID", "241527291"))
PEER_ID = 2000000002  # peer_id БЕСЕДЫ для гостей
TASK_INTERVAL = 900  # 15 минут

# --- Ваш личный ID ВК (для подтверждений в личку) ---
ADMIN_ID = int(os.environ.get("ADMIN_ID", "384701652"))

# --- ПРИВЕТСТВЕННОЕ СООБЩЕНИЕ ---
INTRO = (
    "💍 Дорогие гости! 💍\n\n"
    "Сегодня у нас необычный день — мы запускаем свадебный квест! 🎉\n\n"
    "Как это работает:\n"
    "• Каждые 15 минут сюда прилетает новое задание.\n"
    "• Выполняйте его и присылайте результат в этот чат — фото, видео, текст или голосовое.\n"
    "• Фантазируйте! Лучшие моменты попадут в общий свадебный альбом.\n\n"
    "🏆 И это не просто игра — это соревнование! 🏆\n\n"
    "Каждый сам за себя!\n"
    "Главный приз на банкете получит только один абсолютный победитель 👑 — тот, кто выполнит все задания быстрее всех.\n\n"
    "Участвуют ВСЕ одновременно.\n"
    "Если задание требует сфотографировать кого-то или что-то — каждый присылает своё личное фото. Старайтесь не повторяться: если один гость уже сфотографировался с кем-то, пусть второй участник найдёт для селфи кого-то другого. Так у нас получится больше живых, разных и неожиданных кадров! 😉\n\n"
    "Скорость решает всё! ⏱️🔥\n"
    "Ловите моменты, пишите ответы и отправляйте их без промедления. Если на финише несколько человек выполнят все задания — победу заберёт тот, чьи сообщения прилетели хотя бы на секунду раньше остальных!\n\n"
    "Маленькое исключение — командные задания.\n"
    "Если задание групповое (например, «сфотографируйтесь всей командой»), его может прислать один человек за всех — повторять всей группой не нужно. 📸\n\n"
    "Готовы? Первое задание уже летит! 🚀\n\n"
    "С любовью, Ксения и Дмитрий 💕"
)

# --- СПИСОК ЗАДАНИЙ ---
TASKS = [
    "Сделайте селфи с гостем, которого видите впервые 😄",
    "Найдите в автобусе человека в самых ярких носках и сфотографируйте его 🧦",
    "Напишите четверостишие, используя слова: любовь, автобус, кольца, тёща ✍️",
    "Соберите комплимент от 3 гостей и отправьте его голосовым сообщением 🎤",
    "Сфотографируйтесь всей командой в одной забавной позе 📸",
    "Возьмите мудрый совет для молодых у самого старшего гостя 👴",
    "Изобразите молодожёнов на фото так, чтобы было смешно 😂",
    "Отправьте видеокружок с пожеланием для молодой пары 🎉",
    "Помашите из окна случайному прохожему так, чтобы он помахал вам в ответ. Снимите этот триумф на видео! 👋",
    "Включите фантазию! Сделайте фото любого предмета в автобусе (бутылка, поручень, ремень безопасности) так, будто это свадебное кольцо 💍",
    "Сделайте фото в стиле «Серьёзная мафия». Никаких улыбок, суровые лица, бокалы в руках 😎",
    "Изучаем палитру сегодняшнего дня прямо на улицах города! 🏙️ Найдите за окном автобуса что-то голубое, коричневое, оливковое, сливочное или синее. Сделайте фото через стекло и подпишите, насколько этот объект вписывается в наш дресс-код от 1 до 10. Самый стильный кадр получит приз на банкете! 🪟👔",
]

current_task_index = 0

# --- Логирование ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Мини-сервер для Render ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# --- Инициализация VK ---
vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.199')
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# --- Отправка в БЕСЕДУ (для гостей) ---
def send_to_group(text, reply_to=None):
    try:
        vk.messages.send(
            peer_id=PEER_ID,
            message=text,
            reply_to=reply_to,
            random_id=get_random_id()
        )
        logging.info(f"✅ Сообщение отправлено в беседу {PEER_ID}")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки в беседу {PEER_ID}: {repr(e)}")

# --- Отправка в ЛИЧКУ (для админа) ---
def send_to_admin(text):
    if ADMIN_ID == 0:
        return
    try:
        vk.messages.send(
            user_id=ADMIN_ID,
            message=text,
            random_id=get_random_id()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

# --- Отправка одного задания ---
def send_scheduled_task():
    global current_task_index
    if current_task_index < len(TASKS):
        task_text = TASKS[current_task_index]
        send_to_group(f"🎉 Задание №{current_task_index + 1}\n\n{task_text}\n\n📸 Присылайте результат в этот чат!")
        logging.info(f"Задание №{current_task_index + 1} отправлено.")
        current_task_index += 1
    else:
        send_to_group("🎊 Все задания выполнены! Спасибо за игру!")
        logging.info("Все задания выполнены! Останавливаем рассылку.")
        schedule.clear('quest')  # ← ОСТАНАВЛИВАЕМ РАССЫЛКУ

# --- Команды (только для личных сообщений) ---
def cmd_start_quest():
    global current_task_index
    current_task_index = 0
    schedule.clear('quest')
    send_to_group(INTRO)
    threading.Timer(8, send_scheduled_task).start()
    schedule.every(TASK_INTERVAL).seconds.do(send_scheduled_task).tag('quest')
    send_to_admin("✅ Квест запущен! Приветствие ушло в беседу. Первое задание — через 8 секунд.")

def cmd_next():
    send_scheduled_task()
    send_to_admin("➡️ Следующее задание отправлено в беседу.")

def cmd_reset():
    global current_task_index
    current_task_index = 0
    send_to_admin("🔄 Счётчик сброшен. Следующее задание будет №1.")

def cmd_stop():
    schedule.clear('quest')
    send_to_admin("⏹ Квест остановлен.")

# --- Слушатель LongPoll ---
def listen_messages():
    logging.info("VK-бот запущен. Команды — в личку сообщества, задания — в беседу.")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.object.message
            peer_id = msg['peer_id']
            user_id = msg['from_id']
            text = msg.get('text', '').strip()
            attachments = msg.get('attachments', [])
            has_media = any(att['type'] in ['photo', 'video', 'audio_message'] for att in attachments)

            logging.info(f"Получено сообщение от {user_id} в чат {peer_id}: {text[:50]}")

            try:
                # ЛИЧКА (peer_id == user_id) — команды
                if peer_id == user_id:
                    if text == '/start_quest':
                        cmd_start_quest()
                    elif text == '/next':
                        cmd_next()
                    elif text == '/reset':
                        cmd_reset()
                    elif text == '/stop':
                        cmd_stop()
                    elif text == '/test_group':
                        send_to_group("🧪 Тестовое сообщение. Если вы его видите — всё работает!")
                    elif text == '/start' or text == 'начать':
                        send_to_admin("Привет! Команды:\n/start_quest — запустить квест\n/next — следующее задание сейчас\n/reset — сбросить счётчик\n/stop — остановить\n/test_group — проверить отправку в беседу")
                # БЕСЕДА — реакции на гостей
                elif peer_id == PEER_ID:
                    if has_media:
                        send_to_group("🔥 Огонь! Задание в копилке!", msg['id'])
                    elif text and not text.startswith('/'):
                        send_to_group("💬 Отличный ответ!", msg['id'])
            except Exception as e:
                logging.error(f"Ошибка при обработке: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    listener_thread = threading.Thread(target=listen_messages)
    listener_thread.daemon = True
    listener_thread.start()
    while True:
        schedule.run_pending()
        time.sleep(1)
