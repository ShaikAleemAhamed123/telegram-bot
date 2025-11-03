# How to RUN the BOT Locally and chat from telegram
1. Go to `BotFather` in telegram and create a new bot and get a bot token.
2. `clone` the repository(cd to it)
3. Install `uv` in your machine
4. create `.env` file with contents `BOT_TOKEN=<your-bot-token-here>`. 
5. delete all contents of `cache.json`
6. create a venv with uv `uv venv .venv`
7. activate the venv `source .venv/activate/bin`
8. run `uv sync` to install all the required packages
9. run the bot with `uv run fastapi run main.py` to serve the files via BOT API(files > 50MB will be shared as chunks). 
10. (pls follow foot-note) run `uv run fastapi new_main.py` to serve files via telegram client..suitable for large files(Files of All Sizes will be served as a single file)
11. Install `NGROK` in your system
12. create an account in ngrok and acquire the `auth-token`
13. add ngrok auth token in your local machine `ngrok config add-authtoken <auth-token>`
14. Tunnel your local system using ngrok.. so that telegram servers can contact your bot. Run the following to tunnel `ngrok http <port number where bot is running>`.
15. register webhook for your bot with telegram by running `curl -F "url=<your ngrok tunneled end point of the bot>" https://api.telegram.org/bot<bot_token>/setWebhook`
16. yay.. Now you have your `bot running`.. anyone on telegram can chat with your bot.
>If using Point-10 to run the bot.. you need to create a new telegram client-app and get API_ID and API_HASH and set it in .env file.
