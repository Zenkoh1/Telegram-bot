import logging
import os
import sys
from datetime import datetime
import redis
from telegram import Bot
from telegram.ext import Updater, CommandHandler
from telegram.error import BadRequest                      
import pytz
import threading

# Enabling logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Getting mode, so we could define run function for local and Heroku setup
mode = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
REDIS_PASS = os.getenv("REDIS_PASS")
REDIS_NAME = os.getenv("REDIS_NAME")
REDIS_PORT = os.getenv("REDIS_PORT")

MONTH_PAY = 2.50 # One month's worth of spotify

if mode == "dev":
    def run(updater):
        updater.start_polling()
elif mode == "prod":
    def run(updater):
        PORT = int(os.environ.get("PORT", "8443"))
        HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
        updater.start_webhook(listen="0.0.0.0",
                              port=PORT,
                              url_path=TOKEN)
        updater.bot.set_webhook("https://{}.herokuapp.com/{}".format(HEROKU_APP_NAME, TOKEN))
else:
    logger.error("No MODE specified!")
    sys.exit(1)

def get_info(update, context):
    logger.info(f"User {update.effective_user['id']} getting info")

    if len(context.args) == 0:
        info_dict = client.hgetall('money_owed')
        
        msg = "*__Pay money bro__*\n"

        for name, money in info_dict.items():
            money = float(money)
            
            if money < 0:
                money *= -1
                msg += f"{name}: \-${money:.2f}\n"
            else:
                msg += f"{name}: ${money:.2f}\n"
        msg = msg.replace('.', '\.')
        msgs = [msg]
    elif len(context.args) >= 1:
        msgs = []
        for name in context.args:
        
            try:
                name = name.title()
                money = float(client.hget('money_owed', name))
                months_left = int(client.hget('dates', name))
                if money > 0:
                    msg = f"{name} owes Jarryl ${money:.2f} with {months_left} month\(s\) worth of Spotify to pay."
                elif money == 0:
                    msg = f"{name} is debt free."
                elif money <0:
                    msg = f"{name} has paid an extra ${money * -1:.2f} with \(an\) extra {months_left * -1} month\(s\) to go."

                msg = msg.replace('.', '\.')
                msgs.append(msg)

            except TypeError: # will return typeerror because you cant float() a NoneType       
                msg = "Please enter valid names:D"
                msgs = [msg]
                break
    
    for msg in msgs:
        update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)




def get_dates(update, context):
    logger.info(f"User {update.effective_user['id']} attempted to get dates")
    date_dict = client.hgetall('dates')
    msg = "*__No. of months owed__*\n"
    
    for name, num in date_dict.items():
        msg += f"{name}: {num}\n"
        
    msg = msg.replace('.', '\.')
    msg = msg.replace('-', '\-')
   
    update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)

def paid(update, context):
    
    try:
        if len(context.args) == 1:
            name = context.args[0].title()
            client.hset('dates', name, 0)
            client.hset('money_owed', name, 0)
            msg = f"{name} has paid off all his debt\."

        elif len(context.args) == 2:
            name = context.args[0].title()
            num = int(context.args[1])
            client.hincrby('dates', name, - num)
            client.hincrbyfloat('money_owed', name, - num  * MONTH_PAY)

            msg = f"{name} has paid ${num * MONTH_PAY:.2f} for {num} month\(s\) worth of Spotify."
            msg = msg.replace('.', '\.')

        elif len(context.args) > 2:
            msg = "Please enter using the correct format:D"

        update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)

        logger.info(f"User {update.effective_user['id']} paid for {name}")
    
    except BadRequest:
        update.message.reply_text("Please enter a valid name:D", quote = False)

def check_date():
    
    mytimezone = pytz.timezone("Asia/Singapore")
    today_sg = datetime.now(mytimezone)
    month = today_sg.month
    year = int(str(today_sg.year)[2:])
    new_date = f"{month:02d} {year:02d}"
    date_hist = client.lrange('added_dates',0, -1)

    logger.info(f"Checking date @ {today_sg}")
    threading.Timer(60 * 60, check_date).start()
    if new_date not in date_hist:
        add_date(new_date, today_sg)

def add_date(new_date, today_sg):
    logger.info(f"Adding new date:{new_date} to list of added dates")
    client.rpush('added_dates', new_date)
    info_dict = client.hgetall('money_owed')
    name_list = info_dict.keys()

    cost = client.get('cost')
    for name in name_list:
        client.hincrbyfloat('money_owed', name, cost)
        client.hincrby('dates', name, 1)

    show_date = today_sg.strftime('%d %B %Y')
    msg = f"It is {show_date} friends, pls pay Jarryl ${cost:.2f} :D"
    bot.send_message(chat_id = -485281991, text = msg) #chat_id is for the spotify loan shark group
    

def change_cost(update, context):
    try:
        if len(context.args) == 1:

            
            
            try:
                cost = float(context.args[0])
            except ValueError:
                 update.message.reply_text("Please enter a number", parse_mode = 'MarkdownV2', quote = False)
                 return
            client.set('cost', cost)
            msg = f"The cost has been changed to ${cost} per month."
            bot.send_message(chat_id = -485281991, text = msg)
            return

        else:
            msg = f"Enter in the correct format"

        update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)

        
    
    except BadRequest as e:
        update.message.reply_text(f"Enter in the correct format {e}", quote = False)

if __name__ == '__main__':
    client = redis.Redis(
        host= REDIS_NAME,
        port= REDIS_PORT,
        password = REDIS_PASS,
        decode_responses= True)

    logger.info("Starting bot")
    updater = Updater(TOKEN)
    bot = Bot(token=TOKEN)
    check_date()
    
    updater.dispatcher.add_handler(CommandHandler("info", get_info))
    updater.dispatcher.add_handler(CommandHandler("dates", get_dates))
    updater.dispatcher.add_handler(CommandHandler("paid", paid))
    updater.dispatcher.add_handler(CommandHandler("change", change_cost))
    run(updater)

    