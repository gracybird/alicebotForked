#
# Configuration for ALiceBot
#

logfile = '/home/ubuntu/bots/alicebot/alicebot.log'

# sybol that proceeds all commands
prefix = '.'

# bot token from discord setup
token = ''

# prefix for database filenames
db_prefix = '/home/ubuntu/bots/alicebot/db_'

# configs formerly stored in the db
# TODO evaluate these for necessity
# TODO update code to use the remaining vars instead of pulling them from the db
# TODO document what the vars are used for
invite_cooldown = '1d'
invite_timespan = '1d'
log_channel = 626518062446673961
autokick_hasrole = 481116110679179274
autokick_timelimit = '48h'
autokick_reason = 'Took too long to register a profile'
announce_channel = 838121022908661762
announce_arrive = 723423705274777700
announce_leave = 839153372153511956