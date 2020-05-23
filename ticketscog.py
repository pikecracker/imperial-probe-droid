#!/usr/bin/env python3

import pytz
import json
import traceback
from datetime import datetime
from discord import Embed
from discord.ext import commands, tasks

from opts import *
from errors import *

import DJANGO
from django.db import transaction
from swgoh.models import Player, PlayerConfig, PlayerActivity

class TicketsCog(commands.Cog):

	max_raid_tickets = 600
	max_guild_tokens = 10000

	def __init__(self, bot):
		self.bot = bot
		self.config = bot.config
		self.logger = bot.logger
		self.redis = bot.redis
		self.raid_tickets_notifier.start()

	def cog_unload(self):
		self.raid_tickets_notifier.cancel()

	def get_lpad_tickets(self, tickets):

		spaces = 0

		if tickets < 10:
			spaces = 2

		elif tickets < 100:
			spaces = 1

		return ' ' * spaces

	def get_lpad_tokens(self, tokens):

		spaces = 0

		if tokens < 10:
			spaces = 3

		elif tokens < 100:
			spaces = 2

		elif tokens < 1000:
			spaces = 1

		return ' ' * spaces

	def get_raid_tickets_config(self):
		return PlayerConfig.objects.filter(key=PlayerConfig.CONFIG_NOTIFY_RAID_TICKETS)

	def get_guild_tokens_config(self):
		return PlayerConfig.objects.filter(key=PlayerConfig.CONFIG_NOTIFY_GUILD_TOKENS)

	def get_discord_id(self, player_id):

		try:
			player = Player.objects.get(player_id=player_id)
			return '<@!%s>' % player.discord_id

		except Player.DoesNotExist:
			return None

	def store_player_activity(self, player_id, timestamp, raid_tickets, guild_tokens):

		try:
			player = Player.objects.get(player_id=player_id)

		except Player.DoesNotExist:
			print('Missing player ID from database: %s' % player_id)
			return None

		defaults = { 'raid_tickets': raid_tickets, 'guild_tokens': guild_tokens }

		return PlayerActivity.objects.update_or_create(player=player, timestamp=timestamp, defaults=defaults)

	async def get_guild_activity(self, creds_id=None, notify=False, store=False):

		activities = []

		total_guild_tokens = 0
		total_raid_tickets = 0
		guild = await self.bot.client.guild(creds_id=creds_id, full=True)

		guild_activity = {
			'name': guild['name'],
			'banner': guild['bannerLogo'],
			'colors': guild['bannerColor'],
			'total': {},
			'guild-tokens': {},
			'raid-tickets': {},
		}

		for member, profile in zip(guild['roster'], guild['members']):

			player_id = profile['id']
			discord_id = profile['name']

			if notify is True:
				discord_id = self.get_discord_id(player_id) or profile['name']

			stat_gt = member['activities'][1] # Guild Tokens stats
			stat_rt = member['activities'][2] # Raid Tickets stats

			guild_tokens = 'valueDaily' in stat_gt and stat_gt['valueDaily'] or 0
			raid_tickets = 'valueDaily' in stat_rt and stat_rt['valueDaily'] or 0

			total_guild_tokens += guild_tokens
			total_raid_tickets += raid_tickets

			guild_activity['guild-tokens'][discord_id] = guild_tokens
			guild_activity['raid-tickets'][discord_id] = raid_tickets

			if store is True:
				activity_reset = pytz.utc.localize(datetime.fromtimestamp(int(guild['activityReset'])))
				activity, created = self.store_player_activity(player_id, activity_reset, raid_tickets, guild_tokens)
				if activity is None:
					print('ERROR: Could not store player activity for %s (%s, %s)' % (player_id, raid_tickets, guild_tokens))
				else:
					activities.append(activity)

		guild_activity['total']['guild-tokens'] = total_guild_tokens
		guild_activity['total']['raid-tickets'] = total_raid_tickets

		if store is True and activities:
			with transaction.atomic():
				for activity in activities:
					activity.save()

		return guild_activity

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):

		if isinstance(error, commands.CommandNotFound):
			return

		raise error

	@tasks.loop(minutes=1)
	async def raid_tickets_notifier(self, min_tickets: int = 600):

		try:
			now = datetime.now()

			alerts = self.get_raid_tickets_config()
			for alert in alerts:

				notif_time = datetime.strptime(alert.value, '%H:%M')
				creds_id = alert.player.creds_id

				hour_ok = now.hour == notif_time.hour
				minute_ok = now.minute == notif_time.minute
				if hour_ok and minute_ok:

					lines = []
					guild_activity = await self.get_guild_activity(creds_id=creds_id, notify=alert.notify, store=alert.store)
					raid_tickets = guild_activity['raid-tickets']

					for name, tickets in sorted(raid_tickets.items(), key=lambda x: x[1], reverse=True):
						if tickets < min_tickets:
							pad = self.get_lpad_tickets(tickets)
							lines.append('`| %s%d/%d |` **%s**' % (pad, tickets, min_tickets, name))

					channel = self.bot.get_channel(alert.channel_id)
					await channel.send('\n'.join(lines))

		except Exception as err:
			print(err)
			print(traceback.format_exc())
			self.logger.error(err)
			self.logger.error(traceback.format_exc())

	@tasks.loop(minutes=1)
	async def guild_tokens_notifier(self, min_tokens: int = 10000):

		now = datetime.now()

		alerts = self.get_guild_tokens_config()
		for alert in alerts:

			notif_time = datetime.strptime(alert.value, '%H:%M')
			creds_id = alert.player.creds_id

			hour_ok = now.hour == notif_time.hour
			minute_ok = now.minute == notif_time.minute
			if hour_ok and minute_ok:

				lines = []
				guild_activity = await self.get_guild_activity(creds_id=creds_id, notify=alert.notify, store=alert.store)
				guild_tokens = guild_activity['guild-tokens']

				for name, tokens in sorted(guild_tokens.items(), key=lambda x: x[1], reverse=True):
					if tickets != self.max_raid_tickets:
						lines.append('`| %s%d/%d |` **%s**' % (pad, tickets, min_tickets, name))

				channel = self.bot.get_channel(alert.channel_id)
				await channel.send('\n'.join(lines))

	@commands.command(aliases=['ticket', 'tickets'])
	async def rtc(self, ctx, *, args: str = ''):

		MAX_TICKETS = 600

		notify = False
		store = False
		min_tickets = MAX_TICKETS

		args = [ x.lower() for x in args.split(' ') ]
		for arg in args:

			if arg in [ 'alert', 'alerts', 'mention', 'mentions', 'notify', 'notification', 'notifications' ]:
				notify = True

			elif arg in [ 'save', 'store' ]:
				store = True

			else:
				try:
					min_tickets = int(arg)
				except:
					pass

		if min_tickets > self.max_raid_tickets:
			min_tickets = self.max_raid_tickets

		premium_user = parse_opts_premium_user(ctx.author)
		if not premium_user:
			return error_not_premium()

		lines = []
		guild_activity = await self.get_guild_activity(creds_id=premium_user.creds_id, notify=notify, store=store)
		guild_name = guild_activity['name']
		guild_banner = guild_activity['banner']
		guild_colors = guild_activity['colors']
		raid_tickets = guild_activity['raid-tickets']
		for name, tickets in sorted(raid_tickets.items(), key=lambda x: x[1], reverse=True):
			if tickets < min_tickets :
				pad = self.get_lpad_tickets(tickets)
				lines.append('`| %s%d/%d |` **%s**' % (pad, tickets, min_tickets, name))

		if not lines:
			lines.append('Everyone got their raid tickets done (%d/%d)! Congratulations! 🥳' % (min_tickets, self.max_raid_tickets))
		else:
			sep = self.config['separator']
			lines = [ sep ] + lines + [ sep ]

		description = '\n'.join(lines)
		icon_url = 'https://swgoh.gg/static/img/assets/tex.%s.png' % guild_banner

		embed = Embed(title='Raid Ticket Check', description=description)
		embed.set_author(name=guild_name, icon_url=icon_url)
		await ctx.send(embed=embed)

	@commands.command(aliases=['gtc'])
	async def guild_tokens_check(self, ctx, min_tokens: int = 10000, *, command=''):

		if min_tokens > self.max_guild_tokens:
			min_tokens = self.max_guild_tokens

		premium_user = parse_opts_premium_user(ctx.author)
		if not premium_user:
			return error_not_premium()

		notify = command.lower() in [ 'alert', 'mention', 'notify', 'notification' ]

		lines = []
		guild_activity = await self.get_guild_activity(creds_id=premium_user.creds_id, notify=notify)
		guild_tokens = guild_activity['guild-tokens']
		for name, tokens in sorted(guild_tokens.items(), key=lambda x: x[1], reverse=True):
			if tokens < min_tokens:
				pad = self.get_lpad_tokens(tokens)
				lines.append('`| %s%d/%d |` **%s**' % (pad, tokens, min_tokens, name))

		if not lines:
			lines.append('Everyone got their guild tokens done (%d/%d)! Contratulations! 🥳' % (min_tokens, self.max_guild_tokens))
		else:
			sep = self.config['separator']
			lines = [ sep ] + lines + [ sep ]

		await ctx.send('\n'.join(lines))
