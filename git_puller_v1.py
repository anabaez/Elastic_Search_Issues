"""
This is the script file for creating a GitHub bug_tracker in Squirro . 
"""

import requests
from requests.auth import HTTPBasicAuth
from squirro_client import ItemUploader 
import sys
import json
import argparse
import hashlib

# Script version. It's recommended to increment this with every change, to make
# debugging easier.
VERSION = '0.9.0'

# Set up logging.
log = logging.getLogger('{0}[{1}]'.format(os.path.basename(sys.argv[0]),
                                          os.getpid()))

CACHE_FOLDER = 'C:/Python27/cache'

def main(args, config):
    uploader = ItemUploader(project_id=config.get('sq_creds','project_id'), 
                                source_name=config.get('sq_creds','source_name'),
                                token=config.get('sq_creds','token'),
                                cluster=config.get('sq_creds','cluster'))




def pretty_print(obj):
	print json.dumps(obj, indent=4, sort_keys=True)
	return

def get_comments_by_url(url, auth):

	#create cachekey
	m = hashlib.md5()
	m.update(url)
	key = m.hexdigest()

	cache_file_path = "%s/%s.json" % (CACHE_FOLDER, key)

	try:
		#HIT
		with open(cache_file_path, 'rb') as cache_file:
			return json.loads(cache_file.read())
	except IOError:
		#MISS
		result = requests.get(url, auth=auth)
		data = result.json()

		with open(cache_file_path, 'wb') as cache_file:
			cache_file.write(json.dumps(data, indent=4))
		return data

def parse_link_header(headers):

	if not headers.get('link'):
		return None

	#get all the links
	links = headers.get('link').split(',')
	#not sure what this is used for?
	next_link = None

	#look for the next link
	for link in links:
		if link.find('\"next\"') == -1:
			continue

		#extract the next url
		return link.split(';')[0].strip().strip('<').strip('>')

	return None

def add_keyword(obj):
	ks[obj]=[]

	for key in issue[obj]:
		ks[obj].append(key)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--verbose', '-v', action='count',
                        help='Show additional information.')
    parser.add_argument('--log-file', dest='log_file',
                        help='Log file on disk.')
    parser.add_argument('--config-file', dest='config_file',
                        help='Configuration file to read settings from.')
	parser.add_argument('--debug', '-d', help='turn on printing',
						required=False, type=int, default = 0, choices=[0,1])
	parser.add_argument('--user','-u',help='Input GitHub username',
						required=True)
	parser.add_argument('--password','-p',help='Input GitHub password',
						required=True)
    return parser.parse_args()



user = (args.user,args.password)

url = config.get('git_creds','url')

payload = {'per_page':'5','page':1, 'state':'all', 'sort':'updated'}

#github issue url : 'https://api.github.com/repos/elastic/elasticsearch/issues'
r = requests.get(url, auth=user, params=payload)

print "done requesting"

while True:

	#print r.headers['link']
	if r.text == '':
		#print 'Breaking', repr(r.text)
		break
	
	#print json.dumps(r.json(), indent=4)
		
	items = []
	issues = r.json()

	for issue in issues : 
		print "hullo"
		item={}
		item['title'] = issue['title']
		item['id'] = issue['id']
		item['link'] = issue['html_url']
		item['created_at'] = issue['updated_at'].strip('z')

		if issue['closed_at'] != None:
			#print issue['closed_at']
			closed_at = ' - ' + issue['closed_at']
		else:
			closed_at = ''
			closed_at = closed_at.strip('Z')

		body = u"""
			<html>
				<head> 
					<H6> 
					Status: {status}  {closed_at} <br/>
					Author: {author} <br/>
					Updated: {updated}
					</H6>
				</head>
			<pre>
				<body>
				{body}
				</body>
			</pre>
			</html>
			""".format(author=issue['user']['login'], updated=item['created_at'], body=issue['body'], status=issue['state'], closed_at = closed_at)
		
		#issue comments are contained in a seperate page
		if issue['comments'] != '0':
			comments = get_comments_by_url(issue['comments_url'], auth=user)
			for comment in comments:
				body += u"\n" + u"""
					<html>
						<head>
							<H6>
							Comment: <br/>
							Author: {author} <br/>
							Updated: {updated}
							</H6>
						</head>
					<pre>
						<body>
						{body}
						</body>
					</pre>
					</html>
					""".format(author=comment['user']['login'], updated=comment['updated_at'].strip('Z'), body=comment['body'])
				
		item['body'] = body

		#Add keywords
		ks = {}
		'''
def add_keyword(obj):
	ks[obj]=[]

	for key in issue[obj]:
		ks[obj].append(key)
'''
		
		ks['comments']=str(issue['comments'])
		
		if issue['locked'] == True:
			ks['locked']='locked'
		
		if issue['assignee'] != None:
			ks['assignee'] = issue['assignee']['login']

		if issue['milestone'] != None:
			ks['milestone'] = issue['milestone']

		ks['labels'] = []

		for label in issue['labels']:
			ks['labels'].append(label['name'])

		ks['status'] = issue['state']

		ks['id'] = issue['id']

		item['keywords'] = ks

		items.append(item)		
	#uploader.upload(items)

	#are there more?
	next = parse_link_header(r.headers)
	print next

	if not next:
		break

	r = requests.get(next, auth=user, )

