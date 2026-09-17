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
VK_TOKEN = os.environ.get("VK_TOKEN", "vk1.a.nf6zK6aw_gwAxX7cc5mYvEbP3oqbyhOTXKWaCAieJ0RnV792f_6SIt8ZZ_eAjUHxPDx3BI-n81ZLrreqo3AOQHjB3Dc0ffBmHj-Eru-bBgr-lei-TLd8a9LUUgkiPWRnFlzBjmaoBAyD4YdZ6uHwELD_EAZJTwCcSB3JC76Z2J_5SQRP84XmrJGW1QoFs4vqrxPCy9EbFRLE-W4L0s1lUQ")
GROUP_ID = int(os.environ.get("GROUP_ID", "241527291"))
PEER_ID = 2000000109  # peer_id вашей беседы
TASK_INTERVAL = 900  # 15 минут

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
    "Найдите гостя, чья первая буква имени совпадает с вашей. Сделайте совместное фото «Тёзки» 🔤",
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
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# --- Отправка задания ---
def send_scheduled_task():
    global current_task_index
    if current_task_index < len(TASKS):
        task_text = TASKS[current_task_index]
        try:
            vk.messages.send(
                peer_id=PEER_ID,
                message=f"🎉 Задание №{current_task_index + 1}\n\n{task_text}\n\n📸 Присылайте результат в этот чат!",
                random_id=get_random_id()
            )
            logging.info(f"Задание №{current_task_index + 1} отправлено.")
            current_task_index += 1
        except Exception as e:
            logging.error(f"Ошибка отправки задания: {e}")
    else:
        logging.info("Все задания выполнены!")

# --- Слушатель LongPoll ---
def listen_messages():
    logging.info("VK-бот запущен и слушает сообщения...")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW and event.to_me:
            msg = event.object.message
            text = msg.get('text', '')
            attachments = msg.get('attachments', [])
            has_media = any(att['type'] in ['photo', 'video', 'audio_message'] for att in attachments)
            try:
                if has_media:
                    vk.messages.send(peer_id=event.peer_id, message="🔥 Огонь! Задание в копилке!", reply_to=msg['id'], random_id=get_random_id())
                elif text and not text.startswith('/'):
                    vk.messages.send(peer_id=event.peer_id, message="💬 Отличный ответ!", reply_to=msg['id'], random_id=get_random_id())
                elif text == '/start_quest':
                    vk.messages.send(peer_id=event.peer_id, message=INTRO, random_id=get_random_id())
                    schedule.every(TASK_INTERVAL).seconds.do(send_scheduled_task)
            except Exception as e:
                logging.error(f"Ошибка при ответе на сообщение: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    listener_thread = threading.Thread(target=listen_messages) if False else threading.Thread(target=listen_messages)
    listener_thread.daemon = True
    listener_thread.start()
    logging.info("VK-бот запущен. Ожидание команды /start_quest...")
    while True:
        schedule.run_pending()
        time.sleep(1)