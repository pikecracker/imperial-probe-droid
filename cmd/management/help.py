#!/usr/bin/python3

from errors import *

help_help = {
	'title': 'Imperial Probe Droid Help - Prefix: %prefix',
	'description': """**Botmaster(s)**: %authors
**Source Code**: %source
**Need support?**: Join us on [Discord](%discord)!
**Like this bot?**: Support us on [Patreon](%patreon)!
%separator
**Help Commands**
**`help`**: This help menu.
**`help command`**: Get help menu for command.
%separator
**Management Commands**
**`alias`**: Manage command aliases.
**`format`**: Manage output formats.
**`invite`**: Invite this bot.
**`links`**: Manage URL list.
**`nicks`**: Manage nicknames for units and ships.
%separator
**Guild Commands**
**`gc`**: Compare different guilds and their respective units.
%separator
**Player Commands**
**`arena`**: Show arena squads details.
**`gear`**: List needed pieces of gear for units.
**`locked`**: Show locked characters or ships.
**`meta`**: Show information about best arena and fleet squads.
**`needed`**: Show information about needed modsets globally.
**`pc`**: Compare different players and their respective units.
**`recos`**: Show information about recommended mods.
**`wntm`**: List characters who needs mods with specific criteria."""
#NOT WORKING **`mods`**: Show information about mods.
#NOT WORKING **`stats`**: Show statistics about equipped mods."""
}

def substitute_tokens(config, text):

	tokens = [
		'authors',
		'discord',
		'patreon',
		'prefix',
		'separator',
		'source',
	]

	for token in tokens:

		value = config[token]
		if token == 'source':
			value = '[Github](%s)' % value

		if type(value) is list:
			value = ', '.join(value)

		text = text.replace('%' + token, value)

	return text

def cmd_help(config, author, channel, args):

	msg = help_help

	if args:
		command = args[0].lower()
		if command in config['help']:
			msg = config['help'][command]
		else:
			return error_no_such_command(command)

	return [{
		'title':       substitute_tokens(config, msg['title']),
		'description': substitute_tokens(config, msg['description']),
	}]
