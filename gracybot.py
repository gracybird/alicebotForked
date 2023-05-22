#!/usr/bin/env python3

import time
from classes.utils import utils.log
import discord
from discord.ext import tasks, commands
from tinydb import TinyDB
from datetime import datetime
import config
import classes.events as events
import classes.tasks as tasks
import classes.commands as commands
import classes.user as user
import classes.utils as utils


known_config = ( ('invite_cooldown', 'interval'),
                 ('invite_timespan', 'interval'),
                 ('autokick_hasrole', 'role'),
                 ('autokick_timelimit', 'interval'),
                 ('autokick_reason', 'string'),
                 ('utils.log_channel', 'channel'),
                 ('announce_arrive', 'channel'),
                 ('announce_leave', 'channel'),
               )

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=config.prefix, intents=intents)
db = dict()
botconfig = dict()


events.on_member_update()

@bot.command()
async def convert(ctx, *args):
    '''
    Convert values between units
    '''
    if not user.perm_check(ctx, None):
        return

    response = None
    if args and args[0] == 'list':
        response = "Known conversions:\n"
        whole = utils.config_read(ctx.guild, 'convert')
        count = 0
        if whole:
            whole = sorted(whole)
        for c in whole:
            (unit, sub) = utils.convert_splitkey(c)
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
    elif not utils.isfloat(args[0]) and ':' not in args[0]:
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
        key = utils.convert_makekey(baseunit, subunit)
        item = utils.config_get(ctx.guild, 'convert', key)
        if not item:
            response = "Sorry I don't know how to convert from {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
        else:
            destunit = item[0]
            factor = item[1]
            if utils.isfloat(factor):
                output = value * float(factor)
            elif utils.isexpression(factor):
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
    if not user.perm_check(ctx, None):
        return

    response = None
    if len(args)==1 and args[0] == 'list':
        response = "Known conversions:\n"
        whole = utils.config_read(ctx.guild, 'convert')
        for c in whole:
            item = whole[c]
            (unit, sub) = utils.convert_splitkey(c)
            factor = item[1]
            if sub:
                response += " * {} [{}]".format(unit, sub)
            else:
                response += " * {}".format(unit)
            if utils.isexpression(factor):
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
            key = utils.convert_makekey(baseunit, subunit)
            response = "conversion for {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
            if not utils.config_get(ctx.guild, 'convert', key):
                response += " not found"
            else:
                utils.config_set(ctx.guild, 'convert', key, None)
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

        if not utils.isfloat(factor) and not utils.isexpression(factor):
            response = "Factor must be a float or an expression manipulating x.  e.g. '((x-32)*5/9' instead of '%s'" % factor
        else:
            response = "Convert {}".format(baseunit)
            if subunit:
                response += " [{}]".format(subunit)
            response += " into {} with {}".format(tounit, factor)

            key = utils.convert_makekey(baseunit, subunit)
            utils.config_set(ctx.guild, 'convert', key, (tounit, factor, subunit))
    
    if response:
        await ctx.send(response)


@bot.command()
async def define(ctx, *args):
    '''
    Define a word
    '''
    if not user.perm_check(ctx, None):
        return

    response = None
    if not args or args[0] == 'help':
        response = 'Usage: .define word Text of definition....'
    else:
        keyword = args[0].lower()
        rest = args[1:]
        u = ctx.author
        c = utils.config_get(ctx.guild, 'dict', keyword)

        if not rest:
            if not c:
                response = 'No dictionary entry for "' + keyword + '"'
            else:
                response = "Removed definition of '"+keyword+"'"
                utils.config_set(ctx.guild, 'dict', keyword, None)
        else:
            text = " ".join(rest)
            utils.config_set(ctx.guild, 'dict', keyword, text)
            response = "Defined '"+keyword+"' as '"+text+"'"

    if response:
        await ctx.send(response)

@bot.command()
async def d(ctx, *args):
    '''
    Print a word definition
    '''
    if not user.perm_check(ctx, None):
        return

    response = None
    if not args or args[0] == 'help':
        response = 'Usage: '+config.prefix+'d word\nPrints the definitionof the given word.'
    elif args[0] == 'list':
        response = "Known dictionary words: "
        whole = utils.config_read(ctx.guild, 'dict')
        response += ", ".join(whole.keys())
    else:
        keyword = args[0].lower()
        u = ctx.author
        c = utils.config_get(ctx.guild, 'dict', keyword)

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
    if not user.perm_check(ctx, None):
        return

    u = ctx.author
    c = utils.db_get(ctx.guild, u, 'PingCount', 'count')
    if not c:
        c = 1
    else:
        c = c + 1
    utils.db_set(ctx.guild, u, 'PingCount', 'count', c)

    await ctx.send(u.display_name + ' you have said ping ' + str(c) + ' times')

@bot.command()
async def invite(ctx):
    '''
    create a 24hour invite
    '''
    if not user.perm_check(ctx, 676891619773120589):
        return
    u = ctx.author
    mintime = utils.config_get(ctx.guild, 'config', 'invite_cooldown', 'interval')
    if not mintime:
        mintime = 3600
    else:
        mintime = mintime.total_seconds()

    timespan = utils.config_get(ctx.guild, 'config',  'invite_timespan', 'interval')
    if not timespan:
        timespan = 3600
    else:
        timespan = timespan.total_seconds()

    last = utils.db_get(ctx.guild, u, "invite", "last")
    now = int(time.time())
    if not last or last == 0 or (now - last) > mintime:
        link = await discord.TextChannel.create_invite(ctx.message.channel, max_age=timespan, max_uses=1)
        dur = utils.timestr(timespan)
        await u.send('Here is an invite valid for {} {}'.format(dur, link.url))
        await ctx.send('Invite sent to '+u.display_name)
        utils.db_set(ctx.guild, u, "invite", "last", now)
        utils.log(ctx.guild, ctx.channel, "{}[{}] created an {} invite".format(ctx.author.display_name, ctx.author.id, dur))
    else:
        delta = now - last
        remain = int(mintime - delta)
        await ctx.send('Sorry '+u.display_name+', you have issued an invite too recently, please wait another '+utils.timestr(remain))

@bot.command()
async def config(ctx, *args):
    '''
    Configuration commands
    '''
    if not user.perm_check(ctx, 0):
        return

    gid = ctx.guild.id
    if not args or args[0] == 'list':
        text = "gracyBot config values :-\n"
        for key in known_config:
            text = text + "* " + key[0] + " = "
            val = utils.config_get(ctx.guild, 'config', key[0], type=key[1])
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
            key = utils.find_config(args[1])
            if not key:
                text = "Unknown config value '"+args[1]+"'"
            else:
                val = utils.config_get(ctx.guild, 'config', key[0], type=key[1])
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
        elif not utils.find_config(args[1]):
            text = "Unknown config setting %s" % (args[1])
        else:
            key = utils.find_config(args[1])
            value = args[2]
            if key[1] == 'role':
                if ctx.message.role_mentions:
                    role = ctx.message.role_mentions[0]
                else:
                    role = ctx.guild.get_role(int(value))
                if not role:
                    text = "Could not find a role matching %s" % (value)
                else:
                    utils.config_set(ctx.guild, 'config', key[0], role.id)
                    text = "Set config %s = %d (%s)" % (key[0], role.id, role.name)
            elif key[1] == 'channel':
                if ctx.message.channel_mentions:
                    channel = ctx.message.channel_mentions[0]
                else:
                    channel = ctx.guild.get_channel(int(value))
                if not channel:
                    text = "Could not find channel matching %s" % (value)
                else:
                    utils.config_set(ctx.guild, 'config', key[0], channel.id)
                    text = "Set config %s = %d (%s)" % (key[0], channel.id, channel.name)

            else:
                utils.config_set(ctx.guild, 'config', key[0], value)
                text = "Set config %s = %s" % (key[0], value)
            utils.log(ctx.guild, ctx.channel, "User {}[{}] just set config {}={}".format(ctx.author.display_name, ctx.author.id, key[0], value))
    elif args[0] == 'unset':
        if not args[1]:
            text = 'Usage: config unset {key}'
        else:
            key = utils.find_config(args[1])
            if not key:
                text = "Unknown config value '"+args[1]+"'"
            else:
                val = utils.config_set(ctx.guild, 'config', key[0], None)
                text = "Removed config value for '"+key[0]+"'"
    else:
        text = "Unrecognised operation " + args[0]
    await ctx.send(text)

@bot.command()
async def access(ctx, *args):
    '''
    Access control to commands
    '''
    if not user.perm_check(ctx, 0):
        return

    if not args or args[0] == 'list':
        text = "Usage: access list                  - list all commands\n"
        text += "       access set {command} {role}  - restrict usage of command\n"
        text += "       access unset {command}       - remove restriction\n"
        text += "Command access permissions :-\n"
        for cmd in bot.commands:
            text = text + " * {} - ".format(cmd.name)
            val = utils.config_get(ctx.guild, 'access', cmd.name)
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
                utils.config_set(ctx.guild, 'access', cmd.name, role.id)
                text = "Restricting {} command to @{} [id:{}]".format(cmd.name, role.name, role.id)
                utils.log(ctx.guild, ctx.channel, "User {}[{}] restricted {} to {}[{}]".format(ctx.author.display_name, ctx.author.id, cmd.name, role.name, role.id))
    elif args[0] == 'unset':
        cmd = None
        for c in bot.commands:
            if c.name == args[1]:
                cmd = c
        if not cmd:
            text = "Could not find command '{}'".format(args[1])
        else:
            utils.config_set(ctx.guild, "access", cmd.name, None)
            text = "Removing restriction on command {}".format(cmd.name)
            utils.log(ctx.guild, ctx.channel, "User {}[{}] unrestricted {}".format(ctx.author.display_name, ctx.author.id, cmd.name))
    else:
        text = "Unrecognised operation " + args[0]

    await ctx.send(text)

@bot.command()
async def userinfo(ctx, *args):
    '''
    Forced Update of the user info db
    '''
    if not user.perm_check(ctx, 0):
        return

    if args and args[0] == 'update':
        count = 0
        for mem in ctx.guild.members:
            utils.db_set(ctx.guild, mem, "info", "joined", str(mem.joined_at))
            utils.db_set(ctx.guild, mem, "info", "nick", mem.nick)
            count += 1
        text = "Updated %d members." % count
        lastmsg = {}
        for chan in ctx.guild.channels:
            if chan.type != discord.ChannelType.text:
                continue
            hist = chan.history(limit=None)
            async for msg in hist:
                if msg.author.id in lastmsg:
                    if msg.created_at > lastmsg[msg.author.id]:
                        lastmsg[msg.author.id] = msg.created_at
                else:
                    lastmsg[msg.author.id] = msg.created_at
        for uid in lastmsg:
            mem = bot.get_user(uid)
            if mem:
                utils.db_set(ctx.guild, mem, "info", "lastmsg", str(lastmsg[uid]))
        text += "\nUpdated %d users last message time." % len(lastmsg)

    elif args[0]:
        uid = int(args[0])
        mem = bot.get_user(uid)
        joined = utils.db_get(ctx.guild, mem, "info", "joined")
        nick = utils.db_get(ctx.guild, mem, "info", "nick")
        lastmsg = utils.db_get(ctx.guild, mem, "info", "lastmsg")
        text = ">>> User: %s#%s (ID: %d)" % (mem.name, mem.discriminator, uid)
        if joined:
            text += "\nJoined: %s ago." % utils.timesince(joined)
        if nick:
            text += "\nLast Nickname: %s" % nick
        if lastmsg:
            text += "\nLast message: %s ago." % utils.timesince(lastmsg)
        if botconfig[ctx.guild.id]['mee6']:
            try:
                mee6API = botconfig[ctx.guild.id]['mee6']
                level = await mee6API.levels.get_user_level(mem.id)
                text += "\nMEE6 Level: %s" % level
            except Exception:
                pass

    await ctx.send(text)
    #foobar

@tasks.loop(minutes=60)
async def periodic_autokick():
    """ check for users that should be kicked """
    utils.log(None, None, "AutoKick Timed loop")
    today = datetime.utcnow()
    for guild in bot.guilds:
        utils.log(guild, None, 'Guild '+guild.name+' has '+str(len(guild.members))+' members.')
        wantrole = utils.config_get(guild, 'config', 'autokick_hasrole' )
        timeout = utils.config_get(guild, 'config', 'autokick_timelimit', type='interval')
        reason = utils.config_get(guild, 'config', 'autokick_reason')
        channel = utils.config_get(guild, 'config', 'utils.log_channel', type='channel')
        utils.logtext = str()
        if wantrole and timeout:
            for member in guild.members:
                if user.has_role(member, wantrole):
                    onfor = today - member.joined_at
                    if onfor > timeout:
                        utils.logtext += " - %s expired by %s\n" % ( member.display_name, str(onfor - timeout))
                        if reason:
                            utils.db_set(guild, member, "info", "kicked", reason)
                            await guild.kick(member, reason=reason)
                        else:
                            #await guild.kick(member)
                            pass
        if utils.logtext and channel:
            if reason:
                info = "The following users have been autokicked :-\n"
            else:
                info = "The following users will be kicked if you set autokick_reason:\n"
            await channel.send(info + utils.logtext)
   
@tasks.loop(minutes=2)
async def periodic_flush():
    """ Write out the last message utils.log"""
    today = datetime.utcnow()
    for guild in bot.guilds:
        userlist = botconfig[guild.id]['last_msg']
        botconfig[guild.id]['last_msg'] = dict()
        for uid, when in userlist.items():
            mem = bot.get_user(uid)
            if mem:
                utils.db_set(guild, mem, "info", "lastmsg", str(when))


@bot.event
async def on_ready():
    """
    This event triggers when the bot is connected to the server
    and has received a list of all the guilds.
    open up a db for each one
    """
    utils.log(None, None, "Bot ready")
    for guild in bot.guilds:
        utils.log(None, None, 'guild: ' + guild.name + ' (' + str(guild.id) + ')')
        dbpath = config.db_prefix + str(guild.id) + '.json'
        db[ guild.id ] = TinyDB(dbpath)
        utils.config_load(guild)

    periodic_autokick.start()
    periodic_flush.start()
    
@bot.event
async def on_connect():
    """
    connected to discord, but not necessarily ready to run yet
    """
    utils.log(None, None, "Bot connected")

@bot.event
async def on_guild_join(guild):
    """
    We just joined a server
    """
    utils.log(guild, None, "Joined server " + guild.name)
    dbpath = config.db_prefix + str(guild.id) + '.json'
    db[ guild.id ] = TinyDB(dbpath)
    utils.config_load(guild)

@bot.event
async def on_guild_remove(guild):
    """
    We just left a server
    """
    utils.log(guild, None, "Left server " + guild.name)

@bot.event
async def on_message(msg):
    """
    every message on every server passes through Here
    """
    #print(inspect.getmembers(message))
    botconfig[msg.guild.id]['last_msg'][ msg.author.id ] = msg.created_at
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    """ a member arrived. announce and record it """
    guild = member.guild
    channel = utils.config_get(guild, 'config', 'announce_arrive', type='channel')
    last_seen = utils.db_get(guild, member, "info", "lastseen")
    name = "%s#%s" % (member.name, member.discriminator)
    if last_seen:
        nick = utils.db_get(guild, member, "info", "nick")
        ago = utils.timesince(last_seen)
        text = ">>> **%s** just re-joined the server after %s away." % (name, ago)
        if nick:
            text += "\nThey were previously known as %s" % nick
        if botconfig[guild.id]['mee6']:
            try:
                mee6API = botconfig[guild.id]['mee6']
                level = await mee6API.levels.get_user_level(member.id)
                text += "\nMEE6 Level: %s" % level
            except Exception:
                pass
        text += "\nPlease welcome them back."
    else:
        text = "**%s** just joined the server, please welcome them." % name
    utils.db_set(guild, member, "info", "joined", str(member.joined_at))
    utils.db_set(guild, member, "info", "nick", member.nick)
    utils.db_set(guild, member, "info", "lastseen", None)
    utils.db_set(guild, member, "info", "kicked", None)
    if channel:
        await channel.send(text)

@bot.event
async def on_member_remove(member):
    """ a member left. announce and record it. """
    guild = member.guild
    today = datetime.utcnow()
    channel = utils.config_get(guild, 'config', 'announce_leave', type='channel')
    name = "%s#%s" % (member.name, member.discriminator)
    nick = utils.db_get(guild, member, "info", "nick")
    joined = utils.db_get(guild, member, "info", "joined");
    level = None
    last_msg = utils.db_get(guild, member, "info", "lastmsg");
    reason = utils.db_get(guild, member, "info", "kicked");
    if botconfig[guild.id]['mee6']:
        try:
            mee6API = botconfig[guild.id]['mee6']
            level = await mee6API.levels.get_user_level(member.id)
        except Exception:
            pass

    # remember that they left, so we can welcome them back
    utils.db_set(guild, member, "info", "lastseen", str(today))

    text = ">>> "
    if nick:
        text += "**%s** _(%s)_ has left the server." % (nick, name)
    else:
        text += "**%s** has left the server." % (name)
    if level:
        text += "\nMEE6 Level %s" % level
    if joined:
        text += "\nThey joined the server %s ago." % utils.timesince(joined)
    if last_msg:
        text += "\nTheir last message was %s ago." % utils.timesince(last_msg)
    if reason:
        text += "\nUser was kicked: %s" % reason
    else:
        text += "\nIf you are able, Please check in with them."

    if channel:
        await channel.send(text)

bot.run(config.token)
