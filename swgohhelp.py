#!/usr/bin/python3

from utils import get_units_dict, http_get, http_post, find_ally_in_guild

import json
import sys
from datetime import datetime, timedelta

db = {
	'stats':   {},
	'players': {},
	'guilds':  {},
	'roster':  {},
	'units':   {},
	'events':  {},
	'zetas':   {},
	'data':    {},
}

SWGOH_HELP = 'https://api.swgoh.help'

CRINOLO_PROD_URL = 'https://crinolo-swgoh.glitch.me/statCalc/api'
CRINOLO_TEST_URL = 'https://crinolo-swgoh.glitch.me/testCalc/api'
CRINOLO_BETA_URL = 'https://crinolo-swgoh-beta.glitch.me/statCalc/api'

#
# Internal - Do not call yourself
#

def get_access_token(config):

	if 'access_token' in config['swgoh.help']:
		expire = config['swgoh.help']['access_token_expire']
		if expire > datetime.now() + timedelta(seconds=60):
			return config['swgoh.help']['access_token']

	headers = {
		'method': 'post',
		'content-type': 'application/x-www-form-urlencoded',
	}

	data = {
		'username': config['swgoh.help']['username'],
		'password': config['swgoh.help']['password'],
		'grant_type': 'password',
		'client_id': 'abc',
		'client_secret': '123',
	}

	auth_url = '%s/auth/signin' % SWGOH_HELP
	response, error = http_post(auth_url, headers=headers, data=data)
	if error:
		raise Exception('Authentication failed to swgohhelp API: %s' % error)

	data = response.json()
	if 'access_token' not in data:
		raise Exception('Authentication failed: Server returned `%s`' % data)

	config['swgoh.help']['access_token'] = data['access_token']
	config['swgoh.help']['access_token_expire'] = datetime.now() + timedelta(seconds=data['expires_in'])

	print('Logged in successfully', file=sys.stderr)
	return config['swgoh.help']['access_token']

def get_headers(config):
	return {
		'method': 'post',
		'content-type': 'application/json',
		'authorization': 'Bearer %s' % get_access_token(config),
	}

def call_api(config, project, url):
	headers = get_headers(config)
	print("CALL API: %s %s %s" % (url, headers, project), file=sys.stderr)
	response, error = http_post(url, headers=headers, json=project)
	if error:
		raise Exception('http_post(%s) failed: %s' % (url, error))

	data = response.json()
	if 'error' in data and 'error_description' in data:
		raise Exception(data['error_description'])

	return data

#
# API
#

def api_swgoh_players(config, project):
	return call_api(config, project, '%s/swgoh/players' % SWGOH_HELP)

def api_swgoh_guilds(config, project):
	return call_api(config, project, '%s/swgoh/guilds' % SWGOH_HELP)

def api_swgoh_roster(config, project):
	return call_api(config, project, '%s/swgoh/roster' % SWGOH_HELP)

def api_swgoh_units(config, project):
	return call_api(config, project, '%s/swgoh/units' % SWGOH_HELP)

def api_swgoh_zetas(config, project):
	return call_api(config, project, '%s/swgoh/zetas' % SWGOH_HELP)

def api_swgoh_squads(config, project):
	return call_api(config, project, '%s/swgoh/squads' % SWGOH_HELP)

def api_swgoh_events(config, project):
	return call_api(config, project, '%s/swgoh/events' % SWGOH_HELP)

def api_swgoh_data(config, project):
	return call_api(config, project, '%s/swgoh/data' % SWGOH_HELP)

def api_crinolo(config, units):
	#url = '%s/characters?flags=withModCalc' % CRINOLO_PROD_URL
	#url = '%s/characters?flags=withModCalc,gameStyle' % CRINOLO_TEST_URL
	url = '%s/characters?flags=withModCalc,gameStyle' % CRINOLO_BETA_URL
	print('CALL CRINOLO API: %s' % url, file=sys.stderr)
	response, error = http_post(url, json=units)
	if error:
		raise Exception('http_post(%s) failed: %s' % (url, error))

	data = response.json()
	if 'error' in data:
		raise Exception('POST request failed for URL: %s\n%d Error: %s' % (url, response.status_code, data['error']))

	return data
#
# Fetch functions
#

def fetch_players(config, ally_codes, key='name'):

	# Remove ally codes for which we already have fetched the data
	needed = list(ally_codes)
	for ally_code in ally_codes:
		if int(ally_code) in db['players'] and key in db['players'][int(ally_code)]:
			needed.remove(ally_code)

	if needed:

		# Perform API call to retrieve newly needed player info
		players = api_swgoh_players(config, {
			'allycodes': needed,
		})

		# Store newly needed players in db
		for player in players:

			total, char, ship = get_player_gp_from_roster(player['roster'])

			player['gp'] = {
				'total': total,
				'char': char,
				'ship': ship,
			}

			player['roster'] = get_units_dict(player['roster'], 'defId')

			ally_code = player['allyCode']
			db['players'][ally_code] = player

	players = {}
	for ally_code in ally_codes:
		players[ally_code] = db['players'][int(ally_code)]

	return players

def fetch_guilds(config, ally_codes):

	# Remove ally codes for which we already have fetched the guild data
	needed = list(ally_codes)
	for ally_code in ally_codes:
		if int(ally_code) in db['guilds']:
			needed.remove(ally_code)

	if needed:

		# Perform API call to retrieve newly needed guild info
		guilds = api_swgoh_guilds(config, {
			'allycodes': needed,
		})

		# Store newly needed guilds in db
		for guild in guilds:
			guild['roster'] = get_units_dict(guild['roster'], 'allyCode')
			guild_name = guild['name']
			ally_code = find_ally_in_guild(guild, needed)
			if not ally_code:
				raise Exception('Could not find ally code: %s in guild: %s' % (ally_code, guild_name))
			db['guilds'][int(ally_code)] = guild

	guilds = {}

	for ally_code in ally_codes:
		guilds[ally_code] = db['guilds'][int(ally_code)]

	return guilds

def fetch_units(config, ally_codes):

	# Remove ally codes for which we already have fetched the data
	needed = list(ally_codes)
	for ally_code in ally_codes:
		if int(ally_code) in db['units']:
			needed.remove(ally_code)

	if needed:

		# Perform API call to retrieve newly needed units info
		units = api_swgoh_units(config, {
			'allycodes': needed,
		})

		# Store newly needed units in db
		for base_id, units in units.items():
			for unit in units:
				ally_code = unit['allyCode']
				if ally_code not in db['units']:
					db['units'][ally_code] = {}

				db['units'][ally_code][base_id] = unit

	units = {}

	for ally_code in ally_codes:
		units[ally_code] = db['units'][int(ally_code)]

	return units

def fetch_roster(config, ally_codes):

	# Remove ally codes for which we already have fetched the data
	needed = list(ally_codes)
	for ally_code in ally_codes:
		if int(ally_code) in db['roster']:
			needed.remove(ally_code)

	if needed:

		# Perform API call to retrieve newly needed roster info
		rosters = api_swgoh_roster(config, {
			'allycodes': needed,
		})

		# Store newly needed rosters in db
		for roster in rosters:
			for base_id, unit_roster in roster.items():
				for unit in unit_roster:
					ally_code = unit['allyCode']
					if ally_code not in db['roster']:
						db['roster'][ally_code] = {}

					db['roster'][ally_code][base_id] = unit

	rosters = {}

	for ally_code in ally_codes:
		rosters[ally_code] = db['roster'][int(ally_code)]

	return rosters

def fetch_crinolo_stats(config, ally_codes, base_ids=[]):

	players = api_swgoh_players(config, {
		'allycodes': ally_codes,
	})

	result = {}
	stats = api_crinolo(config, players)

	for player in stats:
		ally_code = player['allyCode']
		result[ally_code] = {}
		for unit in player['roster']:
			base_id = unit['defId']
			if base_id not in base_ids:
				continue

			if base_id not in result[ally_code]:
				result[ally_code][base_id] = unit

	return result, players
#
# Utility functions
#

def get_guilds_ally_codes(guilds):

	ally_codes = {}

	for guild_name, guild in guilds.items():
		for ally_code in guild['roster']:
			ally = guild['roster'][ally_code]
			ally_codes[ally_code] = ally

	return ally_codes

def get_player_gp_from_roster(roster):

	total, char, ship = 0, 0, 0

	for unit in roster:

		gp = unit['gp']

		total += gp

		if unit['combatType'] is 1:
			char += gp

		if unit['combatType'] is 2:
			ship += gp

	return total, char, ship

def get_unit_name(config, base_id, language):

	import DJANGO
	from swgoh.models import Translation

	try:
		t = Translation.objects.get(string_id=base_id, language=language)
		return t.translation

	except Translation.DoesNotExist:
		pass

	print('No character name found for base id: %s' % base_id)
	return None

def get_ability_name(config, skill_id, language):

	import DJANGO
	from swgoh.models import Translation

	if skill_id in config['skills']:
		ability_id = config['skills'][skill_id]['abilityReference']
		try:
			t = Translation.objects.get(string_id=ability_id, language=language)
			return t.translation

		except Translation.DoesNotExist:
			pass

	print('No ability name found for skill id: %s' % skill_id)
	return None
