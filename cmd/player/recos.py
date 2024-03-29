from utils import basicstrip, get_banner_emoji, get_mod_sets_emojis, get_mod_primaries, get_field_legend, translate
from constants import EMOJIS

from swgohgg import get_full_avatar_url, get_swgohgg_player_unit_url

import DJANGO

from swgoh.models import ModRecommendation

help_recos = {
	'title': 'Recommendations Help',
	'description': """Shows recommended mods from Capital Games and Crouching Rancor.

**Syntax**
```
%prefixrecos [players] [characters]```
**Aliases**
```
%prefixr```
**Examples**
Show recommended mods for **Emperor Palpatine**:
```
%prefixr ep```
Or:
```
%prefixr "emperor palpatine"```
Show recommended mods for **Grand Admiral Thrawn**, **Grand Master Yoda**, **Qui-Gon Jinn**, **General Kenobi**, and **Darth Traya**:
```
%prefixr gat gmy qgj gk traya```
Show recommended mods for **Death Trooper**:
```
%prefixr deathtrooper```
Or:
```
%prefixr "death trooper"```
Show recommended mods for **Darth Traya** on someone by mention:
```
%prefixr @Someone traya```
Show recommended mods for **Darth Nihilus** on two players by ally code:
```
%prefixr 123456789 234567891 nih```"""
}

SHORT_STAT_EXCEPTIONS = [
	'Critical Avoidance',
	'Critical Chance',
	'Critical Damage',
]

def get_short_stat(stat_id, language):

	stat_id = stat_id.strip()

	stat_name = stat_id
	if stat_name not in SHORT_STAT_EXCEPTIONS:
		stat_name = translate(stat_name, language)

	tokens = stat_name.split(' ')
	if len(tokens) == 1:
		return tokens[0][0:2]

	elif len(tokens) == 2:
		return '%s%s' % (tokens[0][0], tokens[1][0])

	raise Exception('Invalid short stat request for %s %s (%s)' % (stat_id, language, stat_name))


async def cmd_recos(ctx):

	bot = ctx.bot
	args = ctx.args
	author = ctx.author
	config = ctx.config

	ctx.alt = bot.options.parse_alt(args)
	language = bot.options.parse_lang(ctx, args)

	selected_players, error = bot.options.parse_players(ctx, args)

	selected_units = bot.options.parse_unit_names(args)

	if error:
		return error

	if not selected_players:
		return bot.errors.no_ally_code_specified(ctx)

	if not selected_units:
		return bot.errors.no_unit_selected(ctx)

	if args:
		return bot.errors.unknown_parameters(args)

	ally_codes = [ player.ally_code for player in selected_players ]
	players = await bot.client.players(ally_codes=ally_codes)
	if not players:
			return bot.errors.ally_codes_not_found(ally_codes)

	players = { x['allyCode']: x for x in players }

	emoji_cg = EMOJIS['capitalgames']
	emoji_cr = EMOJIS['crouchingrancor']
	emoji_gg = EMOJIS['swgoh.gg']

	msgs = []
	for player in selected_players:

		ally_code = player.ally_code
		player_data = players[ally_code]
		guild_banner = get_banner_emoji(player_data.get('guildBannerLogo'))
		discord_id = player.discord_id and '<@%s>' % player.discord_id or player.player_name

		lines  = []
		for ref_unit in selected_units:

			lines.clear()

			base_id   = ref_unit.base_id
			unit_name = translate(base_id, language)

			if ref_unit.is_ship:
				continue

			roster = { x['defId']: x for x in player_data['roster'] }
			recos  = ModRecommendation.objects.filter(character_id=ref_unit.id).values()

			for reco in recos:

				source   = EMOJIS[ reco['source'].replace(' ', '').lower() ]

				set1     = EMOJIS[ reco['set1'].replace(' ', '').lower() ]
				set2     = EMOJIS[ reco['set2'].replace(' ', '').lower() ]
				set3     = EMOJIS[ reco['set3'].replace(' ', '').lower() ]

				square   = get_short_stat(reco['square'],   language)
				arrow    = get_short_stat(reco['arrow'],    language)
				diamond  = get_short_stat(reco['diamond'],  language)
				triangle = get_short_stat(reco['triangle'], language)
				circle   = get_short_stat(reco['circle'],   language)
				cross    = get_short_stat(reco['cross'],    language)

				info     = reco['info'].strip()
				info     = info and ' %s' % info or ''

				line = '%s%s%s%s`%s|%s|%s|%s`%s' % (source, set1, set2, set3, arrow, triangle, circle, cross, info)
				lines.append(line)

			if base_id in roster and 'mods' in roster[base_id]:
				unit = roster[base_id]
				spacer = EMOJIS['']
				modsets = get_mod_sets_emojis(config, unit['mods'])
				primaries = get_mod_primaries(config, unit['mods'])
				del(primaries[1])
				del(primaries[3])

				primaries = [ primaries[x] for x in primaries ]

				source   = guild_banner

				set1     = modsets[0]
				set2     = modsets[1]
				set3     = modsets[2]

				short_primaries = []
				for primary in primaries:
					short_primaries.append(get_short_stat(primary, language))

				primaries = '|'.join(short_primaries)

				line = '%s%s%s%s`%s` %s' % (source, set1, set2, set3, primaries, discord_id)

			elif base_id not in roster:
				unit = None
				line = '**%s** is still locked for %s' % (unit_name, discord_id)

			else:
				unit = roster[base_id]
				line = '**%s** has no mods for %s' % (unit_name, discord_id)

			lines.append(config['separator'])
			lines.append(line)

			spacer = EMOJIS[''] * 4

			header = '%s%s%s%s%s' % (spacer, EMOJIS['arrow'], EMOJIS['triangle'], EMOJIS['circle'], EMOJIS['cross'])
			unit_link = '**[%s](%s)**' % (unit_name, get_swgohgg_player_unit_url(ally_code, base_id))

			for line in [ header, config['separator'], unit_link ]:
				lines.insert(0, line)

			msgs.append({
				'title': '',
				'description': '\n'.join(lines),
				'author': {
					'name': ref_unit.name,
					'icon_url': ref_unit.get_image(),
				},
				'image': {
					'url': get_full_avatar_url(config, ref_unit, unit),
				},
				'fields': [ get_field_legend(config, meta='Meta Report') ],
			})

		if not lines:
			msgs.append({
				'title': '== No Recommended Mod Sets ==',
				'description': '**%s** is missing from all source of recommendations.' % unit_name,
			})

	return msgs
