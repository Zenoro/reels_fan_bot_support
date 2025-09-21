import threading
import re
import os
from dotenv import load_dotenv, dotenv_values
from telebot import TeleBot, apihelper
import yt_dlp
from params import *
from utils import *
import sqlite3
import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    filename="bot.log",
    encoding="utf-8",
    filemode="a",
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)

# Загрузка переменных окружения из .env файла
load_dotenv()
values = dotenv_values()
bot = TeleBot(values['BOT_TOKEN'])

target_inst_dir = 'reels'
os.makedirs(target_inst_dir, exist_ok=True)

class VideoHandler:
    def __init__(self, bot, message, type):
        self.bot = bot
        self.message = message
        self.chat_id = message.chat.id
        self.thread_id = message.message_thread_id
        self.username = message.forward_from.username if message.forward_from else message.from_user.username
        self.type = type

    def preprocess(self, wait_text):
        self.bot.delete_message(self.chat_id, self.message.message_id)
        self.feedback_msg = self.bot.send_message(chat_id=self.chat_id,
                                                  message_thread_id=self.thread_id,
                                                  text=wait_text)

    def extract_caption(self, matched):
        user_caption = f'{self.type} от @{self.username}'
        text_caption = matched.group(3)
        self.url = matched.group(1)
        self.caption = text_caption + '\n' + user_caption if text_caption else user_caption

    def handle_error(self, db_cursor, error_text):
        self.bot.edit_message_text(chat_id=self.chat_id,
                                   message_id=self.feedback_msg.message_id,
                                   text=error_text)
        logger.info(f'error in {self.url}')
        db_cursor.execute("""
            UPDATE stats
            SET err_cnt = err_cnt + 1
            WHERE chat_id = ?;
        """, (self.chat_id, ))

    def download_and_send_video(self):
        match self.type:
            case 'рилс':
                field = 'reels_cnt'
            case 'шортс':
                field = 'shorts_cnt'
            case 'вк клип':
                field = 'vk_cnt'
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        try:
            video_path, info = dwld_YTDLP_video(self.url, YDL_OPTS)
            try:
                if IS_THUMBS:
                    cover_path = dwld_YTThumb(info, os.path.join(os.getcwd(), 'thumbnail.jpg'))
            except:
                logger.error("ERROR OCCURED WHILE TAKING THUMBNAIL")
            self.bot.send_video(chat_id=self.chat_id,
                                message_thread_id=self.thread_id,
                                video=open(video_path, 'rb'),
                                caption=self.caption,
                                thumb=open(cover_path, 'rb'))
            self.bot.delete_message(chat_id=self.chat_id,
                                    message_id=self.feedback_msg.message_id)
            os.remove(video_path) if os.path.exists(video_path) else None
            os.remove(cover_path) if os.path.exists(cover_path) else None
            logger.info(f"Video \"{video_path}\" has sent successfully.")
            cursor.execute("""
                UPDATE stats
                SET {} = {} + 1
                WHERE chat_id = ?;
            """.format(field, field), (self.chat_id, ))
        except yt_dlp.utils.DownloadError as e:
            self.handle_error(f'{self.type}а не будет :(\nошибка: {e}')
        except:
            self.handle_error(cursor, 'ошибка при загрузке. бот занят или пусть админ смотрит логи')
        conn.commit()
        conn.close()

    def process(self, matched):
        self.preprocess(f'ща будет {self.type}')
        self.extract_caption(matched)
        self.download_and_send_video()

@bot.message_handler(func=lambda message: message.text.startswith('https://'))
def handle_urls(message: dict) -> None:
    if (matched := re.match(fr'(({'|'.join(YT_URLS)})\S*)\s*(.*)', message.text)):
        type = IS_SHORTS and 'шортс'
    elif (matched := re.match(fr'(({'|'.join(IG_URLS)})\S*)\s*(.*)', message.text)):
        type = IS_REELS and 'рилс'
    elif (matched := re.match(fr'(({'|'.join(VK_URLS)})\S*)\s*(.*)', message.text)):
        type = IS_VKCLIPS and 'вк клип'
    else:
        bot.reply_to(message=message,
                     text="Неподдерживаемая ссылка")
        return
    if type:
        VideoHandler(bot, message, type).process(matched)
    else:
        bot.reply_to(message=message, text='Поддержка этого формата была отключена в настройках бота')

@bot.message_handler(commands=['status'])
def send_status(message: dict) -> None:
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    with sqlite3.connect('bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT reels_cnt, shorts_cnt, vk_cnt, err_cnt FROM stats
            WHERE chat_id=?;
        """, (chat_id,))
        REELS_CNT, SHORTS_CNT, VKCLIPS_CNT, ERR_CNT = cursor.fetchone()
    bottext = f"🤖 Бот работает. За время работы:\n" \
              f"🤤 Количество скачанных рилсов: {REELS_CNT}\n" \
              f"🩳 Количество скачанных шортсов: {SHORTS_CNT}\n" \
              f"🤯 Количество скачанных ВК КЛИПОВ: {VKCLIPS_CNT}\n" \
              f"❌ Количество ошибок: {ERR_CNT}"
    bot.send_message(chat_id=chat_id,
                     message_thread_id=thread_id,
                     text=bottext)


@bot.message_handler(commands=['start'])
def send_start(message: dict) -> None:
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    bottext = "🤖 Привет! Основные команды бота:\n" \
              "🤤 /status: узнать статистику по работе бота\n"
    bot.send_message(chat_id=chat_id,
                     message_thread_id=thread_id,
                     text=bottext)
    with sqlite3.connect('bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats(
                chat_id INT PRIMARY KEY,
                reels_cnt INT DEFAULT 0,
                shorts_cnt INT DEFAULT 0,
                vk_cnt INT DEFAULT 0,
                err_cnt INT DEFAULT 0
            );
        """)
        cursor.execute("""
            INSERT INTO stats(chat_id)
            VALUES (?)    
        """, (chat_id,))

# Start polling the bot
logger.info('bot started')
try:
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
except apihelper.ApiException as e:
    logger.error(f"API Exception occurred: {e}")
    # print("Bot is already running on another device. Exiting.")
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")
logger.info("Bot stopped.")