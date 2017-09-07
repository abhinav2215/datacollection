#!/usr/bin/python
# -*- coding: utf-8 -*-

# I find it hard to write clean looking code.
# If you think this is clean, please thank this Pretty Formatter https://pythoniter.appspot.com

# Import all tweets from a given list of authors
# Specify a file name containing one author id per row on the command line, with maxID tuple
# authorfile = main.txt

from twython import Twython
from twython.exceptions import TwythonRateLimitError, TwythonError
from time import gmtime, strftime, sleep
from os import path
from datetime import datetime
from bs4 import BeautifulSoup
import signal
import sys
import demjson
import json
import re
import requests

if len(sys.argv) != 3:
    print("Usage:", sys.argv[0], "<authorFile> <keyFile>")
    exit(1)
else:
    if path.isfile(sys.argv[1]) and path.isfile(sys.argv[2]):
        input_file_name = sys.argv[1]
        keyfile= sys.argv[2]
        print("Input file:", input_file_name)
    else:
        print("authorFile or keyFile not found")
        exit(0)

current_time = strftime("%Y%m%d_%H%M%S", gmtime())

output_file_name = 'authors.output.' + input_file_name + "."+ current_time+".json"
output_file_name_authors_explored = 'authors_id_explored.output.' + input_file_name + "." + current_time
output_file = open(output_file_name, mode='a')
output_file_authors_explored = open(output_file_name_authors_explored, mode='a')

kf = open(keyfile, 'r+')
keys=kf.readlines()[1:]
kf.close()
(nKey, kCount) = (len(keys), 0)  # Number of keys
twitter = False

input_file = open(input_file_name, mode='r')
nb = 0

def changeTwitterKey():
	global kCount, twitter
	key = keys[kCount].strip().split(',')
	twitter = Twython(*key)
	kCount += 1
	if kCount == nKey:
		kCount = 0
	print(twitter)

def checkKeyReplacementTwitter():
	rate_url ='https://api.twitter.com/1.1/application/rate_limit_status.json'
	constructed_url = twitter.construct_api_url(rate_url,resources='search,statuses,application')
	rate_result = twitter.request(constructed_url, method='GET')['resources']

	f=open("rate.json","w+")
	f.write(json.dumps(rate_result,indent=2))
	f.close()

	rem = min(rate_result['statuses']['/statuses/user_timeline']['remaining'],rate_result['application']['/application/rate_limit_status']['remaining'])
	print("Remaining: ",str(rem))
	if rem < 2:
		print('Time to change')
		changeTwitterKey()

def retrieveURL(tweet):
	global filt
	print("Filter: ",filt)
	urls=re.findall(r'(https?://\S+)', tweet)
	for url in urls:
		for f in filt:
			if f in url:
				return url
	return False


def getFSQData(url):
	r=requests.get(url)
	print(url)
	bs=BeautifulSoup(r.text,"html.parser")
	data=False
	for line in bs.find_all('script',attrs={"type" : "text/javascript"}):
		data=line.text if "SwarmCheckinDetail" in line.text[:100] else ""
	if data:
		try:
			data=data.split("SwarmCheckinDetail.init")[1][1:-2].replace("$('body')", '"body"',1)

			# Debugging Actions
			temp=open("temp.json","w+")
			data=demjson.decode(data)
			temp.write(str(data))
			temp.close()

			# data=json.loads(data)
			user,venue={"id":"","firstName":""},{"lng":"","lat":""}
			for key in user: user[key]=data["checkin"]["user"][key]
			for key in venue: venue[key]=data["venue"]["location"][key]
			venue["id"]=data["venue"]["id"]


			print(user)
			print(venue)
			return (user["id"],venue["id"])
		except Exception as e:
			print "Exception in getting checkin data: " + url
			return (False,False)
	# sys.exit(1)
	else:
		return (False, False)



def terminate(signal, frame):
	print("Ctrl + C handler: close file!")
	output_file.close()
	output_file_authors_explored.close()
	print("File closed with about " + str(nb) + " lines")
	exit(0)

signal.signal(signal.SIGINT, terminate)

# INITIALIZE TWITTER
changeTwitterKey()

print(twitter)
nb_tweets = 0
x=input_file.readlines()
authors=[]
for i in x:
	aut=i.strip()
	authors.append(aut)

# print(authors)
# authors = input_file.readlines()
nb_authors = len(authors)
author_id_nb = 0
# print(authors)
dateFormat = "%a %b %d %H:%M:%S +0000 %Y"
filt=["swarmapp.com/","4sq.com/","foursquare.com/"]
fsqUserID="804341497441255424"
for author_id in authors:
	# author_id = author_id[:-1]
	try:
		temp=author_id.split()
		print "temp "+str(temp)
		auth,sinceId=temp[0],int(temp[1])
		print "Start: "+auth
		last_id = -1
		author_id_nb_tweets = 0
		author_id_nb += 1
		flag=True
		ctr=0
		while flag==True:
			checkKeyReplacementTwitter()
			if auth == fsqUserID:
				# Foursquare's user ID. Just in case that shows up we don't need links from there as they might not
				# flag=False
				break
			try:
				if last_id == -1:
					user_tweets = twitter.get_user_timeline(user_id=auth, include_rts='0', count=200,since_id=sinceId)
				elif last_id>sinceId:
					user_tweets = twitter.get_user_timeline(user_id=auth, include_rts='0', count=200, max_id=last_id-1)
				else:
					print "found all tweets"
					break
				ctr+=1
				print("Try #"+str(ctr)+" Author_ID: "+str(auth))
			except TwythonRateLimitError:
				# print("TwythonRateLimitError: sleep 30 seconds...")
				# sleep(30)
				changeTwitterKey()
				continue
			except TwythonError as e:
				print "TwythonError:", e.msg
				if e.msg[2:21] == 'Connection aborted.':
					print "Try to get your connection back. Or Ctrl + C to stop with", nb, "tweets from about", author_id_nb, "authors. Sleep 30 seconds..."
					sleep(30)
					continue
				else:
					print "Maybe Protected. Maybe a problem with author", auth
					break
			print "Number of tweets fetched" ,len(user_tweets)
			if len(user_tweets)>0:
				x=user_tweets[0]["id"]
				y=user_tweets[-1]["id"]
				print "Start ID: ",x,"End ID: ",y
			if len(user_tweets) == 0:
				print "Author", author_id, "(", author_id_nb, "/", nb_authors, ") :", author_id_nb_tweets, "tweets. Total:",nb, "tweets."
				break
			for tweet in user_tweets:
				# print("WHAT")
				last_id = tweet["id"]
				last_date = tweet["created_at"]
				date=datetime.strptime(tweet["created_at"],dateFormat)

				
				nb += 1
				author_id_nb_tweets += 1

				# checkin=True
				# if int(last_id)<=int(sinceId):
				# 	break
				# checkin=False

				# log=open("log.log","a+")
				# log.write(str(last_id)+"\n")
				# log.close()

				# for Filter in filt:
				# 	if Filter in tweet["text"]:
				# 		checkin=True
				# 		break

				# if checkin==False:

				# print("checkin found")
				# debug=open("debug.txt","a+")
				# debug.write("Twitter ID: "+str(last_id)+"\n")
				# debug.write("Date: "+str(last_date)+"\n")
				# json.dump(tweet, debug,indent=2)
				# debug.write("\n\n")
				# debug.close()
				# print(tweet)
				# sys.exit(0)
				# output_file.write(str(tweet))
				print last_id,last_date
				if tweet["entities"]["urls"]:
					url=retrieveURL(tweet["entities"]["urls"][0]["expanded_url"])
				else:
					url=retrieveURL(tweet["text"])
				print("url: ",url)
				if url:
					user,venue=getFSQData(url)
				else:
					continue
				if (not user) or (not venue):
					continue

				json.dump(tweet, output_file,indent=2)
				output_file.write('\n')
				# checkins.write()
				# url=tweet['entities']['urls'][0]['expanded_url']
				print(last_date,url)
				dup=[str(auth),str(last_id),str(user),str(venue),str(last_date),str(url)]
				checkins=open("checkins.log","a+")
				checkins.write(' '.join(dup))
				checkins.write('\n')
				checkins.close()
				print("written to checkins!")
				dup=[]
				
				# print(output_file)
					
					
				# print(author_id, last_id, last_date, nb)
		output_file_authors_explored.write(author_id + '\n')
		print("End: "+author_id)
	except Exception as e:
		print e,author_id

terminate(None, None)
