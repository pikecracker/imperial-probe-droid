import os, sys, json, requests

DEFAULT_ROLE = 'IPD Admin'

class Config(dict):
	pass

config = Config()

def get_root_dir():
	this_file = os.path.realpath(__file__)
	this_folder = os.path.dirname(this_file)
	return this_folder

def get_perms():

	import discord

	perms = discord.Permissions()

	perms.manage_webhooks = True
	perms.read_messages = True
	perms.send_messages = True
	perms.embed_links = True
	perms.attach_files = True
	perms.read_message_history = True
	perms.external_emojis = True
	perms.add_reactions = True

	return perms.value

def load_help():

	help_msgs = {}
	from commands import COMMANDS
	for cmd in COMMANDS:
		for alias in cmd['aliases']:
			help_msgs[alias] = cmd['help']

	config['help'] = help_msgs

def write_config_to_file(config, config_file):

	data = json.dumps(config, indent=4)
	backup = '%s.bak' % config_file
	os.rename(config_file, backup)
	fin = open(config_file, 'w')
	fin.write(data)
	fin.close()

	os.remove(backup)

def parse_mod_primaries(filename='cache/mod-primaries.json'):

	root = get_root_dir()
	filename = '%s/%s' % (root, filename)
	fin = open(filename, 'r')
	data = fin.read()
	fin.close()
	data = json.loads(data)
	config['mod-primaries'] = { int(x): data[x] for x in data }

def count_recos_per_source(source, recos):

	count = 0
	for reco in recos:
		if reco['source'] == source:
			count += 1

	return count

def extract_modstats(stats, recos):

	for reco in recos:

		source = reco['source']
		count = count_recos_per_source(source, recos)

		for slot in [ 'square', 'arrow', 'diamond', 'triangle', 'circle', 'cross' ]:

			primary = reco[slot]

			if slot not in stats:
				stats[slot] = {}

			if primary not in stats[slot]:
				stats[slot][primary] = {}

			if source not in stats[slot][primary]:
				stats[slot][primary][source] = 0.0
			stats[slot][primary][source] += 1.0 / count

def parse_json(filename):
	filepath = os.path.join('cache', filename)
	if not os.path.exists(filepath):
		return []

	fin = open(filepath, 'r')
	data = fin.read()
	fin.close()
	return json.loads(data)

def save_config(config_file='config.json'):

	config_cpy = dict(config)

	to_remove = [
		'abilities',
		'allies',
		'bot',
		'help',
		'mod-primaries',
		'redis',
		'recos',
		'save',
		'separator',
		'skills',
		'stats',
	]

	for key in to_remove:
		if key in config_cpy:
			del config_cpy[key]

	if 'swgoh.help' in config_cpy:
		for key in [ 'access_token', 'access_token_expire' ]:
			if key in config_cpy['swgoh.help']:
				del config_cpy['swgoh.help'][key]

	write_config_to_file(config_cpy, config_file)

def dprint(message):
	if config and 'debug' in config and config['debug'] is True:
		print('DEBUG: %s' % message, file=sys.stderr)

def load_config(config_file='config.json'):

	if not config:

		config_path = '%s/%s' % (get_root_dir(), config_file)
		fin = open(config_path, 'r')
		jsonstr = fin.read()
		fin.close()
		config.update(json.loads(jsonstr))
		parse_mod_primaries()

		config['save'] = save_config
		config['separator'] = '`%s`' % ('-' * 27)
		config['debug'] = 'debug' in config and config['debug']
		config['role'] = DEFAULT_ROLE

		import redis
		config.redis = redis.Redis()

	return config

def setup_logs(facility, filename, level=None):

	import logging
	logger = logging.getLogger(facility)
	logger.setLevel(level is not None and level or logging.DEBUG)
	handler = logging.FileHandler(filename=filename, encoding='utf-8', mode='a')
	handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
	logger.addHandler(handler)
	return logger
