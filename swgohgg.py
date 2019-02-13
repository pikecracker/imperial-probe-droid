#!/usr/bin/python3

from utils import cache_expired, ensure_parents

import os
import json
import requests

db = {}

SWGOH_GG_API_URL = 'https://swgoh.gg/api'

META_UNITS_URL = 'https://swgoh.gg/meta-report/'
META_SHIPS_URL = 'https://swgoh.gg/fleet-meta-report/'
META_MODS_URL = 'https://swgoh.gg/mod-meta-report/'
META_ZETAS_URL = 'https://swgoh.gg/ability-report/'

def get_unit_list(key, url):

	cache = 'cache/%s.json' % key
	ensure_parents(cache)

	if key in db:
		return db[key]

	elif os.path.exists(cache) and os.path.getsize(cache) > 0 and not cache_expired(cache):
		fin = open(cache, 'r')
		data = fin.read()
		fin.close()
		unit_list = json.loads(data)

	else:
		unit_list = requests.get(url).json()
		fout = open(cache, 'w+')
		fout.write(json.dumps(unit_list))
		fout.close()

	db[key] = unit_list
	return unit_list

def get_char_list():
	return get_unit_list('chars', '%s/characters/' % SWGOH_GG_API_URL)

def get_ship_list():
	return get_unit_list('ships', '%s/ships/' % SWGOH_GG_API_URL)

def get_avatar_url(base_id):

	chars = get_char_list()

	image_url = chars[base_id]['image']
	if image_url.startswith('//'):
		image_url = image_url.replace('//', '')

	if not image_url.startswith('https://'):
		image_url = 'https://%s' % image_url

	chars[base_id]['image'] = image_url
	return image_url

def get_full_avatar_url(ally_code, base_id):

	chars = get_all_chars()
	unit = chars[base_id]
	image_name = os.path.basename(unit['image'])
	unit = get_my_unit_by_id(ally_code, base_id)

	level = 'level' in unit and unit['level'] or 1
	gear = 'gear_level' in unit and unit['gear_level'] or 1
	stars = 'rarity' in unit and unit['rarity'] or 0
	zetas = 'zeta_abilities' in unit and len(unit['zeta_abilities']) or 0

	return 'http://%s/avatar/%s?level=%s&gear=%s&rarity=%s&zetas=%s' % (socket.gethostname(), image_name, level, gear, stars, zetas)

#
# Meta Reports
#

def get_top_rank1_leaders(top_n, html_id, url):

	top_leaders = []

	response = requests.get(url)
	soup = BeautifulSoup(response.text, 'lxml')
	trs = soup.select('li#%s tr' % html_id)

	i = 1
	for tr in trs:

		if i > top_n:
			break

		tds = tr.find_all('td')
		if not tds:
			continue

		unit = tds[0].text.strip()
		count = tds[1].text.strip()
		stat = tds[2].text.strip()

		top_leaders.append((unit, count, stat))

		i += 1

	return top_leaders

def get_top_rank1_squads(top_n, html_id, url):

	top_squads = []

	response = requests.get(url)
	soup = BeautifulSoup(response.text, 'lxml')
	trs = soup.select('li#%s tr' % html_id)

	i = 1
	for tr in trs:

		if i > top_n:
			break

		tds = tr.find_all('td')
		if not tds:
			continue

		squad = tds[0]
		count = tds[1].text.strip()
		percent = tds[2].text.strip()

		imgs = squad.find_all('img', alt=True)
		squad = []
		for img in imgs:
			squad.append(img['alt'])

		top_squads.append((squad, count, percent))

		i += 1

	return top_squads

def get_top_rank1_squad_leaders(top_n):
	return get_top_rank1_leaders(top_n, 'leaders', META_UNITS_URL)

def get_top_rank1_fleet_commanders(top_n):
	return get_top_rank1_leaders(top_n, 'leaders', META_SHIPS_URL)

def get_top_rank1_arena_squads(top_n):
	return get_top_rank1_squads(top_n, 'squads', META_UNITS_URL)

def get_top_rank1_fleet_squads(top_n):
	return get_top_rank1_squads(top_n, 'squads', META_SHIPS_URL)

def get_top_rank1_reinforcements(top_n):
	return get_top_rank1_squads(top_n, 'reinforcements', META_SHIPS_URL)