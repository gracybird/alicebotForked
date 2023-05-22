import classes.config as config
import utils


def has_role(member, roleid):
    """ test for role id in members role list """
    if any(r.id == roleid for r in member.roles):
        return True
    return False

def perm_check(ctx, need):
    answer = False
    reason = "None"

    # is there a configured level (ignore admin only ones)
    level = config.get(ctx.guild, "access", ctx.invoked_with)
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

    utils.log(ctx.guild, ctx.channel, "perm_check({},{}) = {}".format(ctx.invoked_with, need, reason))
    return answer

async def on_member_update(before, after):
    """ record any change of users nick """
    if before.nick != after.nick:
        utils.db_set(before.guild, after, "info", "nick", str(after.nick))