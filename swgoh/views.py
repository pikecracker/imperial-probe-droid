import pytz
import math
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
import django.views.generic as generic_views
from django.views.generic.detail import DetailView
from django.views.generic.edit import UpdateView
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponse, HttpResponseServerError, Http404, JsonResponse

from django_redis import get_redis_connection

from PIL import Image, ImageDraw, ImageFont, ImageOps

from cairosvg import svg2png

import io
import os
import csv
import json
import redis
import requests
from datetime import datetime, timedelta

from .models import Gear, BaseUnit, BaseUnitSkill, Player, PlayerActivity, User

redis_cli = get_redis_connection("default")

def index(request):

	ctx = {}

	ctx['demo_url'] = 'https://zeroday.biz/guild/'
	ctx['github_url'] = 'https://github.com/quarantin/imperial-probe-droid'
	ctx['patreon_url'] = 'https://www.patreon.com/imperial_probe_droid'
	ctx['image_path'] = '/media/ipd-coming-soon.gif'

	return render(request, 'swgoh/index.html', ctx)

def dashboard(request):

	ctx = {}
	return render(request, 'swgoh/dashboard.html', ctx)

class UserDetailView(DetailView):

	model = User

	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		return context

	def get(self, request, *args, **kwargs):

		self.object = request.user

		context = self.get_context_data(*args, **kwargs)

		return self.render_to_response(context)

class PlayerUpdateView(UpdateView):

	model = Player
	fields = [ 'ally_code', 'language', 'timezone' ]
	template_name_suffix = '_update_form'
	success_url = '/settings/'

	def get_object(self):
		user = get_object_or_404(User, pk=self.request.user.id)
		return user.player

	def get_success_url(self):
		messages.success(self.request, 'Settings updated successfully.')
		return self.success_url

def guild(request):
	ctx = {}
	return render(request, 'swgoh/guild.html', ctx)

def get_player(request):

	user = request.user
	if not user.is_authenticated:
		user = User.objects.get(id=2)

	try:
		return Player.objects.get(user=user)

	except Player.DoesNotExist:
		return None

def guild_tickets_guild_daily_json(request):

	player = get_player(request)
	guild = redis_cli.get('guild|%s' % player.guild.guild_id)
	if not guild:
		return HttpResponseServerError('Something went wrong! Please notify the developer about this.')

	player_ids = []
	guild = json.loads(guild.decode('utf-8'))
	for member in guild['roster']:
		player_id = member['playerId']
		if player_id not in player_ids:
			player_ids.append(player_id)

	players = Player.objects.filter(player_id__in=player_ids).values()
	db = { x['id']: x for x in players }

	pids = [ x.id for x in Player.objects.filter(player_id__in=player_ids) ]
	players = list(PlayerActivity.objects.filter(player_id__in=pids).values('player_id', 'raid_tickets', 'timestamp'))
	for player in players:
		pid = player.pop('player_id')
		player['id'] = db[pid]['player_id']
		player['name'] = db[pid]['player_name']

	store = {}
	for player in players:

		timestamp = player['timestamp'].strftime('%Y-%m-%d')
		if timestamp not in store:
			store[timestamp] = 0
		store[timestamp] += player['raid_tickets']

	events = []
	for timestamp, tickets in store.items():
		events.append({
			'label': timestamp,
			'value': tickets,
		})

	return JsonResponse({ 'events': events })

def guild_tickets_guild_daily(request):
	context = {}
	context['guild_active'] = True
	context['guild_tickets_guild_daily'] = True
	return render(request, 'swgoh/guild-tickets-guild-daily.html', context)

def guild_tickets_total_per_user_json(request):

	player = get_player(request)
	guild = redis_cli.get('guild|%s' % player.guild.guild_id)
	if not guild:
		return HttpResponseServerError('Something went wrong! Please notify the developer about this.')

	player_ids = []
	guild = json.loads(guild.decode('utf-8'))
	for member in guild['roster']:
		player_id = member['playerId']
		if player_id not in player_ids:
			player_ids.append(player_id)

	players = Player.objects.filter(player_id__in=player_ids).values()
	db = { x['id']: x for x in players }

	pids = [ x.id for x in Player.objects.filter(player_id__in=player_ids) ]
	players = list(PlayerActivity.objects.filter(player_id__in=pids).values('player_id', 'raid_tickets', 'timestamp'))
	for player in players:
		pid = player.pop('player_id')
		player['id'] = db[pid]['player_id']
		player['name'] = db[pid]['player_name']

	store = {}
	for player in players:

		player_name = player['name']
		if player_name not in store:
			store[player_name] = 0
		store[player_name] += player['raid_tickets']

	events = []
	for player, tickets in sorted(store.items(), key=lambda x: x[1]):
		events.append({
			'label': player,
			'value': tickets,
		});

	return JsonResponse({ 'events': events })

def guild_tickets_total_per_user(request):
	context = {}
	context['guild_active'] = True
	context['guild_tickets_total_per_user'] = True
	return render(request, 'swgoh/guild-tickets-total-per-user.html', context)

def guild_tickets_detail_json(request):

	player = get_player(request)
	guild = redis_cli.get('guild|%s' % player.guild.guild_id)
	if not guild:
		return HttpResponseServerError('Something went wrong! Please notify the developer about this.')

	player_ids = []
	guild = json.loads(guild.decode('utf-8'))
	for member in guild['roster']:
		player_ids.append(member['playerId'])
	players = Player.objects.filter(player_id__in=player_ids)

	player_list = {}
	for player in players:
		player_list[player.player_id] = player.player_name

	player_id = request.GET.get('player')
	if not player_id:
		return JsonResponse({})

	player = get_object_or_404(Player, player_id=player_id)

	for member in guild['roster']:
		if member['playerId'] == player_id:
			break
	else:
		raise PermissionDenied()

	events = []
	activity = PlayerActivity.objects.filter(player_id=player.id).values('raid_tickets', 'timestamp')
	for entry in activity:
		timestamp = entry['timestamp'].strftime('%Y-%m-%d')
		events.append({
			'label': timestamp,
			'value': entry['raid_tickets'],
		})

	return JsonResponse({ 'events': events })

def guild_tickets_detail(request):

	player = get_player(request)
	guild = redis_cli.get('guild|%s' % player.guild.guild_id)
	if not guild:
		return HttpResponseServerError('Something went wrong! Please notify the developer about this.')

	player_ids = []
	guild = json.loads(guild.decode('utf-8'))
	for member in guild['roster']:
		player_ids.append(member['playerId'])
	players = Player.objects.filter(player_id__in=player_ids)

	player_list = {}
	for player in players:
		player_list[player.player_id] = player.player_name

	timezones = pytz.common_timezones
	if 'UTC' in timezones:
		timezones.remove('UTC')
	timezones.insert(0, 'UTC')

	context = {
		'players': player_list,
		'timezones': { x: x for x in timezones },
		'guild_active': True,
		'guild_tickets_detail': True,
	}

	timezone = request.GET.get('timezone')
	if timezone:
		context['timezone'] = timezone

	player_id = request.GET.get('player')
	if player_id:
		context['player'] = player_id

	return render(request, 'swgoh/guild-tickets-detail.html', context)

def file_content(path):
	fin = open(path, 'rb')
	data = fin.read()
	fin.close()
	return data

background_colors = {
	 1: ( 67, 145, 163),
	 2: ( 76, 150,   1),
	 4: (  0,  75, 101),
	 7: ( 71,   0, 167),
	 9: ( 71,   0, 167),
	11: ( 71,   0, 167),
	12: (153, 115,   0),
}

def get_gear_background(gear, size):

	width, height = size
	image = Image.new('RGBA', (width, height))
	center = background_colors[gear.tier]
	border = (0, 0, 0)

	for y in range(height):
		for x in range(width):
			distanceToCenter = math.sqrt((x - width / 2) ** 2 + (y - height / 2) ** 2)
			distanceToCenter = float(distanceToCenter) / (math.sqrt(2) * width / 2)
			r = int(border[0] * distanceToCenter + center[0] * (1 - distanceToCenter))
			g = int(border[1] * distanceToCenter + center[1] * (1 - distanceToCenter))
			b = int(border[2] * distanceToCenter + center[2] * (1 - distanceToCenter))

			image.putpixel((x, y), (r, g, b))

	return image

def crop_corners(image):

	image_size = 128

	triangle_1_size = 15
	triangle_1 = [
		(0, 0),
		(0, triangle_1_size),
		(triangle_1_size, 0),
	]

	triangle_2_size = 16
	triangle_2 = [
		(image_size, image_size),
		(image_size, image_size - triangle_2_size),
		(image_size - triangle_2_size, image_size),
	]

	triangle_3_size = 8
	triangle_3 = [
		(0, image_size),
		(0, image_size - triangle_3_size),
		(triangle_3_size, image_size),
	]

	draw = ImageDraw.Draw(image)

	draw.polygon(triangle_1, fill=255)
	draw.polygon(triangle_2, fill=255)
	draw.polygon(triangle_3, fill=255)

	return image

def download_gear(gear):

	image_path = 'images/equip-%s.png' % gear.base_id

	if not os.path.exists(image_path):

		url = 'https://swgoh.gg%s' % gear.image

		response = requests.get(url)
		response.raise_for_status()

		fout = open(image_path, 'wb')
		fout.write(response.content)
		fout.close()

	return image_path

def download_skill(skill):

	image_path = 'images/skill.%s.png' % skill.skill_id

	if not os.path.exists(image_path):

		url = 'https://swgoh.gg/game-asset/a/%s/' % skill.skill_id

		response = requests.get(url)
		response.raise_for_status()

		fout = open(image_path, 'wb')
		fout.write(response.content)
		fout.close()

	return image_path

def get_gear_portrait(gear):

	final_path = 'images/equip-%s-tier-%02d.png' % (gear.base_id, gear.tier)
	if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
		return file_content(final_path)

	gear_path = download_gear(gear)
	gear_image = Image.open(gear_path)

	border_path = 'images/border-tier-%02d.png' % gear.tier
	border_image = Image.open(border_path)

	image = get_gear_background(gear, gear_image.size)
	image.paste(gear_image, (0, 0), gear_image)
	image.paste(border_image, (0, 0), border_image)

	crop_corners(image).save(final_path)
	return file_content(final_path)

def gear(request, base_id):

	try:
		gear = Gear.objects.get(base_id=base_id)
		image = get_gear_portrait(gear)
		return HttpResponse(image, content_type='image/png')

	except Gear.DoesNotExist:
		raise Http404('Could not find gear: %s' % base_id)

def relic(request, relic, align):

	image = get_relic(relic, align, raw=True)
	return HttpResponse(image, content_type='image/png')

def skill(request, skill_id):

	try:
		skill = BaseUnitSkill.objects.get(skill_id=skill_id)
		skill_path = download_skill(skill)
		image = file_content(skill_path)
		return HttpResponse(image, content_type='image/png')

	except BaseUnitSkill.DoesNotExist:
		raise Http404('Could not find skill: %s' % skill_id)

def login_success(request):

	google_code = 'No access token specified.'

	if request.method == 'GET':

		google_code = 'No access token specified (GET).'
		if 'code' in request.GET:
			google_code = request.GET['code']

	return HttpResponse(google_code)

ALIGNMENTS = {
	'dark': True,
	'light': True,
	'neutral': True,
}

def download_image(image_name):

	image_path = './images/%s' % image_name
	if not image_path.endswith('.png'):
		image_path = '%s.png' % image_path

	if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:

		url = 'https://swgoh.gg/game-asset/u/%s/' % image_name

		response = requests.get(url)
		if response.status_code == 404:
			raise Http404('Could not find character: %s' % image_name)

		response.raise_for_status()

		image_data = response.content

		fin = open(image_path, 'wb+')
		fin.write(image_data)
		fin.close()

	return image_path

def get_portrait(character):
	width, height = 256, 256
	image = Image.new('RGBA', (256, 256))
	portrait = Image.open(download_image(character)).convert('RGBA')

	x = int(width / 2 + image.width / 2)
	y = int(height / 2 + image.height / 2)
	image.paste(portrait, (x, y), portrait)
	image.show()
	return image

def get_gear(gear, alignment):

	if gear is None:
		return None

	align = gear >= 13 and '-%s-side' % alignment or ''
	image_name = 'gear-%02d%s.png' % (gear, align)
	image_path = download_image(image_name)
	return Image.open(image_path)

def get_level(level):

	if not level:
		return None

	offset = 0
	if level < 10:
		offset = 5

	image_name = 'level.png'
	image_path = download_image(image_name)

	level_image = Image.open(image_path)
	draw = ImageDraw.Draw(level_image)
	font = ImageFont.truetype('fonts/arial.ttf', 24)
	draw.text((51 + offset, 93), "%d" % level, (255, 255, 255), font=font)
	return level_image

def get_rarity(rarity):

	if rarity is None:
		return None

	star_image_name = 'star.png'
	star_image_path = download_image(star_image_name)

	no_star_image_name = 'star-inactive.png'
	no_star_image_path = download_image(no_star_image_name)

	star_img = Image.open(star_image_path)
	no_star_img = Image.open(no_star_image_path)

	rarity_img = Image.new('RGBA', (star_img.width * 7, star_img.height), 0)

	for i in range(0, rarity):
		rarity_img.paste(star_img, (i * 17, 0), star_img)

	for i in range(rarity, 7):
		rarity_img.paste(no_star_img, (i * 17, 0), no_star_img)

	return rarity_img

def get_zetas(zetas):

	image_name = 'zeta-48x48.png'
	image_path = download_image(image_name)

	zeta_image = Image.open(image_path)
	draw = ImageDraw.Draw(zeta_image)
	font = ImageFont.truetype('fonts/arialbd.ttf', 14)
	draw.text((20, 12), '%d' % zetas, (255, 255, 255), font=font)
	return zeta_image

def get_relic(relic, alignment, raw=False):

	final_path = 'images/relic-%s-side-%d.png' % (alignment, relic)
	if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
		return raw is False and Image.open(final_path) or file_content(final_path)

	image_name = 'relic-%s-side.png' % alignment
	image_path = download_image(image_name)

	relic_image = Image.open(image_path)
	draw = ImageDraw.Draw(relic_image)
	font = ImageFont.truetype('fonts/arialbd.ttf', 14)

	x = 23
	y = 19

	draw.text((x + 1, y + 1), '%d' % relic, font=font, fill='black')
	draw.text((x + 2, y + 1), '%d' % relic, font=font, fill='black')
	draw.text((x, y), '%d' % relic, font=font, fill='white')

	relic_image.save(final_path)
	return raw is False and relic_image or file_content(final_path)

def format_image(image, radius):
	size = (radius, radius)
	mask = Image.new('L', size, 0)
	draw = ImageDraw.Draw(mask)
	draw.ellipse((0, 0) + size, fill=255)
	data = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
	data.putalpha(mask)
	return data

def get_param(request, param, default=0):

	try:
		return param in request.GET and request.GET[param] and type(default)(request.GET[param]) or default
	except:
		return default

def has_params(request):
	for param in [ 'level', 'gear', 'rarity', 'zetas', 'relic' ]:
		if param in request.GET and int(request.GET[param]):
			return True
	return False

def get_avatar(request, base_id):

	alignment = get_param(request, 'alignment', 'neutral').lower()
	gear      = get_param(request, 'gear')
	level     = get_param(request, 'level')
	rarity    = get_param(request, 'rarity')
	zeta      = get_param(request, 'zetas')
	relic     = get_param(request, 'relic')

	gear_str   = 'G%d' % gear
	level_str  = 'L%d' % level
	rarity_str = 'S%d' % rarity
	zeta_str   = 'Z%d' % zeta
	relic_str  = 'R%d' % relic

	filename = './images/%s.png' % '_'.join([ base_id, alignment, gear_str, level_str, rarity_str, zeta_str, relic_str ])
	if os.path.exists(filename):
		return filename, Image.open(filename)

	width, height = 256, 256
	size = (width, height)
	radius = int(width / 4)
	image = Image.new('RGBA', (width, height))

	portrait_path = download_image(base_id)
	portrait = Image.open(portrait_path).convert('RGBA')
	portrait.thumbnail((128, 128), Image.ANTIALIAS)

	portrait_x = int(image.width  / 2 - portrait.width  / 2)
	portrait_y = int(image.height / 2 - portrait.height / 2)

	image.paste(portrait, (portrait_x, portrait_y), portrait)

	if has_params(request):
		mask = Image.new('L', size, 0)
		draw = ImageDraw.Draw(mask)
		circle = [ (radius, radius), (radius * 3, radius * 3) ]
		draw.ellipse(circle, fill=255)

		image = ImageOps.fit(image, size)
		image.putalpha(mask)

	if alignment not in ALIGNMENTS:
		alignment = 'neutral'

	if gear > 0:
		gear_image   = get_gear(gear, alignment)
		gear_x = int(image.width  / 2 - gear_image.width / 2)
		gear_y = int(image.height / 2 - gear_image.height / 2)
		image.paste(gear_image, (gear_x, gear_y), gear_image)

	if level > 0:
		level_image  = get_level(level)
		level_x = int(image.width / 2 - level_image.width / 2)
		level_y = int(image.height / 2 - level_image.height / 2 + 10)
		image.paste(level_image, (level_x, level_y), level_image)

	if rarity > 0:
		rarity_image = get_rarity(rarity)
		rarity_x = int(image.width / 2 - portrait.width / 2 + rarity_image.height / 4)
		rarity_y = int(image.height / 2 - portrait.height / 2 - rarity_image.height)
		image.paste(rarity_image, (rarity_x, rarity_y), rarity_image)

	if zeta > 0:
		zeta_image   = get_zetas(zeta)
		zeta_x = int(image.width / 4 - 10)
		zeta_y = int(image.height / 2 + zeta_image.height / 4 + 5)
		image.paste(zeta_image, (zeta_x, zeta_y), zeta_image)

	if relic > 0:
		relic_image  = get_relic(relic, alignment)
		relic_x = int(image.width / 2 + relic_image.width / 4 + 5)
		relic_y = int(image.height / 2 + relic_image.height / 4 - 3)
		image.paste(relic_image, (relic_x, relic_y), relic_image)

	image = image.crop((radius - 10, radius - 20, radius * 3 + 10, radius * 3 + 10))

	image.save(filename, format='PNG')

	return filename, image

def avatar(request, base_id):
	filename, image = get_avatar(request, base_id)
	return FileResponse(open(filename, 'rb'))

class CsvResponse(HttpResponse):

	def __init__(self, filename='events.csv', rows=[], *args, **kwargs):

		super().__init__(*args, **kwargs)

		self['Content-Type'] = 'text/csv'
		self['Content-Disposition'] = 'attachment; filename="%s"' % filename

		writer = csv.writer(self)
		for row in rows:
			writer.writerow(row)

class TerritoryEventMixin:

	def event2date(self, event, dateformat='%Y/%m/%d'):
		ts = int(str(event).split(':')[1][1:]) / 1000
		return datetime.fromtimestamp(int(ts)).strftime(dateformat)

	def get_activity(self):
		if 'activity' in self.request.GET:
			return int(self.request.GET['activity'])

	def get_activities(self):
		return { x: y for x, y in self.model.ACTIVITY_CHOICES }

	def get_category(self, default):

		category = default

		if 'category' in self.request.GET:
			category = self.request.GET['category']

		return category

	def get_categories(self):
		return { x: y for x, y in self.model.categories }

	def get_event(self):

		if 'event' in self.request.GET:
			id = int(self.request.GET['event'])
			return self.event_model.objects.get(id=id)

		return self.event_model.objects.first()

	def get_events(self):
		return { x.id: '%s - %s' % (self.event2date(x.event_id), x.get_name()) for x in self.event_model.objects.all() }

	def get_phase(self):
		if 'phase' in self.request.GET:
			return int(self.request.GET['phase'])

	def get_phases(self, tb_type):
		return self.model.get_phase_list(tb_type)

	def get_player(self):
		if 'player' in self.request.GET:
			return self.request.GET['player']

	def get_player_list(self, event):

		done = {}
		result = []
		players = list(self.model.objects.filter(event=event).values('player_id', 'player_name').distinct())
		for player in sorted(players, key=lambda x: x['player_name'].lower()):
			id = player['player_id']
			name = player['player_name']
			if id not in done:
				done[id] = True
				result.append((id, name))

		return result

	def get_player_object(self):

		user = self.request.user
		if not user.is_authenticated:
			user = User.objects.get(id=2)

		try:
			return Player.objects.get(user=user)

		except Player.DoesNotExist:
			return None

	def get_preloaded(self):
		if 'preloaded' in self.request.GET:
			return (self.request.GET['preloaded'].lower() == 'yes') and 1 or 0

	def get_target(self):
		if 'target' in self.request.GET:
			return self.request.GET['target']

	def get_territory(self):
		if 'territory' in self.request.GET:
			return self.request.GET['territory']

	def get_territories(self, tb_type=None):
		return self.model.get_territory_list(tb_type=tb_type)

	def get_timezone(self):

		timezone = 'UTC'

		if 'timezone' in self.request.GET:
			timezone = self.request.GET['timezone']

		return timezone

	def get_timezones(self):

		timezones = pytz.common_timezones

		if 'UTC' in timezones:
			timezones.remove('UTC')

		timezones.insert(0, 'UTC')

		return { x: x for x in timezones }

	def get_categories(self):
		return { x: y for x, y in self.model.categories }

	def convert_date(self, utc_date, timezone):
		local_tz = pytz.timezone(timezone)
		local_dt = utc_date.astimezone(local_tz)
		return local_tz.normalize(local_dt).strftime('%Y-%m-%d %H:%M:%S')

class ListViewCsvMixin(generic_views.ListView):

	def get(self, request, *args, **kwargs):

		self.object_list = self.get_queryset()
		context = self.get_context_data(*args, **kwargs)

		event = context['event']

		rows = []
		rows.append(self.get_headers())

		index = 0
		for o in context['object_list']:
			new_rows = self.get_rows(o, index)
			rows.extend(new_rows)
			index += len(new_rows)

		return CsvResponse(filename=self.get_filename(event), rows=rows)

class GuildTicketsPerUser(generic_views.ListView, TerritoryEventMixin):

	model = PlayerActivity
	queryset = PlayerActivity.objects.all()

	def get_date_filters(self, display='0'):

		display = int(display)
		dt = datetime.now(tz=pytz.utc)

		if display == 1: # Yesterday

			yesterday = (dt - timedelta(days=1))

			begin = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
			end = yesterday.replace(hour=23, minute=23, second=59, microsecond=999999)

		elif display == 2: # This Month

			begin = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
			end = dt.replace(hour=23, minute=23, second=59, microsecond=999999)

		elif display == 3: # Last 30 Days

			begin = (dt - timedelta(days=30))
			end = dt.replace(hour=23, minute=23, second=59, microsecond=999999)

		elif display == 4: # Last Month

			last_month = dt.month == 1 and 12 or dt.month - 1

			begin = dt.replace(month=last_month, day=1, hour=0, minute=0, second=0, microsecond=0)
			end = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)

		elif display == 5: # Average

			begin = datetime(1970, 1, 1, hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.utc)
			end = dt

		else: # Today

			begin = dt.replace(hour=0, minute=0, second=0, microsecond=0)
			end = dt.replace(hour=23, minute=23, second=59, microsecond=999999)

		return begin, end


	def get_context_data(self, *args, **kwargs):

		context = super().get_context_data(*args, **kwargs)

		player = self.get_player_object()
		guild = redis_cli.get('guild|%s' % player.guild.guild_id)
		if not guild:
			print('Guild not found in redis cache!')
			# TODO better handling in case of guild not found
			return context

		guild = json.loads(guild.decode('utf-8'))
		player_ids = [ x['playerId'] for x in guild['roster'] ]
		kwargs['player__player_id__in'] = player_ids

		display = kwargs.pop('display')
		begin, end = self.get_date_filters(display)
		kwargs['timestamp__gte'] = begin
		kwargs['timestamp__lte'] = end

		activity_list = context['object_list'].filter(**kwargs)

		tickets = {}
		for activity in activity_list:
			player_name = activity.player.player_name
			if player_name not in tickets:
				tickets[player_name] = []

			tickets[player_name].append(activity.raid_tickets)

		result = {}
		for player_name, activity_list in tickets.items():
			result[player_name] = sum(activity_list)
			#if display == 5:
			#	result[player_name] /= float(len(activity_list))

		context['tickets'] = sorted(result.items(), key=lambda x: (-x[1], x[0]))
		context['guild_active'] = True
		context['guild_tickets_average'] = True

		context['displays'] = {
			'0': 'Today',
			'1': 'Yesterday',
			'2': 'This Month',
			'3': 'Last 30 Days',
			'4': 'Last Month',
		}

		context['display'] = display

		return context

	def get(self, request, *args, **kwargs):

		self.object_list = self.get_queryset()

		kwargs['display'] = request.GET.get('display', '0');

		context = self.get_context_data(*args, **kwargs)

		return self.render_to_response(context)
