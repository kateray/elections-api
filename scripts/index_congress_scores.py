#!/bin/env python

import psycopg2, os, re, sys, csv
import postgres_db
import unicodedata

def strip_accents(s):
	s = s.decode('utf-8')
	return ''.join(c for c in unicodedata.normalize('NFD', s)
		if unicodedata.category(c) != 'Mn')

script = os.path.realpath(sys.argv[0])
scripts_dir = os.path.dirname(script)
root_dir = os.path.dirname(scripts_dir)

conn = postgres_db.connect()
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS legislator_scores CASCADE")
cur.execute("DROP TABLE IF EXISTS congress_legislator_scores CASCADE")
cur.execute('''
	CREATE TABLE congress_legislator_scores (
		aclu_id VARCHAR(255),
		category VARCHAR(255),
		subcategory VARCHAR(255),
		position VARCHAR(255),
		name VARCHAR(512),
		value VARCHAR(255)
	)
''')

legislator_score_insert_sql = '''
	INSERT INTO congress_legislator_scores (
		aclu_id,
		category,
		subcategory,
		position,
		name,
		value
	) VALUES (%s, %s, %s, %s, %s, %s)
'''

reps = {}
sens = {}

cur.execute('''
	SELECT lt.aclu_id, lt.state, lt.district_num, lt.type, l.last_name
	FROM congress_legislator_terms AS lt,
	     congress_legislators AS l
	WHERE lt.end_date >= CURRENT_DATE
	  AND lt.aclu_id = l.aclu_id
''')

rs = cur.fetchall()
if rs:
	for row in rs:
		aclu_id = row[0]
		state = row[1].upper()
		district_num = row[2]
		type = row[3]
		if type == 'rep':
			if district_num == 0:
				district_num = 1
			if int(district_num) < 10:
				district_num = "0%s" % district_num
			else:
				district_num = str(district_num)
			state_district = "%s-%s" % (state, district_num)
			reps[state_district] = aclu_id
		else:
			if not state in sens:
				sens[state] = []
			sens[state].append({
				'aclu_id': aclu_id,
				'last_name': row[4]
			})

rep_scores_csv = '%s/sources/aclu_scores/aclu_rep_scores.csv' % root_dir
with open(rep_scores_csv, 'rb') as csvfile:

	reader = csv.reader(csvfile)

	row_num = 0
	headers = []
	categories = []
	subcategories = []
	aclu_position = []

	for row in reader:

		name = row.pop(0)
		state_district = row.pop(0)
		party = row.pop(0)

		if row_num == 0:
			headers = row
		elif row_num == 1:
			categories = row
		elif row_num == 2:
			subcategories = row
		elif row_num == 3:
			aclu_position = row
		else:
			print name
			if state_district in reps:
				col_num = 0
				for col in row:
					aclu_id = reps[state_district]
					category = categories[col_num]
					subcategory = subcategories[col_num]
					position = aclu_position[col_num]
					name = headers[col_num]
					value = row[col_num]
					values = [
						aclu_id,
						category,
						subcategory,
						position,
						name,
						value
					]
					values = tuple(values)
					cur.execute(legislator_score_insert_sql, values)
					col_num = col_num + 1

		row_num = row_num + 1

		conn.commit()

sen_scores_csv = '%s/sources/aclu_scores/aclu_sen_scores.csv' % root_dir
with open(sen_scores_csv, 'rb') as csvfile:

	reader = csv.reader(csvfile)

	row_num = 0
	headers = []
	categories = []
	subcategories = []
	aclu_position = []

	for row in reader:

		name = row.pop(0)
		state = row.pop(0)
		party = row.pop(0)

		if row_num == 0:
			headers = row
		elif row_num == 1:
			categories = row
		elif row_num == 2:
			subcategories = row
		elif row_num == 3:
			aclu_position = row
		else:
			print name

			lname0 = strip_accents(sens[state][0]["last_name"])
			lname1 = strip_accents(sens[state][1]["last_name"])

			if name.find(lname0) != -1:
				aclu_id = sens[state][0]["aclu_id"]
			elif name.find(lname1) != -1:
				aclu_id = sens[state][1]["aclu_id"]
			else:
				print "COULD NOT FIND %s" % name
				continue

			col_num = 0
			for col in row:
				category = categories[col_num]
				subcategory = subcategories[col_num]
				position = aclu_position[col_num]
				name = headers[col_num]
				value = row[col_num]
				values = [
					aclu_id,
					category,
					subcategory,
					position,
					name,
					value
				]
				values = tuple(values)
				cur.execute(legislator_score_insert_sql, values)
				col_num = col_num + 1

		row_num = row_num + 1

		conn.commit()

conn.close()
print("Done")