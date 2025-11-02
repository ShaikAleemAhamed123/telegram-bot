# How to RUN the BOT Locally and chat from telegram
1. Go to `BotFather` in telegram and create a new bot and get a bot token.
2. `clone` the repository(cd to it)
3. Install `uv` in your machine
4. In main.py file replace the `BOT_TOKEN` with your bot token
5. delete all contents of `cache.json`
6. create a venv with uv `uv venv .venv`
7. activate the venv `source .venv/activate/bin`
8. run `uv sync` to install all the required packages
9. run the bot with `uv run fastapi run main.py`
10. Install `NGROK` in your system
11. create an account in ngrok and acquire the `auth-token`
12. add ngrok auth token in your local machine `ngrok config add-authtoken <auth-token>`
13. Tunnel your local system using ngrok.. so that telegram servers can contact your bot. Run the following to tunnel `ngrok http <port number where bot is running>`.
14. register webhook for your bot with telegram by running `curl -F "url=<your ngrok tunneled end point of the bot>" https://api.telegram.org/bot<bot_token>/setWebhook`
15. yay.. Now you have your `bot running`.. anyone on telegram can chat with your bot.
