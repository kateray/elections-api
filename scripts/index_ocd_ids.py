#!/bin/env python

import psycopg2, os, re, sys, csv
import postgres_db

script = os.path.realpath(sys.argv[0])
scripts_dir = os.path.dirname(script)
root_dir = os.path.dirname(scripts_dir)

conn = postgres_db.connect()
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS ocd_ids CASCADE")
cur.execute('''
	CREATE TABLE ocd_ids (
		id VARCHAR(255),
		name VARCHAR(255),
		geoid VARCHAR(255)
	)
''')

cur.execute('''
	CREATE INDEX ocd_ids_lookup_idx ON ocd_ids (
		id,
		geoid
	)
''')

insert_sql = '''
	INSERT INTO ocd_ids (
		id,
		name,
		geoid
	) VALUES (%s, %s, %s)
'''

source_dir = '%s/sources/ocd_ids/ocd-division-ids-master' % root_dir
csv_dir = '%s/identifiers/country-us/census_autogenerated' % source_dir
csv_path = '%s/us_census_places.csv' % csv_dir

with open(csv_path, 'rb') as csvfile:
	reader = csv.reader(csvfile)
	row_num = 0
	for row in reader:
		if row_num == 0:
			headers = row
		else:
			id = row.pop(0)
			name = row.pop(0)
			geoid = row.pop(0)

			# WHY DOES THIS NOT MATCH???
			# ex: id = ocd-division/country:us/state:wv/county:berkeley
			if re.match('/county[^/]+$', id):
				print name
				cur.execute(insert_sql, (id, name, geoid))
			else:
				print("skipping %s" % id)

		row_num = row_num + 1

		conn.commit()
