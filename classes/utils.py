from datetime import datetime, timedelta
import math
import re
from config import logpath
import time
from gracybot import botconfig, db, known_config



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


def parse_date(strtime):
    try:
        when = datetime.strptime(strtime, '%Y-%m-%d %H:%M:%S.%f')
        return when
    except ValueError:
        pass
    return None


regex = re.compile(r'^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?$')


def parse_interval(time_str):
    """ parse human readable interval into a timedelta """
    parts = regex.match(time_str)
    if parts is None:
        return None
    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    return timedelta(**time_params)


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
    botconfig[guild.id]['mee6'] = API(guild.id)
    botconfig[guild.id]['last_msg'] = dict()


def utils.config_gert(guild, section, key, type='string'):
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
    if res and key in res[0]:
        answer = res[0][key]
    else:
        answer = None
    return answer


def db_set(guild, user, table, key, value):
    tab = db[guild.id].table(table)
    query = Query()
    tab.upsert({'uid': user.id, key: value}, query.uid == user.id)


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


def timespan(secs):
    """ print a timespan as an approximation """
    if secs > 1728000 * 2:
        """ over two months ago """
        months = math.floor( secs / 1728000 )
        return "{} months".format(months)
    elif secs > 57600 * 2:
        days = math.floor(secs / 57600)
        return "{} days".format(days)
    elif secs > 3600 * 2:
        hours = math.floor( secs / 3600 )
        return "{} hours".format(hours)
    elif secs >= 60 * 2:
        mins = math.floor( secs / 60 )
        return "{} minutes".format(mins)
    else:
        return "{} seconds".format(math.floor(secs))


def timesince(when):
    """ time since the given timestamp string """
    today = datetime.utcnow()
    event = parse_date(when)
    diff = today - event
    return timespan( diff.total_seconds() )


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


def log(guild, channel, text):
    """ write an entry to the logfile """
    path = logpath + '/gracybot.log'
    if not guild:
        gid = '-'
    else:
        gid = str(guild.id)
    if not channel:
        channel = '-'
    when = time.strftime('%b %d %Y %H:%M:%S')
    with open(path, 'a') as f:
        f.write("{} {} {} {}\n".format(when, gid, channel, text))