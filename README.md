<p align="center">
  <img src="http://i.imgur.com/ZBRXem4.png"/>
</p>

[ScheduleStorm.com](http://schedulestorm.com)

## Schedule Storm Server

Welcome to the back-end that powers Schedule Storm. The back-end is written entirely in Python using Falcon, Beautiful Soup, ldap3, requests, MongoDB, and pymongo.

As you might expect, Schedule Storm is reliant upon class data for numerous universities. Since many universities don't have APIs to query, the vast majority of scraping is done on HTML using Beautiful Soup and Requests. Here you'll be able to find documentation on how to add your University to Schedule Storm.

# How to Run

### Python Dependencies
* Requests
* Beautiful Soup 4
* ldap 3
* pymongo
* falcon

#### Also requires MongoDB to be running

Go through `settings.json` and set the `enabled` and `scrape` settings to true for every university you'd like to enable.

The default port is 3000, you can change this at the bottom of index.py

Make sure MongoDB is running and simply run: `python index.py`

You can browse the API by going to `http//localhost:3000/v1/unis` or `http://localhost:3000/v1/unis/{uni}/{term}/all`

If you'd like to use the front-end with your local API, clone it and change the URLs at the top of `ClassList.js` and `Welcome.js`

# How to Add Your University

1. [Settings File](https://github.com/Step7750/ScheduleStorm_Server#settings-file)
2. [Creating Your University Python File](https://github.com/Step7750/ScheduleStorm_Server#creating-your-university-python-file)
3. [Terms](https://github.com/Step7750/ScheduleStorm_Server#terms)
4. [Subjects](https://github.com/Step7750/ScheduleStorm_Server#subjects)
5. [Course Descriptions](https://github.com/Step7750/ScheduleStorm_Server#course-descriptions)
6. [Classes](https://github.com/Step7750/ScheduleStorm_Server#classes)

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
| name      | string | Yes      | No     | Subject name (ex. Computer Science)
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

# Course Descriptions

## Course Description Object
Course Description Objects are dictionaries with the specified keys

| key       | Type   | Optional | Unique | Notes
| --------- | ------ | -------- | ------ | ------ |
| coursenum | string | No       | No     | Course number (ex. "300")
| subject   | string | No       | No     | Subject abbreviation (ex. "CPSC")
| name      | string | Yes      | No     | Name/title of the course (ex. "Introduction to Computer Science")
| desc      | string | Yes      | No     | Description of the course (ex. "You'll learn about computers in this course")
| units     | int    | Yes      | No     | How many units this course is worth (ex. 3)
| hours     | string | Yes      | No     | Distribution of hours between types of classes (ex. "H(3-3)")
| prereq    | string | Yes      | No     | Human-readable course prerequisites (ex. "Must take CPSC 299 or CPSC 256")
| coreq     | string | Yes      | No     | Human-readable course corequisites (ex. "Must take CPSC 301 with this course")
| antireq   | string | Yes      | No     | Human-readable course antirequisites (ex. "Student must not have taken CPSC 302")
| notes     | string | Yes      | No     | Any further human-readable notes for this class (ex. "You might learn too much!")

The coursenum and subject fields together form a unique constraint.

## Course Description Methods

### `updateCourseDesc(dict coursedesc)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| coursedesc | dict   | No       | Course description object to update in the DB

Updates the course description specified into the DB. If the course description doesn't exist in the DB yet, it is inserted.

### `getCourseDescription(string coursenum, string subject)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| coursenum | string | No       | Course number of the description to obtain (ex. "300")
| subject   | string | No       | Subject abbreviation of the description to obtain (ex. "CPSC")

Returns: Course Description object of the specified coursenum and subject if successful, False if not


# Classes

## Class Object
Class Objects are dictionaries with the specified keys

| key       | Type   | Optional | Unique | Notes
| --------- | ------ | -------- | ------ | ------ |
| id        | int    | No       | Yes    | ID of the class (ex. "34534")
| subject   | string | No       | No     | Subject abbreviation (ex. "CPSC")
| term      | string | No       | No     | Term ID that this class belongs to (ex. "2342")
| coursenum | string | No       | No     | Course number of the description to obtain (ex. "300")
| rooms     | list   | No       | No     | List of strings that contain the rooms that this class is situated in (ex. ["MFH 164", "HEH 101"]). If there are no rooms, set it to ["TBA"] or ["N/A"]
| teachers  | list   | No       | No     | List of strings that contain the teachers teaching this class (ex. ["Jack Shepard", "Hugo 'Hurley' Reyes"]). If there are no teachers, set it to ["TBA"] or ["N/A"]
| type      | string | No       | No     | Type of the class (ex. "LEC")
| times     | list   | No       | No     | List of strings that contain the times in which this class is (ex. ["MWF 12:00PM - 2:00PM"]). If there are no times, set it to ["TBA"] or ["N/A"]. See below for time formatting.
| group     | string | No       | No     | Group of this class. If another class with the same coursenum and subject yet different type and has the same group value, the two classes can be taken together. (ex. "1")
| status    | string | No       | No     | If the class is open, set to "Open", otherwise, set the enrollment status to "Closed" or "Wait List"
| section   | string | Yes      | No     | Shows this value instead of `group` to the user when applicable 
| restriction | bool | Yes      | No     | True if this class has a restriction to some students

### Time Formatting

Each time for a given class must be in the specified format:

### `<DaysOfTheWeek> <StartTime><AM/PM> - <EndTime><AM/PM>`

* Days of the Week
	* Concatenated series of days in which this time is applicable
	* Possible Days
		* M/Mo - Monday
		* T/Tu - Tuesday
		* W/We - Wednesday
		* R/Th - Thursday
		* F/Fr - Friday
		* S/Sa - Saturday 
		* U/Su - Sunday
	* Examples
		* "M"
		* "MTR"
		* "FWM"
	* Order of the days does not matter

* StartTime/EndTime
	* 12-hour Start/End time
	* Format: `<Hour>:<Minutes>`
	* Examples
		* "12:00"
		* "1:23"

* Examples
	* "TR 12:00PM - 1:20PM"
	* "MWF 9:50AM - 10:30AM"
	* "MoWeFr 9:00AM - 11:00AM"
	* "MoTWe 2:00PM - 3:00PM"

## Class Methods

### `updateClasses(list classes)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| classes   | list   | No       | List of class objects to update

Updates the classes specified into the DB. If a class doesn't exist in the DB yet, it is inserted.

### `updateClass(dict class)`
Arguments:

| name      | Type   | Optional | Notes
| --------- | ------ | -------- | ------ |
| class     | dict   | No       | Class object to update

Updates the class specified into the DB. If the class doesn't exist in the DB yet, it is inserted.


# General Tips When Adding a University

* Don't use print statements, the `University` superclass contains a [`logger`](https://docs.python.org/3.5/library/logging.html#logger-objects), you can use it with `self.log`
	* Examples
		* `self.log.error("You can't do this")`
		* `self.log.info("Scraping courses")`
* You can access your uni settings object with `self.settings` within the uni class
* Add a `scrapeinterval` in your settings file and add a delay between successful scraping sessions using `time.sleep(self.settings["scrapeinterval"]`
* Look at `Example.py` for a starting point, make sure you edit the settings file though!
* If you want to add more attributes to a class/subject/term/coursedesc object, go ahead! They won't be used by the front-end, but we can add support for it later on!
* If you have any questions/concerns, feel free to file an issue or talk to us!

# Authors
* Stepan Fedorko-Bartos - [Email](mailto:stepan.fedorkobartos@ucalgary.ca), [Github](https://github.com/step7750), [LinkedIn](https://linkedin.com/in/step7750)
* Ceegan Hale - [Email](mailto:ceeganhale@gmail.com), [Github](https://github.com/per-plex), [LinkedIn](https://www.linkedin.com/in/ceegan-hale-64a4a9128)
* Thanks to any contributors!

## Inspiration from:

* [Hey Winston for University of Alberta](https://github.com/ahoskins/winston)

