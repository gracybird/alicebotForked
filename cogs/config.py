#
# Configuration for gracyBot
#

# sybol that proceeds all commands
import os

from classes.utils import parse_interval
from gracybot import botconfig, db, known_config

# bot prefix
prefix = '.'

# bot token from discord setup
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# prefix for database filenames
db_prefix = 'db_'

#logpath
logpath = os.path.dirname(os.path.realpath(__file__))

def read(guild, section):
    """
    Private function to turn a db table of config into a dict
    """
    tab = db[guild.id].table(section)
    out = dict()
    for r in tab.all():
        out[ r['key'] ] = r['value']
    return out


def set(guild, section, key, value):
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
    botconfig[guild.id][section] = read(guild, section)


def get(guild, section, key, type='string'):
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


def config_load(guild):
    """
    Reload all the configuration fr this guild
    """
    global botconfig
    botconfig[guild.id] = dict()
    botconfig[guild.id]['config'] = read(guild, 'config')
    botconfig[guild.id]['access'] = read(guild, 'access')
    botconfig[guild.id]['dict'] = read(guild, 'dict')
    botconfig[guild.id]['convert'] = read(guild, 'convert')
    botconfig[guild.id]['mee6'] = API(guild.id)
    botconfig[guild.id]['last_msg'] = dict()


def find_config(name):
    """ look up a name in the known configs """
    for config in known_config:
        if config[0] == name:
            return config
    return None
