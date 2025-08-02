from telebot import TeleBot
import instaloader
import re
import os
from dotenv import load_dotenv, dotenv_values
import yt_dlp
from params import *
import utils


# Счетчики для статистики
REELS_CNT = 0
SHORTS_CNT = 0
ERR_CNT = 0


# Загрузка переменных окружения из .env файла
load_dotenv()
values = dotenv_values()
bot = TeleBot(values['BOT_TOKEN'])

target_inst_dir = 'reels'
if not os.path.exists(target_inst_dir):
    os.makedirs(target_inst_dir)


if IS_REELS:
    print("Instagram Reels feature is enabled.")
    L = instaloader.Instaloader()
    L.login(values['INST_LOGIN'], values['INST_PASSWORD'])
    print("Logged in to Instagram as:", values['INST_LOGIN'])

    @bot.message_handler(func=lambda message: message.text.startswith(IG_URL))
    def download_and_send_inst(message):
        global REELS_CNT, ERR_CNT
        chat_id = message.chat.id
        text = message.text
        message_id = message.message_id
        thread_id = message.message_thread_id
        if (sender := message.forward_from):
            username = sender.username
        else:
            username = message.from_user.username
        bot.delete_message(chat_id, message_id)
        bot_message = bot.send_message(chat_id=chat_id,
                                    message_thread_id=thread_id,
                                    text='ща будет рилс...')
        matched = re.match(fr'{IG_URL}([^/]*)/\S* ?(.*)', text)
        if not matched:
            bot.edit_message_text(chat_id=chat_id,
                                message_id=bot_message.message_id,
                                text="ты кого наебать пытаешься?")
        else:
            shortcode = matched.group(1)
            user_caption = f'рилс от @{username}'
            text_caption = matched.group(2)
            caption = text_caption + '\n' + user_caption if text_caption else user_caption
            try:
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=target_inst_dir)
                cover = None
                for file in os.listdir(target_inst_dir):
                    if IS_THUMBS and file.endswith('.jpg'):
                        cover = open(f'{target_inst_dir}/{file}', 'rb')
                    if file.endswith('.mp4'):
                        bot.send_video(chat_id=chat_id,
                                    message_thread_id=thread_id,
                                    video=open(f'{target_inst_dir}/{file}', 'rb'),
                                    caption=caption,
                                    cover=cover)
                        bot.delete_message(chat_id, bot_message.message_id)
                        REELS_CNT += 1
                    os.remove(f'{target_inst_dir}/{file}')
            except instaloader.exceptions.InstaloaderException as e:
                ERR_CNT += 1
                bot.edit_message_text(chat_id=chat_id,
                                    message_id=bot_message.message_id,
                                    text=f'рилса не будет :(\nошибка: {e}')
            except:
                ERR_CNT += 1
                bot.edit_message_text(chat_id=chat_id,
                                    message_id=bot_message.message_id,
                                    text='ошибка при загрузке рилса, пусть админ смотрит логи')
else:
    print("Instagram Reels feature is disabled.")


if IS_SHORTS:
    print("YouTube Shorts feature is enabled.")

    @bot.message_handler(func=lambda message: message.text.startswith(YT_FULL_URL)
                        or message.text.startswith(YT_MOBILE_URL))
    def download_and_send_yt(message):
        global SHORTS_CNT, ERR_CNT
        chat_id = message.chat.id
        text = message.text
        message_id = message.message_id
        thread_id = message.message_thread_id
        youtube_url = YT_FULL_URL if YT_FULL_URL in text else YT_MOBILE_URL
        if (sender := message.forward_from):
            username = sender.username
        else:
            username = message.from_user.username
        bot.delete_message(chat_id, message_id)
        bot_message = bot.send_message(chat_id=chat_id,
                                    message_thread_id=thread_id,
                                    text='ща будет шортс...')
        matched = re.match(fr'{youtube_url}\S* ?(.*)', text)
        if not matched:
            bot.edit_message_text(chat_id=chat_id,
                                message_id=bot_message.message_id,
                                text="ты кого наебать пытаешься?")
        else:
            user_caption = f'шортс от @{username}'
            text_caption = matched.group(1)
            caption = text_caption + '\n' + user_caption if text_caption else user_caption
            try:
                with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                    # Получаем информацию о видео перед скачиванием
                    info = ydl.extract_info(text, download=False)
                    filename = ydl.prepare_filename(info)
                    print(f'Скачивание видео: {filename}')
                    ydl.download([text])
                    cover = None
                    try:
                        if IS_THUMBS:
                            cover = open(cvrpth := utils.dwld_YTThumb(info, os.path.join(os.getcwd(), 'thumbnail.jpg')), 'rb')
                    except:
                        print("ERROR OCCURED WHILE TAKING YT SHORTS THUMBNAIL")
                bot.send_video(chat_id=chat_id,
                            message_thread_id=thread_id,
                            video=open(filename, 'rb'),
                            caption=caption,
                            cover=cover)
                bot.delete_message(chat_id, bot_message.message_id)
                os.remove(filename)
                os.remove(cvrpth)
                print(f"Shorts {filename} sent successfully.")
                SHORTS_CNT += 1
            except yt_dlp.utils.DownloadError as e:
                ERR_CNT += 1
                bot.edit_message_text(chat_id=chat_id,
                                    message_id=bot_message.message_id,
                                    text=f'шортса не будет :(\nошибка: {e}')
            except:
                ERR_CNT += 1
                bot.edit_message_text(chat_id=chat_id,
                                    message_id=bot_message.message_id,
                                    text='ошибка при загрузке шортса. бот занят или пусть админ смотрит логи')
else:
    print("YouTube Shorts feature is disabled.")

if not IS_REELS and not IS_SHORTS:
    print("А нахуя я вообще запущен...")


@bot.message_handler(commands=['status'])
def send_status(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    bottext = f"🤖 Бот работает. За время работы:\n" \
              f"🤤 Количество скачанных рилсов: {REELS_CNT}\n" \
              f"🩳 Количество скачанных шортсов: {SHORTS_CNT}\n" \
              f"❌ Количество ошибок: {ERR_CNT}"
    bot.send_message(chat_id=chat_id,
                     message_thread_id=thread_id,
                     text=bottext)


@bot.message_handler(commands=['start'])
def send_start(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    bottext = "🤖 Привет! Основные команды бота:\n" \
              "🤤 /status: узнать статистику по работе бота\n"
    bot.send_message(chat_id=chat_id,
                     message_thread_id=thread_id,
                     text=bottext)


# Start polling the bot
print("Bot starting...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
