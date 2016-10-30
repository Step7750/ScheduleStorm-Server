<p align="center">
  <img src="http://i.imgur.com/ZBRXem4.png"/>
</p>

[ScheduleStorm.com](http://schedulestorm.com)

## Schedule Storm Server

Welcome to the back-end that powers Schedule Storm. The back-end is written entirely in Python using Falcon, Beautiful Soup, ldap3, requests, MongoDB, and pymongo.

As you might expect, Schedule Storm is reliant upon class data for numerous universities. Since many universities don't have APIs to query, the vast majority of scraping is done on HTML using Beautiful Soup and Requests. Here you'll be able to find documentation on how to add your University to Schedule Storm.

# How to Add Your University

1. Settings File
2. Creating Your University Python File
3. Adding Terms to the DB
4. Adding Course Descriptions to the DB
5. Adding Classes to the DB

## Settings File

Using the settings file, you can tell Schedule Storm your University's rmpid, api key, username, password, etc...

**Every University Must Have An Entry in settings.json**

```javascript
{
    "Universities": {
    	...
        "<uniID>": {
            "fullname": "<University Name>"
            "enabled": true,
            "rmpid": <rmpid>
        },
	...
```

| key       | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| uniID     | string | No       | ID/Abbreviation of the University (ex. UCalgary, MTRoyal)
| fullname  | string | No       | Full name of the university shown to the user (ex. University of Calgary)
| enabled   | bool   | No       | Boolean as to whether this university is enabled or not
| rmpid     | int    | Yes      | RMP ID of the University to fetch professor data from


Within the university's JSON block, you can have as many more attributes as you'd like. Here, you can specify usernames, passwords, api keys, and they'll all be passed to your University thread upon creation.

#### How to get the RMP ID?

Simply go to [Rate My Professors](http://www.ratemyprofessors.com/) and search for your university in the search bar. Make sure you click on your university in the bottom "Schools" section. 

Afterwards, you will be forwarded to a URL such as: http://www.ratemyprofessors.com/campusRatings.jsp?sid=1416

The sid parameter is the school ID, thus, this RMP ID is 1416.
