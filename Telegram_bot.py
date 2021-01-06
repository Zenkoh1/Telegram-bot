import logging
import os
import random
import sys
import redis
from datetime import datetime
from telegram.ext import Updater, CommandHandler
from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)
import pytz

# Enabling logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()
MONTH_PAY = 2.50
# Getting mode, so we could define run function for local and Heroku setup
mode = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
REDIS_PASS = os.getenv("REDIS_PASS")

if mode == "dev":
    def run(updater):
        updater.start_polling()
elif mode == "prod":
    def run(updater):
        PORT = int(os.environ.get("PORT", "8443"))
        HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
        # Code from https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks#heroku
        updater.start_webhook(listen="0.0.0.0",
                              port=PORT,
                              url_path=TOKEN)
        logger.info('test')
        updater.bot.set_webhook("https://{}.herokuapp.com/{}".format(HEROKU_APP_NAME, TOKEN))
else:
    logger.error("No MODE specified!")
    sys.exit(1)


def start_handler(update, context):
    # Creating a handler-function for /start command 
    logger.info("User {} started bot".format(update.effective_user["id"]))
    update.message.reply_text("Hello from Python!\nPress /random to get random number")


def random_handler(update, context):
    # Creating a handler-function for /random command
    number = random.randint(0, 10)
    logger.info("User {} randomed number {}".format(update.effective_user["id"], number))
    update.message.reply_text("Random number: {}".format(number))
    



def get_info(update, context):
    update.message.reply_text('help', parse_mode = 'MarkdownV2', quote = False)

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

    
    print(msg)
    for msg in msgs:

        update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)

def test(update, context):
    table = """
            \| Tables   \|      Are      \|  Cool \|
            \|----------\|---------------\|-------\|
            \| col 1 is \|  left-aligned \| $1600 \|
            \| col 2 is \|    centered   \|   $12 \|
            \| col 3 is \| right-aligned \|    $1 \|
            """
    
    update.message.reply_text(table, parse_mode = 'MarkdownV2', quote = False)



def get_dates(update, context):
    logger.info(f"User {update.effective_user['id']} attempted to get dates")
    """try:
        if len(context.args) == 1:
            name = context.args[0].lower()
            date_list = client.lrange(f"{name}_dates", 0, -1)
            msg = f'*__Monthly Payable \-  {name.title()}__*\n'
            msg += '\n'.join(date_list)
            update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)
        elif len(context.args) == 0:
            update.message.reply_text("Please enter a name:D", quote = False)
        else:
            update.message.reply_text("Please enter only one name:D", quote = False)
    
    except BadRequest: # not a valid entry
       update.message.reply_text("Please enter a valid name:D", quote = False)"""

    
    date_dict = client.hgetall('dates')
    msg = "*__No. of months owed__*\n"

    
    for name, num in date_dict.items():
        
        
        
        msg += f"{name}: {num}\n"
        
        
    msg = msg.replace('.', '\.')
    msg = msg.replace('-', '\-')
   

    update.message.reply_text(msg, parse_mode = 'MarkdownV2', quote = False)

    
def clear(update, context):
    try:
        if len(context.args) == 1:
            name = context.args[0].lower()
            client.delete(f"{name}_dates")

            client.hset('money_owed', f'{name.title()}', 0)

        elif len(context.args) == 2:
            name = context.args[0].lower()
            num = int(context.args[1])
            client.ltrim(f"{name}_dates", num, -1)

            client.hincrbyfloat('money_owed', f'{name.title()}', - num  * MONTH_PAY)

        

        
    
    except BadRequest:
        update.message.reply_text("Please enter a valid name:D", quote = False)
    
    

def check_date(update, context):
    mytimezone=pytz.timezone("Asia/Singapore")
    today = datetime.today()
    today_sg = mytimezone.localize(today)
    month = today_sg.month
    year = int(str(today_sg.year)[2:])
    new_date = f"{month:02d} {year:02d}"
    date_hist = client.lrange('added_dates',0, -1)
    
    if new_date not in date_hist:
        add_date(update, new_date, today_sg)

def add_date(update, new_date, today_sg):
    client.rpush('added_dates', new_date)
    info_dict = client.hgetall('money_owed')
    name_list = info_dict.keys()
    for name in name_list:
        client.hincrbyfloat('money_owed', name, MONTH_PAY)
        client.hincrby('dates', name, 1)

    show_date = today_sg.strftime('%d %B %Y')
    msg = f"It is {show_date} friends, pls pay Jarryl ${MONTH_PAY:.2f} :D"
    update.message.reply_text(msg, quote = False)
    
if __name__ == '__main__':
    client = redis.Redis(
        host= 'redis-14313.c1.us-west-2-2.ec2.cloud.redislabs.com',
        port= '14313',
        password = REDIS_PASS,
        decode_responses= True)

    

    logger.info("Starting bot")
    updater = Updater(TOKEN)

    updater.dispatcher.add_handler(CommandHandler("start", start_handler))
    updater.dispatcher.add_handler(CommandHandler("random", random_handler))
    updater.dispatcher.add_handler(CommandHandler("info", get_info))
    updater.dispatcher.add_handler(CommandHandler("dates", get_dates))
    updater.dispatcher.add_handler(CommandHandler("clear", clear))
    updater.dispatcher.add_handler(CommandHandler("test", check_date))
    run(updater)

    