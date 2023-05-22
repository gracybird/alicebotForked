


import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import classes.config as config
import user
import utils
from helpers import checks, db_manager

'''
Convert values between units
'''
class Convert(commands.Cog, name="moderation"):

    async def convert(ctx, *args):
        if not user.perm_check(ctx, None):
            return

        response = None

        if args and args[0] == 'list':
            response = "Known conversions:\n"
            whole = config.read(ctx.guild, 'convert')
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
            item = config.get(ctx.guild, 'convert', key)
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

    '''
    Define a conversion
    '''
    async def conversion(ctx, *args):
        if not user.perm_check(ctx, None):
            return

        response = None
        if len(args)==1 and args[0] == 'list':
            response = "Known conversions:\n"
            whole = config.read(ctx.guild, 'convert')
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
                if not config.get(ctx.guild, 'convert', key):
                    response += " not found"
                else:
                    config.set(ctx.guild, 'convert', key, None)
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
                config.set(ctx.guild, 'convert', key, (tounit, factor, subunit))
        
        if response:
            await ctx.send(response)

    async def setup(bot):
        await bot.add_cog(Convert(bot))
