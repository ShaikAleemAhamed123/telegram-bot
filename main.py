from telegram.ext import Application, CommandHandler

async def reply(update, context):
    await update.message.reply_text("What the hell man ?")


def main():
    """
    Handles the initial launch of the program (entry point).
    """
    token : str = "8311901559:AAEJIF3HbxtkVnf8YjVYQ5IBgAfcPl9Axh4"
    application : Application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    application.add_handler(CommandHandler("hello", reply))
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == '__main__':
    main()