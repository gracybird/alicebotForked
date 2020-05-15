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

def config_read(guild, section):
    """
    Private function to turn a db table of config into a dict
    """
    tab = db[guild.id].table(section)
    out = dict()
    for r in tab.all():
        out[ r['key'] ] = r['value']
    return out

def config_load(guild):
    """
    Reload all the configuration fr this guild
    """
    global botconfig
    botconfig[guild.id] = dict()
    botconfig[guild.id]['config'] = config_read(guild, 'config')
    botconfig[guild.id]['access'] = config_read(guild, 'access')
    botconfig[guild.id]['dict'] = config_read(guild, 'dict')

def config_set(guild, section, key, value):
    """
    Set a single value of config then reload the dicts
    """
    global botconfig
    tab = db[guild.id].table(section)
    query = Query()
    if not value:
        tab.remove(query.key == key)
    else:
        tab.upsert({'key': key, 'value': value}, query.key == key)
    botconfig[guild.id][section] = config_read(guild, section)

def config_get(guild, section, key):
    """
    fetch a single config value
    """
    global botconfig
    if not guild.id in botconfig:
        return None
    if not section in botconfig[guild.id]:
        return None
    if not key in botconfig[guild.id][section]:
        return None
    return botconfig[guild.id][section][key]

def db_get(guild, user, table, key):
    tab = db[guild.id].table(table)
    query = Query()
    res = tab.search((query.uid == user.id))
    if res:
        answer = res[0][key]
    else:
        answer = None
    return answer

def db_set(guild, user, table, key, value):
    tab = db[guild.id].table(table)
    query = Query()
    tab.upsert({'uid': user.id, key: value}, query.uid == user.id)

def perm_check(ctx, need):
    answer = False
    reason = "None"
    
    # is there a configured level (ignore admin only ones)
    level = config_get(ctx.guild, "access", ctx.invoked_with)
    if need != 0 and level:
        need = level

    # a public command
    if not need and need != 0:
        answer = True
        reason = "Public"

    # you were an admin anyway
    elif ctx.author.permissions_in(ctx.channel).administrator:
        answer = True
        reason = "Admin"

    # you have the corresponding role
    elif any(r.id == need for r in ctx.author.roles):
        answer = True
        reason = "Match"

    log(ctx.guild, ctx.channel, "perm_check({},{}) = {}".format(ctx.invoked_with, need, reason))
    return answer

@bot.command()
async def define(ctx, *args):
    '''
    Define a word
    '''
    if not perm_check(ctx, None):
        return

    response = None
    if not args or args[0] == 'help':
        response = 'Usage: .define word Text of definition....'
    else:
        keyword = args[0].lower()
        rest = args[1:]
        u = ctx.author
        c = config_get(ctx.guild, 'dict', keyword)

        if not rest:
            if not c:
                response = 'No dictionary entry for "' + keyword + '"'
            else:
                response = "Removed definition of '"+keyword+"'"
                config_set(ctx.guild, 'dict', keyword, None)
        else:
            text = " ".join(rest)
            config_set(ctx.guild, 'dict', keyword, text)
            response = "Defined '"+keyword+"' as '"+text+"'"

    if response:
        await ctx.send(response)

@bot.command()
async def d(ctx, *args):
    '''
    Print a word definition
    '''
    if not perm_check(ctx, None):
        return

    response = None
    if not args or args[0] == 'help':
        response = 'Usage: '+abconfig.prefix+'d word\nPrints the definitionof the given word.'
    elif args[0] == 'list':
        response = "Known dictionary words: "
        whole = config_read(ctx.guild, 'dict')
        response += ", ".join(whole.keys())
    else:
        keyword = args[0].lower()
        u = ctx.author
        c = config_get(ctx.guild, 'dict', keyword)

        if not c:
            response = 'No dictionary entry for "' + keyword + '"'
        else:
            response = keyword + " -> " + c

    if response:
        await ctx.send(response)

@bot.command()
async def ping(ctx):
    '''
    Simple command to respond
    '''
    if not perm_check(ctx, None):
        return

    u = ctx.author
    c = db_get(ctx.guild, u, 'PingCount', 'count')
    if not c:
        c = 1
    else:
        c = c + 1
    db_set(ctx.guild, u, 'PingCount', 'count', c)

    await ctx.send(u.display_name + ' you have said ping ' + str(c) + ' times')

@bot.command()
async def invite(ctx):
    '''
    create a 24hour invite
    '''
    if not perm_check(ctx, 676891619773120589):
        return
    u = ctx.author
    mintime = config_get(ctx.guild, 'config', 'invite_cooldown')
    if not mintime:
        mintime = 3600
    else:
        mintime = int(mintime)

    timespan = config_get(ctx.guild, 'config',  'invite_timespan')
    if not timespan:
        timespan = 3600
    timespan = int(timespan)

    last = db_get(ctx.guild, u, "invite", "last")
    now = int(time.time())
    if not last or last == 0 or (now - last) > mintime:
        link = await discord.TextChannel.create_invite(ctx.message.channel, max_age=timespan, max_users=1)
        dur = timestr(timespan)
        await u.send('Here is an invite valid for {} {}'.format(dur, link.url))
        await ctx.send('Invite sent to '+u.display_name)
        db_set(ctx.guild, u, "invite", "last", now)
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
    if not perm_check(ctx, 0):
        return

    gid = ctx.guild.id
    if not args or args[0] == 'list':
        text = "AliceBot config values :-\n"
        for key in known_config:
            text = text + "* " + key + " = "
            val = config_get(ctx.guild, 'config', key)
            if not val:
                text = text + "_Not set_\n"
            else:
                text = text + "'" + val + "'\n"
    elif args[0] == "help":
        text = "config set {key} {value}\nconfig get {key}\nConfiguration values available:\n" + ", ".join(known_config)
    elif args[0] == 'get':
        if not args[1]:
            text = 'Usage: config get {value}'
        else:
            key = args[1]
            val = config_get(ctx.guild, 'config', key)
            if not val:
                text = "No config set for '"+key+"'"
            else:
                text = "Config {} = {}".format(key,val)
    elif args[0] == 'set':
        if not args[1] or not args[2]:
            text = "Usage: config set key value"
        elif not args[1] in known_config:
            text = "Unknown config setting %s" % (args[1])
        else:
            config_set(ctx.guild, 'config', args[1], args[2])
            text = "Set config %s = %s" % (args[1], args[2])
            log(ctx.guild, ctx.channel, "User {}[{}] just set config {}={}".format(ctx.author.display_name, ctx.author.id, args[1], args[2]))
    else:
        text = "Unrecognised operation " + args[0]
    await ctx.send(text)

@bot.command()
async def access(ctx, *args):
    '''
    Access control to commands
    '''
    if not perm_check(ctx, 0):
        return

    if not args or args[0] == 'list':
        text = "Usage: access list                  - list all commands\n"
        text += "       access set {command} {role}  - restrict usage of command\n"
        text += "       access unset {command}       - remove restriction\n"
        text += "Command access permissions :-\n"
        for cmd in bot.commands:
            text = text + " * {} - ".format(cmd.name)
            val = config_get(ctx.guild, 'access', cmd.name)
            if cmd.name in ('config','access'):
                text = text + 'Admin only (not configurable)'
            elif not val:
                text = text + 'No restriction'
            else:
                role = ctx.guild.get_role(val)
                if not role:
                    text = text + "Role {} not found!".format(val)
                else:
                    text = text + "@{} [{}]".format(role.name, role.id)
            text = text + "\n"
    elif args[0] == 'set':
        if not args[1] or not args[2]:
            text = "Usage: .access set {command} {role}"
        else:
            cmd = None
            role = None
            for c in bot.commands:
                if c.name == args[1]:
                    cmd = c

            if ctx.message.role_mentions:
                role = ctx.message.role_mentions[0]
            else:
                role = ctx.guild.get_role(int(args[2]))

            if not cmd:
                text = "Could not find command '{}'".format(args[1])
            if not role:
                text = "Please mention a role"
            else:
                config_set(ctx.guild, 'access', cmd.name, role.id)
                text = "Restricting {} command to @{} [id:{}]".format(cmd.name, role.name, role.id)
                log(ctx.guild, ctx.channel, "User {}[{}] restricted {} to {}[{}]".format(ctx.author.display_name, ctx.author.id, cmd.name, role.name, role.id))
    elif args[0] == 'unset':
        cmd = None
        for c in bot.commands:
            if c.name == args[1]:
                cmd = c
        if not cmd:
            text = "Could not find command '{}'".format(args[1])
        else:
            config_set(ctx.guild, "access", cmd.name, None)
            text = "Removing restriction on command {}".format(cmd.name)
            log(ctx.guild, ctx.channel, "User {}[{}] unrestricted {}".format(ctx.author.display_name, ctx.author.id, cmd.name))
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
    log(None, None, "Bot ready")
    for guild in bot.guilds:
        log(None, None, 'guild: ' + guild.name + ' (' + str(guild.id) + ')')
        dbpath = abconfig.db_prefix + str(guild.id) + '.json'
        db[ guild.id ] = TinyDB(dbpath)
        config_load(guild)
    
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
    dbpath = abconfig.db_prefix + str(guild.id) + '.json'
    db[ guild.id ] = TinyDB(dbpath)
    config_load(guild)

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
