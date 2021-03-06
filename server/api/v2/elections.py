import flask, json, os, re, sys, arrow
from copy import deepcopy
import helpers

def get_elections_by_ocd_ids(ocd_ids, year = '2018'):

	elections = {}
	targeted = helpers.get_targeted()
	blurbs = helpers.get_blurbs()

	if len(ocd_ids) == 0:
		return None

	state = re.search('state:(\w\w)', ocd_ids[0]).group(1)

	cur = flask.g.db.cursor()
	cur.execute('''
		SELECT state, online_reg_url, check_reg_url, polling_place_url,
		       voter_id_req, same_day, vote_by_mail, early_voting,
		       vbm_req_url, voter_id_url, election_info_url, same_day_url
		FROM election_info
		WHERE state = %s
	''', (state,))

	row = cur.fetchone()
	if not row:
		return None

	def url_value(url):
		if url == '':
			return None
		else:
			return url

	elections = {
		'info': {
			'state': row[0],
			'voter_id_req': row[4],
			'same_day': row[5],
			'vote_by_mail': row[6],
			'early_voting': row[7]
		},
		'links': {
			'online_reg_url': url_value(row[1]),
			'check_reg_url': url_value(row[2]),
			'polling_place_url': url_value(row[3]),
			'vbm_req_url': url_value(row[8]),
			'voter_id_url': url_value(row[9]),
			'election_info_url': url_value(row[10]),
			'same_day_url': url_value(row[11])
		},
		'calendar': [],
		'ballots': []
	}

	cur.execute('''
		SELECT name, value
		FROM election_dates
		WHERE state = %s
		ORDER BY value
	''', (state,))

	rs = cur.fetchall()

	primary_index = None
	general_index = None
	primary_runoff_index = None
	general_runoff_index = None

	election_type_lookup = {}

	if rs:
		for row in rs:
			name = row[0]
			date = helpers.format_date(row[1])
			if name.startswith('primary_'):
				name = name.replace('primary_', '')
				type = 'primary'
				if primary_index == None:
					primary_index = len(elections['calendar'])
					elections['calendar'].append({
						'type': type,
						'dates': {}
					})
				elections['calendar'][primary_index]['dates'][name] = date
				election_type_lookup[date] = 'primary'
			elif name.startswith('general_'):
				name = name.replace('general_', '')
				type = 'general'
				if general_index == None:
					general_index = len(elections['calendar'])
					elections['calendar'].append({
						'type': type,
						'dates': {}
					})
				elections['calendar'][general_index]['dates'][name] = date
				election_type_lookup[date] = 'general'
			elif name.startswith('primary_runoff_'):
				name = name.replace('primary_runoff_', '')
				type = 'primary_runoff'
				if primary_runoff_index == None:
					primary_runoff_index = len(elections['calendar'])
					elections['calendar'].append({
						'type': type,
						'dates': {}
					})
				elections['calendar'][primary_runoff_index]['dates'][name] = date
				election_type_lookup[date] = 'primary_runoff'
			elif name.startswith('general_runoff_'):
				name = name.replace('general_runoff_', '')
				type = 'general_runoff'
				if general_runoff_index == None:
					general_runoff_index = len(elections['calendar'])
					elections['calendar'].append({
						'type': type,
						'dates': {}
					})
				elections['calendar'][general_runoff_index]['dates'][name] = date
				election_type_lookup[date] = 'general_runoff'


	# Runoff elections are not ready yet, so we will skip those for now.
	# (20180905/dphiffer)

	election_dates = [
		'primary_date',
		'general_date'
		#'primary_runoff_date',
		#'general_runoff_date'
	]

	ocd_id_list = ', '.join(['%s'] * len(ocd_ids))
	values = tuple(ocd_ids + [year])

	cur.execute('''
		SELECT name, race_type, office_type, office_level,
		       primary_date, primary_runoff_date,
		       general_date, general_runoff_date,
		       ocd_id
		FROM election_races
		WHERE ocd_id IN ({ocd_ids})
		  AND year = %s
	'''.format(ocd_ids=ocd_id_list), values)

	rs = cur.fetchall()
	ballot_lookup = {}
	office_lookup = {}

	offices_template = {
		"federal": [
			{
				"office": "us_senator",
				"blurb": blurbs['us_senator'],
				"races": []
			}, {
				"office": "us_representative",
				"blurb": blurbs['us_representative'],
				"races": []
			}
		],
		"state": [
			{
				"office": "governor",
				"blurb": blurbs['governor'],
				"races": []
			}, {
				"office": "attorney_general",
				"blurb": blurbs['attorney_general'],
				"races": []
			}, {
				"office": "secretary_of_state",
				"blurb": blurbs['secretary_of_state'],
				"races": []
			}, {
				"office": "state_supreme_court",
				"blurb": blurbs['state_supreme_court'],
				"races": []
			}, {
				"office": "state_senator",
				"blurb": blurbs['state_senator'],
				"races": []
			}, {
				"office": "state_representative",
				"blurb": blurbs['state_representative'],
				"races": []
			}
		],
		"county": [
			{
				"office": "district_attorney",
				"blurb": blurbs['district_attorney'],
				"races": []
			}, {
				"office": "county_sheriff",
				"blurb": blurbs['county_sheriff'],
				"races": []
			}
		]
	}

	office_lookup_template = {
		'us_senator': 0,
		'us_representative': 1,
		'governor': 0,
		'attorney_general': 1,
		'secretary_of_state': 2,
		'state_supreme_court': 3,
		'state_senator': 4,
		'state_representative': 5,
		'district_attorney': 0,
		'county_sheriff': 1
	}

	if rs:
		for row in rs:

			office_level = row[3]

			election_date_lookup = {
				'primary_date': row[4],
				'general_date': row[6],
				'primary_runoff_date': row[5],
				'general_runoff_date': row[7]
			}

			for name in election_dates:
				if election_date_lookup[name]:

					date = helpers.format_date(election_date_lookup[name])

					if name in election_date_lookup:
						name = name.replace('_date', '_election_date')

						if not date in ballot_lookup:
							ballot_lookup[date] = len(elections['ballots'])
							elections['ballots'].append({
								'date': date,
								'offices': deepcopy(offices_template),
								'initiatives': []
							})
							office_lookup[date] = deepcopy(office_lookup_template)

						ballot = ballot_lookup[date]

						if not 'type' in elections['ballots'][ballot]:

							if date in election_type_lookup:
								type = election_type_lookup[date]

							else:
								type = row[1]
								if type == 'regular':
									if name == 'primary_election_date':
										type = 'primary'
									elif name == 'general_election_date':
										type = 'general'
									elif name == 'primary_runoff_election_date':
										type = 'primary_runoff'
									elif name == 'general_runoff_election_date':
										type = 'general_runoff'
								elif type == 'special':
									if name == 'primary_election_date':
										type = 'special_primary'
									else:
										type = 'special_general'

							elections['ballots'][ballot]['type'] = type

						office = row[2]

						if not office_level in elections['ballots'][ballot]['offices']:
							elections['ballots'][ballot]['offices'][office_level] = []

						if not office in office_lookup[date]:
							office_lookup[date][office] = len(elections['ballots'][ballot]['offices'][office_level])
							elections['ballots'][ballot]['offices'][office_level].append({
								'office': office,
								'races': []
							})

						office_index = office_lookup[date][office]
						elections['ballots'][ballot]['offices'][office_level][office_index]['ocd_id'] = row[8]

						if office_index <= len(elections['ballots'][ballot]['offices'][office_level]) - 1:
							race = {
								'name': row[0]
							}
							for ocd_id in ocd_ids:
								if ocd_id in targeted['races']:
									for t in targeted['races'][ocd_id]:
										if t['office'] == office:
											race['targeted'] = [t]
							office_obj = elections['ballots'][ballot]['offices'][office_level][office_index]
							office_obj['races'].append(race)

							if 'blurb' in office_obj and 'alt_names' in office_obj['blurb']:
								office_obj['blurb'] = helpers.localize_blurb(office_obj['blurb'], race['name'])
						else:
							print("Warning: could not add %s to %s office %d" % (row[0], office_level, office_index))

				if name.startswith('primary_runoff_'):
					name = name.replace('primary_runoff_', '')
					if primary_runoff_index and primary_runoff_index in elections['calendar']:
						if not name in elections['calendar'][primary_runoff_index]['dates']:
							elections['calendar'][primary_runoff_index]['dates'][name] = date
				elif name.startswith('general_runoff_'):
					name = name.replace('general_runoff_', '')
					if general_runoff_index and general_runoff_index in elections['calendar']:
						if not name in elections['calendar'][general_runoff_index]['dates']:
							elections['calendar'][general_runoff_index]['dates'][name] = date
				elif name.startswith('primary_'):
					name = name.replace('primary_', '')
					if not name in elections['calendar'][primary_index]['dates']:
						elections['calendar'][primary_index]['dates'][name] = date
				elif name.startswith('general_'):
					name = name.replace('general_', '')
					if not name in elections['calendar'][general_index]['dates']:
						elections['calendar'][general_index]['dates'][name] = date

	def filter_offices(office):
		return len(office['races']) > 0

	for ballot in elections['ballots']:
		for office_level in ballot['offices']:
			ballot['offices'][office_level] = filter(filter_offices, ballot['offices'][office_level])

	def sort_ballots(a, b):
		return 1 if a['date'] > b['date'] else -1
	elections['ballots'].sort(cmp=sort_ballots)

	def sort_calendar(a, b):
		return 1 if a['dates']['election_date'] > b['dates']['election_date'] else -1
	elections['calendar'].sort(cmp=sort_calendar)

	for ocd_id in ocd_ids:
		if ocd_id in targeted['initiatives']:
			for ballot in elections['ballots']:
				ballot['initiatives'] = targeted['initiatives'][ocd_id]

	cur.execute('''
		SELECT name, party, office_name, last_name, first_name, ballotpedia_url
		FROM election_candidates
		WHERE ocd_id IN ({ocd_ids})
		  AND general_status = 'On the Ballot'
	'''.format(ocd_ids=ocd_id_list), tuple(ocd_ids))
	print(ocd_ids)

	candidate_lookup = {}
	rs = cur.fetchall()
	if rs:
		for row in rs:
			office_name = row[2]
			if not office_name in candidate_lookup:
				candidate_lookup[office_name] = []
			candidate_lookup[office_name].append({
				'name': row[0],
				'party': row[1],
				'last_name': row[3],
				'first_name': row[4],
				'ballotpedia_url': row[5]
			})

	def sort_candidates(a, b):
		if a['party'] == b['party']:
			if a['last_name'] == b['last_name']:
				return 1 if a['first_name'] > b['first_name'] else -1
			else:
				return 1 if a['last_name'] > b['last_name'] else -1
		elif a['party'] == 'Independent':
			return 1
		elif b['party'] == 'Independent':
			return -1
		else:
			return 1 if a['party'] > b['party'] else -1

	for ballot in elections['ballots']:

		# Only show candidates in the General Election (20181018/dphiffer)
		if ballot['type'] != 'general':
			continue

		for office_level in ballot['offices']:
			for office in ballot['offices'][office_level]:
				for race in office['races']:
					if race['name'] in candidate_lookup:
						name = race['name']
						race['candidates'] = candidate_lookup[name]
						race['candidates'].sort(cmp=sort_candidates)

	return elections
