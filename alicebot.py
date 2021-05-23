#!/usr/bin/env python3

import os
import time
import math
import re
import discord
from discord.ext import tasks, commands
from tinydb import TinyDB, Query
from timeloop import Timeloop
from datetime import timedelta
from datetime import datetime
import abconfig

known_config = ( ('invite_cooldown', 'interval'),
                 ('invite_timespan', 'interval'),
                 ('autokick_hasrole', 'role'),
                 ('autokick_timelimit', 'interval'),
                 ('autokick_reason', 'string'),
                 ('log_channel', 'channel'),
                 ('announce_channel', 'channel'),
               )

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=abconfig.prefix, intents=intents)
db = dict()
botconfig = dict()
tl = Timeloop()

logpath = os.path.dirname(os.path.realpath(__file__))

def isfloat(a):
    """ Is the argument a floating point number"""
    try:
        float(a)
        return True
    except ValueError:
        pass
    return False

def isexpression(a):
    """ does the argument contain a valid expression """
    if 'x' not in a:
        return False
    try:
        res = eval(a, {'x': 1.0})
        return True
    except SyntaxError as err:
        print("SyntaxError +%d: %s" % (err.offset, err.text))
    except NameError as err:
        print("Var not found: %s" % err)
    #except (SyntaxError, NameError):
    #    pass
    return False

def find_config(name):
    """ look up a name in the known configs """
    for config in known_config:
        if config[0] == name:
            return config
    return None

def has_role(member, roleid):
    """ test for role id in members role list """
    if any(r.id == roleid for r in member.roles):
        return True
    return False

def timestr(secs):
    """ print number of seconds as a human readable value """
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

regex = re.compile(r'^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?$')

def parse_interval(time_str):
    """ parse human readable interval into a timedelta """
    parts = regex.match(time_str)
    if parts is None:
        return None
    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    return timedelta(**time_params)

def log(guild, channel, text):
    """ write an entry to the logfile """
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
    botconfig[guild.id]['convert'] = config_read(guild, 'convert')

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

def config_get(guild, section, key, type='string'):
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
    answer = botconfig[guild.id][section][key]
    if type == 'interval':
        answer = parse_interval(answer)
    elif type == 'role':
        answer = guild.get_role(answer)
    elif type == 'channel':
        answer = guild.get_channel(answer)
    return answer

def db_get(guild, user, table, key):
    """ lookup a config value for this guild """
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
    elif has_role(ctx.author, need):
        answer = True
        reason = "Match"

    log(ctx.guild, ctx.channel, "perm_check({},{}) = {}".format(ctx.invoked_with, need, reason))
    return answer

def convert_makekey(unit, subunit):
    if subunit:
        return "{}|{}".format(unit,subunit)
    else:
        return "{}".format(unit)

def convert_splitkey(key):
    unit = None
    sub = None
    if key:
        parts = key.split('|')
        unit = parts[0]
        if len(parts) > 1:
            sub = parts[1]
    return (unit,sub)

@bot.command()
async def convert(ctx, *args):
    '''
    Convert values between units
    '''
    if not perm_check(ctx, None):
        return

    response = None
    if args and args[0] == 'list':
        response = "Known conversions:\n"
        whole = config_read(ctx.guild, 'convert')
        count = 0
        if whole:
            whole = sorted(whole)
        for c in whole:
            (unit, sub) = convert_splitkey(c)
            if count > 0:
                response += ","
            response += " {}".format(unit)
            if sub:
                response += " [{}]".format(sub)
            count += 1

    elif not args or args[0] == 'help' or len(args) < 2:
        response = 'Usage: .convert {value} {unit} [subunit]\n' \
                   '   or: .convert list\n' \
                   '\n' \
                   'e.g.  .convert 30 pmol/l e2\n'
    elif not isfloat(args[0]) or ':' not in x:
        response = "Error: the first argument must be a value or time"
    else:
        try:
          value = float(args[0])
        except ValueError:
          pass
        baseunit = args[1].lower()
        subunit = None
        if len(args) > 2:
            subunit = args[2].lower()
        key = convert_makekey(baseunit, subunit)
        item = config_get(ctx.guild, 'convert', key)
        if not item:
            response = "Sorry I don't know how to convert from {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
        else:
            destunit = item[0]
            factor = item[1]
            if isfloat(factor):
                output = value * float(factor)
            elif isexpression(factor):
                output = eval(factor, {'x': value})
            else:
                response = "Error in conversion factor '{}'".format(factor)
            if output:
                response = "{} {} is {:.2f} {}".format(value, baseunit, output, destunit)

    if response:
        await ctx.send(response)

@bot.command()
async def conversion(ctx, *args):
    '''
    Define a conversion
    '''
    if not perm_check(ctx, None):
        return

    response = None
    if len(args)==1 and args[0] == 'list':
        response = "Known conversions:\n"
        whole = config_read(ctx.guild, 'convert')
        for c in whole:
            item = whole[c]
            (unit, sub) = convert_splitkey(c)
            factor = item[1]
            if sub:
                response += " * {} [{}]".format(unit, sub)
            else:
                response += " * {}".format(unit)
            if isexpression(factor):
                response += " = {} -> {}\n".format(factor, item[0])
            else:
                response += " = x * {} -> {}\n".format(factor, item[0])


    elif args and args[0] == 'remove':
        if len(args) < 2:
            response = "Usage: .convert remove {fromunit} [subunit]"
        else:
            baseunit = args[1].lower()
            subunit = None
            if len(args) > 2:
                subunit = args[2].lower()
            key = convert_makekey(baseunit, subunit)
            response = "conversion for {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
            if not config_get(ctx.guild, 'convert', key):
                response += " not found"
            else:
                config_set(ctx.guild, 'convert', key, None)
                response += " deleted"

    elif not args or args[0] == 'help' or len(args) < 3:
        response = 'Usage: .conversion {fromunit} {factor/formula} {tounit} [subunit]\n' \
                   '   or: .conversion list\n' \
                   '   or: .conversion remove {fromunit} [subunit]\n' \
                   '\n' \
                   'e.g.  .conversion pmol/l 3.671 pg/ml e2\n' \
                   '      .conversion celsius "((x-32)*5)/9" fahrenheit'
    else:
        baseunit = args[0].lower()
        factor = args[1]
        tounit = args[2]
        subunit = None
        if len(args) > 3:
            subunit = args[3].lower()

        if not isfloat(factor) and not isexpression(factor):
            response = "Factor must be a float or an expression manipulating x.  e.g. '((x-32)*5/9' instead of '%s'" % factor
        else:
            response = "Convert {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
            response += " into {} with {}".format(tounit, factor)

            key = convert_makekey(baseunit, subunit)
            config_set(ctx.guild, 'convert', key, (tounit, factor, subunit))
    
    if response:
        await ctx.send(response)


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
    mintime = config_get(ctx.guild, 'config', 'invite_cooldown', 'interval')
    if not mintime:
        mintime = 3600
    else:
        mintime = mintime.total_seconds()

    timespan = config_get(ctx.guild, 'config',  'invite_timespan', 'interval')
    if not timespan:
        timespan = 3600
    else:
        timespan = timespan.total_seconds()

    last = db_get(ctx.guild, u, "invite", "last")
    now = int(time.time())
    if not last or last == 0 or (now - last) > mintime:
        link = await discord.TextChannel.create_invite(ctx.message.channel, max_age=timespan, max_uses=1)
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
            text = text + "* " + key[0] + " = "
            val = config_get(ctx.guild, 'config', key[0], type=key[1])
            if not val:
                text = text + "_Not set_\n"
            elif key[1] == 'role':
                    text += "'@{}' [{}]\n".format(val.name,val.id)
            elif key[1] == 'channel':
                    text += "'#{}' [{}]\n".format(val.name,val.id)
            else:
                text = text + "'" + str(val) + "'\n"
    elif args[0] == "help":
        text = "config set {key} {value}\nconfig get {key}\nconfig unset {key}\n"
    elif args[0] == 'get':
        if not args[1]:
            text = 'Usage: config get {value}'
        else:
            key = find_config(args[1])
            if not key:
                text = "Unknown config value '"+args[1]+"'"
            else:
                val = config_get(ctx.guild, 'config', key[0], type=key[1])
                if not val:
                    text = "No config set for '"+key[0]+"'"
                elif key[1] == 'role':
                    text = "Config {} = @{} [{}]".format(key[0],val.name,val.id)
                elif key[1] == 'channel':
                    text = "Config {} = #{} [{}]".format(key[0],val.name,val.id)
                else:
                    text = "Config {} = {}".format(key[0],val)
    elif args[0] == 'set':
        if not args[1] or not args[2]:
            text = "Usage: config set key value"
        elif not find_config(args[1]):
            text = "Unknown config setting %s" % (args[1])
        else:
            key = find_config(args[1])
            value = args[2]
            if key[1] == 'role':
                if ctx.message.role_mentions:
                    role = ctx.message.role_mentions[0]
                else:
                    role = ctx.guild.get_role(int(value))
                if not role:
                    text = "Could not find a role matching %s" % (value)
                else:
                    config_set(ctx.guild, 'config', key[0], role.id)
                    text = "Set config %s = %d (%s)" % (key[0], role.id, role.name)
            elif key[1] == 'channel':
                if ctx.message.channel_mentions:
                    channel = ctx.message.channel_mentions[0]
                else:
                    channel = ctx.guild.get_channel(int(value))
                if not channel:
                    text = "Could not find channel matching %s" % (value)
                else:
                    config_set(ctx.guild, 'config', key[0], channel.id)
                    text = "Set config %s = %d (%s)" % (key[0], channel.id, channel.name)

            else:
                config_set(ctx.guild, 'config', key[0], value)
                text = "Set config %s = %s" % (key[0], value)
            log(ctx.guild, ctx.channel, "User {}[{}] just set config {}={}".format(ctx.author.display_name, ctx.author.id, key[0], value))
    elif args[0] == 'unset':
        if not args[1]:
            text = 'Usage: config unset {key}'
        else:
            key = find_config(args[1])
            if not key:
                text = "Unknown config value '"+args[1]+"'"
            else:
                val = config_set(ctx.guild, 'config', key[0], None)
                text = "Removed config value for '"+key[0]+"'"
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

@bot.command()
async def updateusers(ctx, *args):
    '''
    Forced Update of the user info db
    '''
    if not perm_check(ctx, 0):
        return

    count = 0
    for mem in ctx.guild.members:
        db_set(ctx.guild, mem, "info", "joined", str(mem.joined_at))
        db_set(ctx.guild, mem, "info", "nick", mem.nick)
        count += 1
    text = "Updated %d members." % count
    await ctx.send(text)

@tasks.loop(hours=1.0)
async def periodic():
    log(None, None, "Timed loop")
    today = datetime.utcnow()
    for guild in bot.guilds:
        log(guild, None, 'Guild '+guild.name+' has '+str(len(guild.members))+' members.')
        wantrole = config_get(guild, 'config', 'autokick_hasrole' )
        timeout = config_get(guild, 'config', 'autokick_timelimit', type='interval')
        reason = config_get(guild, 'config', 'autokick_reason')
        channel = config_get(guild, 'config', 'log_channel', type='channel')
        logtext = str()
        if wantrole and timeout:
            for member in guild.members:
                if has_role(member, wantrole):
                    onfor = today - member.joined_at
                    if onfor > timeout:
                        logtext += " - %s expired by %s\n" % ( member.display_name, str(onfor - timeout))
                        if reason:
                            await guild.kick(member, reason=reason)
                        else:
                            #await guild.kick(member)
                            pass
        if logtext and channel:
            if reason:
                info = "The following users have been autokicked :-\n"
            else:
                info = "The following users will be kicked if you set autokick_reason:\n"
            await channel.send(info + logtext)

@periodic.before_loop
async def before_periodic():
#    print("Timed loop setup...")
    pass

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

    periodic.start()
    
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

@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = config_get(guild, 'config', 'announce_channel', type='channel')
    if not channel:
        #print("No announce channel configured for guild %s" % guild.name)
        return
    name = "%s#%s" % (member.name, member.discriminator)
    text = "**%s** just joined the server." % name
    db_set(guild, member, "info", "joined", str(member.joined_at))
    db_set(guild, member, "info", "nick", member.nick)
    #await channel.send(text)

@bot.event
async def on_member_remove(member):
    guild = member.guild
    channel = config_get(guild, 'config', 'announce_channel', type='channel')
    if not channel:
        return

    name = "%s#%s" % (member.name, member.discriminator)
    nick = db_get(guild, member, "info", "nick")
    joined = db_get(guild, member, "info", "joined");
    if nick:
        text = "**%s** (%s) just left the server." % (nick, name)
    else:
        text = "**%s** just left the server." % (name)
    if joined:
        text += "\nThey joined the server on %s" % joined
    await channel.send(text)

@bot.event
async def on_member_update(before, after):
    guild = before.guild
    channel = config_get(guild, 'config', 'announce_channel', type='channel')
    text = None
    if not channel:
        return

    if before.nick != after.nick:
        #text = "%s changed their nick to %s" % (before.display_name, after.nick)
        db_set(guild, after, "info", "nick", str(after.nick))
    else:
        #text = "%s changed something we dont care about" % after.display_name
        pass

    if text:
        await channel.send(text)

bot.run(abconfig.token)
