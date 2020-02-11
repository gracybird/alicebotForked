#!/usr/bin/env python3

import os
import time
import math
import discord
from discord.ext import commands
from tinydb import TinyDB, Query
from timeloop import Timeloop
import abconfig

known_config = ( 'invite_cooldown', 'invite_timespan' )
bot = commands.Bot(command_prefix=abconfig.prefix)
db = dict()
botconfig = dict()
tl = Timeloop()

logpath = os.path.dirname(os.path.realpath(__file__))

def timestr(secs):
    if secs > 57600:
        days = math.floor(secs / 57600)
        secs = secs - 57600 * days
        hours = math.floor( secs / 3600 )
        return "{}d {}h".format(days, hours)
    elif secs > 3600:
        hours = math.floor( secs / 3600 )
        secs = secs - 3600 * hours
        mins = math.floor( secs / 60 )
        return "{}h {}m".format(hours, mins)
    elif secs > 60:
        mins = math.floor( secs / 60 )
        secs = secs - 60 * mins
        return "{}m {}s".format(mins, secs)
    else:
        return "{}s".format(secs)

def log(guild, channel, text):
    path = logpath + '/alicebot.log'
    if not guild:
        gid = '-'
    else:
        gid = str(guild.id)
    if not channel:
        channel = '-'
    when = time.strftime('%b %d %Y %H:%M:%S')
    with open(path, 'a') as f:
        f.write("{} {} {} {}\n".format(when, gid, channel, text))

def config_load(server_id):
    tab = db[server_id].table('config')
    out = dict()
    for r in tab.all():
        out[ r['key'] ] = r['value']
    return out

def config_set(server_id, key, value):
    tab = db[server_id].table('config')
    query = Query()
    tab.upsert({'key': key, 'value': value}, query.key == key)

def config_get(server_id, key):
    if not key in botconfig[server_id]:
        return None
    return botconfig[server_id][key]

def db_get(server_id, user_id, table, key):
    tab = db[server_id].table(table)
    query = Query()
    res = tab.search((query.uid == user_id))
    if res:
        answer = res[0][key]
    else:
        answer = None
    return answer

def db_set(server_id, user_id, table, key, value):
    tab = db[server_id].table(table)
    query = Query()
    tab.upsert({'uid': user_id, key: value}, query.uid == user_id)

@bot.command()
async def ping(ctx):
    '''
    Simple command to respond
    '''
    u = ctx.author
    c = db_get(ctx.guild.id, u.id, 'PingCount', 'count')
    if not c:
        c = 1
    else:
        c = c + 1
    db_set(ctx.guild.id, u.id, 'PingCount', 'count', c)

    await ctx.send(u.display_name + ' you have said ping ' + str(c) + ' times')

@bot.command()
async def invite(ctx):
    '''
    create a 24hour invite
    '''
    u = ctx.author
    mintime = config_get(ctx.guild.id, 'invite_cooldown')
    if not mintime:
        mintime = 3600
    else:
        mintime = int(mintime)

    timespan = config_get(ctx.guild.id, 'invite_timespan')
    if not timespan:
        timespan = 3600
    timespan = int(timespan)

    last = db_get(ctx.guild.id, u.id, "invite", "last")
    now = int(time.time())
    if not last or last == 0 or (now - last) > mintime:
        link = await discord.TextChannel.create_invite(ctx.message.channel, max_age=timespan, max_users=1)
        dur = timestr(timespan)
        await u.send('Here is an invite valid for {} {}'.format(dur, link.url))
        await ctx.send('Invite sent to '+u.display_name)
        db_set(ctx.guild.id, u.id, "invite", "last", now)
        log(ctx.guild, ctx.channel, "{}[{}] created an {} invite".format(ctx.author.display_name, ctx.author.id, dur))
    else:
        delta = now - last
        remain = int(mintime - delta)
        await ctx.send('Sorry '+u.display_name+', you have issued an invite too recently, please wait another '+timestr(remain))

@bot.command()
async def config(ctx, *args):
    '''
    Configuration commands
    '''
    global botconfig
    # tis command is admins only
    if not ctx.author.permissions_in(ctx.channel).administrator:
        return

    gid = ctx.guild.id
    if not args or args[0] == 'list':
        text = "AliceBot config values :-\n"
        if not gid in botconfig:
            text = text + "none set"
        else:
            for key in known_config:
                text = text + "* " + key + " = "
                if not key in botconfig[gid]:
                    text = text + "_Not set_\n"
                else:
                    text = text + "'" + botconfig[gid][key] + "'\n"
    elif args[0] == "help":
        text = "config set {key} {value}\nconfig get {key}\nConfiguration values available:\n" + ", ".join(known_config)
    elif args[0] == 'get':
        if not args[1]:
            text = 'Usage: config get {value}'
        else:
            key = args[1]
            if key in botconfig[gid]:
                text = "Config "+key+" = "+botconfig[gid][key]
            else:
                text = "No config set for '"+key+"'"
    elif args[0] == 'set':
        if not args[1] or not args[2]:
            text = "Usage: config set key value"
        elif not args[1] in known_config:
            text = "Unown config setting %s" % (args[1])
        else:
            config_set(ctx.guild.id, args[1], args[2])
            botconfig[ ctx.guild.id ] = config_load(ctx.guild.id)
            text = "Set config %s = %s" % (args[1], args[2])
            log(ctx.guild, ctx.channel, "User {}[{}] just set config {}={}".format(ctx.author.display_name, ctx.author.id, args[1], args[2]))
    else:
        text = "Unrecognised operation " + args[0]
    await ctx.send(text)

@bot.event
async def on_ready():
    """
    This event triggers when the bot is connected to the server
    and has received a list of all the guilds.
    open up a db for each one
    """
    global botconfig
    log(None, None, "Bot ready")
    for guild in bot.guilds:
        log(None, None, 'guild: ' + guild.name + ' (' + str(guild.id) + ')')
        dbpath = abconfig.db_prefix + str(guild.id) + '.json'
        db[ guild.id ] = TinyDB(dbpath)
        botconfig[ guild.id ] = config_load(guild.id)
    
@bot.event
async def on_connect():
    """
    connected to discord, but not necessarily ready to run yet
    """
    log(None, None, "Bot connected")

@bot.event
async def on_guild_join(guild):
    """
    We just joined a server
    """
    log(guild, None, "Joined server " + guild.name)

@bot.event
async def on_guild_remove(guild):
    """
    We just left a server
    """
    log(guild, None, "Left server " + guild.name)

@bot.event
async def on_message(msg):
    """
    every message on every server passes through Here
    """
    #print(inspect.getmembers(message))
    await bot.process_commands(msg)

bot.run(abconfig.token)
