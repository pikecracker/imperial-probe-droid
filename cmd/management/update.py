#!/usr/bin/python3

from errors import *

help_update = {
	'title': 'Update Help',
	'description': """Update the source code and restart this bot.
	
**Syntax**
```
%prefixupdate```
**Aliases**
```
%prefixU```
**Restrictions**
Only administrators of this bot can use this command.

**Examples**
Update the bot:
```
%prefixu```"""
}

def cmd_update(config, author, channel, args):

	if 'admins' in config and author in config['admins']:
		from utils import exit_bot, update_source_code
		update_source_code()
		exit_bot()
		return []

	return error_permission_denied()
