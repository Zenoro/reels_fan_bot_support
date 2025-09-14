import threading
import re
import os
from dotenv import load_dotenv, dotenv_values
from telebot import TeleBot, apihelper
import yt_dlp
from params import *
from utils import *

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
        self.text = message.text
        self.username = message.forward_from.username if message.forward_from else message.from_user.username
        self.type = type

    def preprocess(self, wait_text):
        self.bot.delete_message(self.chat_id, self.message.message_id)
        self.feedback_msg = self.bot.send_message(chat_id=self.chat_id,
                                                  message_thread_id=self.thread_id,
                                                  text=wait_text)

    def extract_caption(self, matched):
        user_caption = f'{self.type} от @{self.username}'
        text_caption = matched.groups()[-1]
        self.caption = text_caption + '\n' + user_caption if text_caption else user_caption

    def handle_error(self, error_text):
        self.bot.edit_message_text(chat_id=self.chat_id,
                                   message_id=self.feedback_msg.message_id,
                                   text=error_text)

    def download_and_send_video(self):
        try:
            video_path, info = dwld_YTDLP_video(self.text, YDL_OPTS)
            try:
                if IS_THUMBS:
                    cover_path = dwld_YTThumb(info, os.path.join(os.getcwd(), 'thumbnail.jpg'))
            except:
                print("ERROR OCCURED WHILE TAKING THUMBNAIL")
            self.bot.send_video(chat_id=self.chat_id,
                                message_thread_id=self.thread_id,
                                video=open(video_path, 'rb'),
                                caption=self.caption,
                                thumb=open(cover_path, 'rb'))
            self.bot.delete_message(chat_id=self.chat_id,
                                    message_id=self.feedback_msg.message_id)
            os.remove(video_path) if os.path.exists(video_path) else None
            os.remove(cover_path) if os.path.exists(cover_path) else None
            print(f"Video \"{video_path}\" has sent successfully.")
        except yt_dlp.utils.DownloadError as e:
            self.handle_error(f'{self.type}а не будет :(\nошибка: {e}')
        except:
            self.handle_error('ошибка при загрузке. бот занят или пусть админ смотрит логи')
        
    def process(self, matched):
        self.preprocess(f'ща будет {self.type}')
        self.extract_caption(matched)
        self.download_video()

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
    if type:
        VideoHandler(bot, message, type).process(matched)
    else:
        bot.reply_to(message=message, text='Поддержка этого формата была отключена в настройках бота')

@bot.message_handler(commands=['status'])
def send_status(message: dict) -> None:
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    bottext = '...'
    # bottext = f"🤖 Бот работает. За время работы:\n" \
    #           f"🤤 Количество скачанных рилсов: {REELS_CNT}\n" \
    #           f"🩳 Количество скачанных шортсов: {SHORTS_CNT}\n" \
    #           f"🤯 Количество скачанных ВК КЛИПОВ: {VKCLIPS_CNT}\n" \
    #           f"❌ Количество ошибок: {ERR_CNT}"
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

# Start polling the bot
print("Bot starting")
try:
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
except apihelper.ApiException as e:
    print(f"API Exception occurred: {e}")
    # print("Bot is already running on another device. Exiting.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
print("Bot stopped.")