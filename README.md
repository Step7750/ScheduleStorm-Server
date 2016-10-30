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
3. Terms
4. Subjects
5. Course Descriptions
6. Classes

# Settings File

Using the settings file, you can tell Schedule Storm your University's rmpid, api key, username, password, etc...

**Every University Must Have An Entry in settings.json**

```javascript
{
    "Universities": {
    	...
        "<uniID>": {
            "fullname": "<University Name>"
            "enabled": true,
	    "scrape": true,
            "rmpid": <rmpid>,
	    ...
        },
	...
```

| key       | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| uniID     | string | No       | ID/Abbreviation of the University (ex. UCalgary, MTRoyal)
| fullname  | string | No       | Full name of the university shown to the user (ex. University of Calgary)
| enabled   | bool   | No       | Boolean as to whether this university is enabled or not
| scrape    | bool   | No       | If true, starts the university thread to fetch updated course info
| rmpid     | int    | Yes      | RMP ID of the University to fetch professor data from


Within the university's JSON block, you can have as many more attributes as you'd like. Here, you can specify usernames, passwords, api keys, and they'll all be passed to your University thread upon creation.

#### How to get the RMP ID?

Simply go to [Rate My Professors](http://www.ratemyprofessors.com/) and search for your university in the search bar. Make sure you click on your university in the bottom "Schools" section. 

Afterwards, you will be forwarded to a URL such as: http://www.ratemyprofessors.com/campusRatings.jsp?sid=1416

The sid parameter is the school ID, thus, this RMP ID is 1416.


# Creating Your University Python File

## File Name

**All of the universities are located in the "uni" folder with their names being \<uniID\>.py**

For example: University of Calgary has a uniID of "UCalgary" in the settings file, so its file is UCalgary.py.

## Creating the Class

Each university inherits the University class, which inherits the threading.Thread class. 

Within your Uni file, you must import the University superclass at the top: `from .University import University`. The `University` superclass contains the API handlers and DB interaction methods.

Next, you'll want to create a class that inherits `University` and is named your uniID along with instantiating the University superclass in your `__init__` method.

ex. If your uniID is "UCalgary"

```python
from .University import University

class UCalgary(University):
    def __init__(self, settings):
        super().__init__(settings)

    def run(self):
        """
        Scraping thread that obtains updated course info
        :return:
        """
        self.log.info("Obtain course info here!")
```

**Within the run method, you should fetch updated course data**

It is highly recommended that you set a scraping interval within your settings file to pause the scraping every X seconds after it is finished before scraping again.

# Terms

Since each university inherits the `University` superclass, all interaction with the MongoDB database is done through it. You can use the following methods to interface with the terms.

## Term Object
Term Objects are dictionaries with the specified keys

| key       | Type   | Optional | Unique | Notes
| --------- | ------ | -------- | ------ | ------ |
| id        | string | No       | Yes    | ID of the Term (ex. "20235")
| name      | string | No       | No     | Name of the term (ex. "Fall 2016")

Within the DB, it also contains an enabled flag that specifies whether it is shown to users or not. The Term methods abstract this from you.

## Term Methods

### `updateTerms(list terms)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| terms     | list   | No       | List of term objects to update in the DB

**NOTE: This sets the only enabled terms to be the specified terms in the list**

Updates the terms specified into the DB. If a term doesn't exist in the DB yet, it is inserted.

### `updateTerm(dict term)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| term      | dict   | No       | Term object to update in the DB

Updates the term specified into the DB and sets its enabled flag to `True` (shows it to users). If the term doesn't exist in the DB yet, it is inserted.

### `getTerm(str/int termid)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| termid    | string | No       | ID of the term for fetch the term obj for

Returns: Term object for the specified termid if succesful, False if not

### `resetEnabledTerms()`

Sets every term within the DB to have a `False` enabled flag (isn't shown to users).

# Subjects

## Subject Object
Subject Objects are dictionaries with the specified keys

| key       | Type   | Optional | Unique | Notes
| --------- | ------ | -------- | ------ | ------ |
| subject   | string | No       | Yes    | Subject abbreviation (ex. CPSC)
| name      | string | No       | No     | Subject name (ex. Computer Science)
| faculty   | string | Yes      | No     | Faculty that this subject belongs to (ex. Faculty of Science)

## Subject Methods

### `updateSubjects(list subjects)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| subjects  | list   | No       | List of subject objects to update in the DB

Updates the subjects specified into the DB. If a subject doesn't exist in the DB yet, it is inserted.

### `updateSubject(dict subject)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| subject   | dict   | No       | Subject object to update in the DB

Updates the subject specified into the DB. If the subject doesn't exist in the DB yet, it is inserted.

