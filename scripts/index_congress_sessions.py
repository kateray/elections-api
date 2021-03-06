#!/bin/env python

import bs4, arrow, psycopg2, os, re, sys
import postgres_db

script = os.path.realpath(sys.argv[0])
scripts_dir = os.path.dirname(script)
root_dir = os.path.dirname(scripts_dir)

curr_session = 116
curr_end_date = "2021-01-03"

next_session = 117
next_start_date = "2021-01-03"
next_end_date = "2023-01-03"

conn = postgres_db.connect()
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS sessions") # old table name
cur.execute("DROP TABLE IF EXISTS congress_sessions")
cur.execute('''
	CREATE TABLE congress_sessions (
		id INTEGER PRIMARY KEY,
		start_date DATE,
		end_date DATE
	)''')
conn.commit()

insert_sql = '''
	INSERT INTO congress_sessions (
		id,
		start_date,
		end_date
	) VALUES (%s, %s, %s)
'''

print("%s: %s to %s" % (next_session, next_start_date, next_end_date))
values = [
	next_session,
	next_start_date,
	next_end_date
]
cur.execute(insert_sql, values)

source_path = "%s/sources/congress_sessions/congress_sessions.html" % root_dir
with open(source_path) as source_file:
	soup = bs4.BeautifulSoup(source_file.read(), "html.parser")

last_cell = None

for row in soup.find_all('tr'):
	cells = row.find_all('td')
	if len(list(cells)) < 4:
		continue

	for cell in cells:
		sup = cell.find('sup')
		if sup:
			sup.clear()

	label = cells[0].get_text().strip()
	if label:
		if last_cell:
			start_date = last_cell
			start_date = arrow.get(start_date, 'MMM D, YYYY').format('YYYY-MM-DD')
			print("%s: %s to %s" % (session, start_date, end_date))
			values = [
				int(session),
				start_date,
				end_date
			]
			cur.execute(insert_sql, values)

		session = label

		# Current session doesn't include an end date, weirdly
		if int(session) == curr_session:
			end_date = curr_end_date
		else:
			end_date = cells[3].get_text().strip()
			end_date = arrow.get(end_date, 'MMM D, YYYY').format('YYYY-MM-DD')

	last_cell = cells[2].get_text().strip()

start_date = last_cell
start_date = arrow.get(start_date, 'MMM D, YYYY').format('YYYY-MM-DD')
print("%s: %s to %s" % (session, start_date, end_date))

values = [
	int(session),
	start_date,
	end_date
]
cur.execute(insert_sql, values)

conn.commit()
conn.close()

print("Done")
