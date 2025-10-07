import discord

# Important: You must also enable the “Message Content Intent” in your bot’s settings on the Discord Developer Portal
# under “Bot -> Privileged Gateway Intents.”
# Create a variable called intents then make a client, giving it those intents.
intents = discord.Intents.default() # declaring bots permissions
intents.message_content = True # allows the bot to read messages in server
client = discord.Client(intents=intents) 

@client.event
async def on_ready():
    print(f'YAYYYYY it works! {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.contains('$hello world'):
        await message.channel.send('This is my first Discord bot!')

client.run('TOKEN')
