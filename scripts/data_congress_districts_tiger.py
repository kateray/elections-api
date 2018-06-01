#!/bin/env python

import json, os, sys, us, area, optparse, re
import postgres_db, data_index
import mapzen.whosonfirst.geojson
import mapzen.whosonfirst.utils

script = os.path.realpath(sys.argv[0])
scripts_dir = os.path.dirname(script)
root_dir = os.path.dirname(scripts_dir)

opt_parser = optparse.OptionParser()
opt_parser.add_option('-s', '--start', dest='start', type='int', action='store', default=None, help='Start session (e.g. 113)')
opt_parser.add_option('-e', '--end', dest='end', type='int', default=None, action='store', help='End session (e.g. 115)')
options, args = opt_parser.parse_args()

session = options.start
district_prop = "CD%sFP" % session
source_path = "%s/sources/congress_districts_%s/congress_districts_%s.geojson" % (root_dir, session, session)

conn = postgres_db.connect()
cur = conn.cursor()

cur.execute("SELECT id, start_date, end_date FROM congress_sessions")
rs = cur.fetchall()
sessions = {}
if rs:
	for row in rs:
		id = row[0]
		sessions[id] = {
			"start_date": str(row[1]),
			"end_date": str(row[2])
		}

encoder = mapzen.whosonfirst.geojson.encoder(precision=None)

def get_filename(props):

	global district_prop

	state_geoid = props["STATEFP"]
	state_upper = str(us.states.lookup(state_geoid).abbr)
	state = state_upper.lower()

	district_num = props[district_prop]
	filename = "congress_district_%s_%s_%s.geojson" % (session, state, district_num)
	return filename

def sort_districts(a, b):
	a_filename = get_filename(a['properties'])
	b_filename = get_filename(b['properties'])
	if a_filename > b_filename:
		return 1
	else:
		return -1

print("Loading %s" % source_path)
with open(source_path) as data_file:
	data = json.load(data_file)

data["features"].sort(sort_districts)

for feature in data["features"]:

	props = feature["properties"]

	if props[district_prop] == "ZZ":
		continue

	state_geoid = props["STATEFP"]
	state_upper = str(us.states.lookup(state_geoid).abbr)
	state = state_upper.lower()
	district_num = props[district_prop]

	filename = get_filename(props)
	path = "congress_districts_%s/%s/%s" % (session, state, filename)
	abs_path = "%s/data/%s" % (root_dir, path)
	name = "%s %s" % (state_upper, props["NAMELSAD"])

	aclu_id = data_index.get_id('elections-api', 'congress_district', path, name)

	non_zero_padded = re.search('^0+(\d+)', district_num)
	if not non_zero_padded:
		non_zero_padded = district_num
	else:
		non_zero_padded = non_zero_padded.group(1)

	ocd_id = 'ocd-division/country:us/state:%s/cd:%s' % (state, non_zero_padded)

	print("Saving %s" % path)

	feature["properties"] = {
		"aclu_id": aclu_id,
		"geoid": props["GEOID"],
		"ocd_id": ocd_id,
		"name": name,
		"state": state,
		"start_session": options.start,
		"start_date": sessions[options.start]["start_date"],
		"end_session": options.end,
		"end_date": sessions[options.end]["end_date"],
		"district_num": district_num
	}
	feature["id"] = aclu_id

	mapzen.whosonfirst.utils.ensure_bbox(feature)
	feature["properties"]["area"] = area.area(feature["geometry"])

	dirname = os.path.dirname(abs_path)
	if not os.path.exists(dirname):
		os.makedirs(dirname)

	with open(abs_path, 'w') as outfile:
		encoder.encode_feature(feature, outfile)

print("Saving index")
data_index.save_index('elections-api')

print("Done")
