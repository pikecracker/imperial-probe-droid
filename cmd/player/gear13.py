from utils import translate

from swgohgg import get_full_avatar_url

import DJANGO
from swgoh.models import BaseUnit, Gear13Stat

from collections import OrderedDict

help_gear13 = {
	'title': 'Gear13 Help',
	'description': """Shows most popular gear 13 units that you don't already have.

**Syntax**
```
%prefixgear13 [player] [locked] [limit]```
**Aliases**
```
%prefixg13```
**Options**
**`limit:`** The max number of gear 13 you want to see (default is 25).
**`locked:`** If present, shows most popular gear 13 for units still locked.

**Examples**
Show top 25 most popular gear 13 for characters you have:
```
%prefixg13```
Show top 5 most popular gear 13 units:
```
%prefixg13 5```
Show top 25 most popular gear 13 for characters you don't have:
```
%prefixg13 locked```"""
}

async def cmd_gear13(ctx):

	bot = ctx.bot
	args = ctx.args
	author = ctx.author
	config = ctx.config

	ctx.alt = bot.options.parse_alt(args)
	language = bot.options.parse_lang(ctx, args)

	limit_per_user = bot.options.parse_limit(args)

	include_locked = bot.options.parse_include_locked(args)

	selected_players, error = bot.options.parse_players(ctx, args)

	if error:
		return error

	if args:
		return bot.errors.unknown_parameters(args)

	if not selected_players:
		return bot.errors.no_ally_code_specified(ctx)

	ally_codes = [ x.ally_code for x in selected_players ]
	players = await bot.client.players(ally_codes=ally_codes)
	if not players:
		return bot.errors.ally_codes_not_found(ally_codes)

	players = { x['allyCode']: x for x in players }

	msgs = []
	all_g13 = OrderedDict()
	for g13 in Gear13Stat.objects.all().order_by('-percentage').values():
		unit_id = g13['unit_id']
		g13['locked'] = True
		unit = BaseUnit.objects.get(id=unit_id)
		all_g13[unit.base_id] = g13

	for player in selected_players:

		g13_list = dict(all_g13)

		jplayer = players[player.ally_code]
		jroster = { x['defId']: x for x in jplayer['roster'] }

		for base_id, unit in jroster.items():

			if unit['gear'] == 13:
				del g13_list[base_id]
				continue

			if base_id not in g13_list:
				continue

			g13_list[base_id]['locked'] = False

		lines = []
		limit = limit_per_user
		for base_id, g13 in g13_list.items():

			if g13['locked'] is not include_locked:
					continue

			unit_name = translate(base_id, language)
			percentage = g13['percentage']

			lines.append('`%.2f` **%s**' % (percentage, unit_name))

			limit -= 1
			if limit <= 0:
				break

		msgs.append({
			'author': {
				'name': jplayer['name'],
			},
			'title': 'Most Popular Gear 13',
			'description': '\n'.join(lines),
		})

	return msgs
