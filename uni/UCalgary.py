"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import requests
from bs4 import BeautifulSoup
import re
import time
import logging
import traceback
from .University import University


log = logging.getLogger("UCalgary")

# Only for testing purposes in order to debug HTTPS network traffic
requests.packages.urllib3.disable_warnings()
verifyRequests = False


class UCalgary(University):

    # Maps the term season to its respective id
    termIDMap = {
        "Winter": 1,
        "Spring": 3,
        "Summer": 5,
        "Fall": 7
    }

    def __init__(self, settings):
        # UCalgary doesn't have a public directory for course info, we have to login with a student account
        super().__init__(settings)
        self.settings = settings
        self.loginSession = requests.session()

    def login(self):
        """
        Logs into MyUofC given the account specified in settings

        NOTE: Due to the lack of HTTP status codes on MyUofC, we have to see the text of the DOM as to whether the
        login was successful. The strings may change in the future, which will cause the bot to continually fail to login

        :return: **boolean** Defines whether we successfully logged in or not
        """

        log.info("Logging into MyUofC")

        payload = {"username": self.settings["username"],
                   "password": self.settings["password"],
                   "lt": "ScheduleStorm",
                   "Login": "Sign+In"}

        r = self.loginSession.post("https://cas.ucalgary.ca/cas/login?service="
                                   "https://my.ucalgary.ca/psp/paprd/?cmd=start&ca.ucalgary.authent.ucid=true",
                                   data=payload,
                                   verify=verifyRequests)

        # UCalgary has improper HTTP status codes, we can't use them (200 for invalid login etc...)
        # We'll have to scan the text to see whether we logged in or not
        if "invalid username or password" not in r.text:
            # Parse the form data
            payload = self.getHiddenInputPayload(r.text)


            r = self.loginSession.post("https://my.ucalgary.ca/psp/paprd/?cmd=start", data=payload, verify=verifyRequests)

            if "My class schedule" in r.text:
                # We probably logged in, it's hard to tell without HTTP status codes
                log.info("Successfully logged into MyUofC")
                return True
            else:
                return False
        else:
            log.error("Invalid Username or Password to MyUofC")
            return False

    def getHiddenInputPayload(self, text):
        """
        Given a U of C page, this will extract the inputs that are "hidden" and return their values

        :param text: **string** HTML of a UCalgary page with hidden input fields
        :return: **dict** Contains the names and values of the hidden inputs (called the "payload" for each request)
        """

        soup = BeautifulSoup(text, "lxml")

        payload = {}

        # We want to put all of the input fields that are "hidden" into a dict and send it over to the next request
        for hiddenfield in soup.findAll("input", {"type": "hidden"}):
            # Add this field
            if hiddenfield["name"] in payload:
                # This item is already in the dict, add this new value to the list
                if isinstance(payload[hiddenfield["name"]], list):
                    # Just append to the list
                    payload[hiddenfield["name"]].append(hiddenfield["value"])
                else:
                    # Make a new list
                    curval = payload[hiddenfield["name"]]
                    payload[hiddenfield["name"]] = [curval, hiddenfield["value"]]
            else:
                payload[hiddenfield["name"]] = hiddenfield["value"]

        return payload

    def scrapeSearchTerms(self):
        """
        MUST BE LOGGED IN

        Retrieves a list of available terms on the "Search classes" page to retrieve class data for

        :return:
        """
        r = self.loginSession.get("https://csprd.ucalgary.ca/psc/csprd/EMPLOYEE/CAMPUS/c/"
                                  "SA_LEARNER_SERVICES.CLASS_SEARCH.GBL?Page=SSR_CLSRCH_ENTRY"
                                  "&Action=U&ExactKeys=Y&TargetFrameName=None",
                                  verify=verifyRequests, allow_redirects=False)

        if r.status_code == requests.codes.ok:
            soup = BeautifulSoup(r.text, "lxml")

            termlist = []
            foundSelected = False

            for term in soup.find("select", {"id": re.compile('CLASS_SRCH_WRK2_STRM\$\d+\$')}).findAll("option"):
                if term.has_attr('selected'):
                    foundSelected = True

                if foundSelected:
                    termlist.append(term.text.split(' - ')[1])

            return termlist
        else:
            return False

    def parseTerms(self, text):
        """
        Returns list of terms on a term page

        :param text: **string** HTML of the UCalgary term page
        :return: **list** available terms on the page
        """
        soup = BeautifulSoup(text, "lxml")
        termlist = []
        for term in soup.findAll("span", {"id": re.compile('TERM_CAR\$\d*')}):
            termlist.append(term.text)

        return termlist

    def termNameToID(self, termname):
        """
        Given the term name, returns the id (ex. Winter 2017 = 2171)

        :param termname: **string** Name of the term (ex. Winter 2017)
        :return: **string** Term ID
        """
        splitname = termname.split(" ")
        id = ""

        # If the year is 2016, this creates 216
        id += splitname[1][0] + splitname[1][2:4]

        if splitname[0] in self.termIDMap:
            # We have a mapping for this season
            id += str(self.termIDMap[splitname[0]])
            return id
        else:
            # We don't have a mapping for this season
            return False

    def termIDToName(self, termname):
        """
        Given the term id, returns the name (ex. 2171 = Winter 2017)

        :param termname: **string/int** ID of the term (ex. 2171)
        :return: **string** Name of the term
        """
        termname = str(termname)

        year = termname[0] + "0" + termname[1:3]

        season = ""

        for termseason in self.termIDMap:
            if int(termname[3]) == self.termIDMap[termseason]:
                season = termseason
                break

        return season + " " + year

    def setSearchTerm(self, termid, payload):
        payload['ICAction'] = 'CLASS_SRCH_WRK2_STRM$35$'
        payload['DERIVED_SSTSNAV_SSTS_MAIN_GOTO$7$'] = 9999
        payload['CLASS_SRCH_WRK2_INSTITUTION$31$'] = 'UCALG'
        payload['CLASS_SRCH_WRK2_STRM$35$'] = termid
        payload['SSR_CLSRCH_WRK_SUBJECT_SRCH$0'] = ""
        payload['SSR_CLSRCH_WRK_SSR_EXACT_MATCH1$1'] = "C"
        payload['SSR_CLSRCH_WRK_CATALOG_NBR$1'] = ""
        payload['SSR_CLSRCH_WRK_ACAD_CAREER$2'] = ""
        payload['SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$3'] = "Y"
        payload['SSR_CLSRCH_WRK_SSR_OPEN_ONLY$3'] = "Y"
        payload['SSR_CLSRCH_WRK_OEE_IND$chk$4'] = "N"
        payload['DERIVED_SSTSNAV_SSTS_MAIN_GOTO$8$'] = 9999

        searchTerm = self.loginSession.post("https://csprd.ucalgary.ca/psc/csprd/EMPLOYEE/CAMPUS/c/"
                                            "SA_LEARNER_SERVICES.CLASS_SEARCH.GBL",
                                            data=payload, verify=verifyRequests)

        if searchTerm.status_code == requests.codes.ok:
            return searchTerm.text
        else:
            return False

    def getSearchTermCourses(self, termid):
        """
        Gets the available courses for the specified term and calls to obtain the classes for each one in search

        :param termid: **string/int** Term ID to get courses for
        :return:
        """
        log.info("Getting courses for " + str(termid))

        searchPage = self.loginSession.get("https://csprd.ucalgary.ca/psc/csprd/EMPLOYEE/CAMPUS/c/"
                                            "SA_LEARNER_SERVICES.CLASS_SEARCH.GBL?Page=SSR_CLSRCH_ENTRY"
                                            "&Action=U&ExactKeys=Y&TargetFrameName=None",
                                            verify=verifyRequests, allow_redirects=False)

        if searchPage.status_code != requests.codes.ok:
            return

        payload = self.getHiddenInputPayload(searchPage.text)

        termPage = self.setSearchTerm(termid, payload)

        if termPage is False:
            return

        # get subjects
        subjects = []

        soup = BeautifulSoup(termPage, "lxml")

        for subject in soup.find("select", {"id": "SSR_CLSRCH_WRK_SUBJECT_SRCH$0"}).findAll("option"):
            if subject["value"] != "":
                # Don't want to include the first whitespace option
                subjects.append(subject.text)

        for subject in subjects:
            try:
                self.getSubjectCourses(subject, termid, payload)
            except requests.exceptions.Timeout:
                log.error("Request timed out for " + subject)

        log.info("Finished parsing the term courses for " + str(termid))

    def getSubjectCourses(self, subject, termid, payload):
        """
        Gets and processes the courses for the given subject and termid

        :param subject: **string** Subject to obtain courses for
        :param termid: **int/string** ID of the term to obtain courses for
        :param payload: **dict** Hidden inputs of the previous page
        :return:
        """
        subjectid = subject.split("-")[0] # id, aka abbreviation

        # We want all of the classesfor this subject and since there is a 250 return limit, we request on a subject
        # by subject basis (and get around the >2 search parameters constraint)
        payload["ICAction"] = "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH"

        # Specify the subject
        payload["SSR_CLSRCH_WRK_SUBJECT_SRCH$0"] = subjectid

        # Specify the term
        payload["CLASS_SRCH_WRK2_STRM$35$"] = termid

        # Get every class with a number greater than or equal to 0 (should get every class)
        payload["CLASS_SRCH_WRK2_INSTITUTION$31$"] = "UCALG"
        payload["SSR_CLSRCH_WRK_SSR_EXACT_MATCH1$1"] = "G"
        payload["SSR_CLSRCH_WRK_CATALOG_NBR$1"] = 0
        payload["SSR_CLSRCH_WRK_ACAD_CAREER$2"] = ""
        payload["SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$3"] = "N"
        payload["SSR_CLSRCH_WRK_OEE_IND$chk$4"] = "N"
        payload["DERIVED_SSTSNAV_SSTS_MAIN_GOTO$8$"] = 9999
        payload["DERIVED_SSTSNAV_SSTS_MAIN_GOTO$7$"] = 9999

        log.info("Retrieving data for " + subjectid)

        # Get the courselist
        courselist = self.loginSession.post("https://csprd.ucalgary.ca/psc/csprd/EMPLOYEE/CAMPUS/c/"
                                            "SA_LEARNER_SERVICES.CLASS_SEARCH.GBL",
                                            data=payload, verify=verifyRequests, timeout=30)

        if "search will return over 50 classes" in courselist.text:
            # Want to continue
            log.info("Confirming we want more than 50 classes")
            payload = self.getHiddenInputPayload(courselist.text)
            payload["ICAction"] = "#ICSave"

            courselist = self.loginSession.post("https://csprd.ucalgary.ca/psc/csprd/EMPLOYEE/CAMPUS/c/"
                                                "SA_LEARNER_SERVICES.CLASS_SEARCH.GBL",
                                                data=payload, verify=verifyRequests, timeout=40)



        if "Your search will exceed the maximum limit" in courselist.text:
            # This should not happen, if means we couldn't retrieve these courses
            log.error("Too many courses for " + subjectid)
        elif "The search returns no results that match the criteria specified" in courselist.text:
            log.error("No courses for " + subjectid)
        else:
            # We probably have the data we want
            self.parseRawCourseList(courselist.text, subjectid, termid)

    def parseRawCourseList(self, courselist, subjectid, termid):
        """
        Parses the raw HTML of the course list and upsets each course in the DB
        :param courselist: **string** HTML of the course list page
        :param subjectid: **string** Subject that this course list is for
        :param termid: **int/string** Term of this course list
        :return:
        """

        soup = BeautifulSoup(courselist, 'html5lib')

        # If true, we are already obtaining descriptions for this subject, no need to make another thread
        obtainingDescriptions = False

        # Iterate through the courses
        for course in soup.findAll("div", {"id": re.compile('win0divSSR_CLSRSLT_WRK_GROUPBOX2\$\d*')}):
            coursename = course.find("div", {"id": re.compile('win0divSSR_CLSRSLT_WRK_GROUPBOX2GP\$\d*')}).text.strip()

            log.debug(coursename)

            subid = coursename.split("  ")[0]  # Subject ID

            if subid != subjectid:
                # We didn't receive the data we want, this shouldn't be happening
                log.error("Incorrect subject returned for " + subjectid + " while parsing " + str(termid) + ": " +
                    subid)
                continue

            splitname = coursename.split(" - ")
            coursenum = splitname[0].split("  ")[1]  # Course number
            descname = " ".join(splitname[1:]).strip()  # Short description of the course

            # Find the possible classes in this course
            for classdiv in course.findAll("table", {"id": re.compile('ACE_SSR_CLSRSLT_WRK_GROUPBOX3\$\d*')}):
                classid = classdiv.find("div", {"id": re.compile('win0divMTG_CLASSNAME\$\d*')}).text.strip()
                scheduletype = " ".join(classid.split("\n")[1:])  # Regular, LabWeek, etc...

                type = classid.split("\n")[0].split("-")[1]  # Lab, Lec etc...

                # Figure out if there are class restrictions
                restriction = False
                restrictiondiv = classdiv.find("div", {"id": re.compile('win0divUCSS_E010_WRK_HTMLAREA\$\d*')})

                if restrictiondiv.find("img"):
                    # There is a restriction on this class
                    restriction = True


                # Construct the upsert obj with the other properties
                classdict = {
                    "subject": subjectid,
                    "type": type,
                    "scheduletype": scheduletype.strip(),
                    "coursenum": coursenum,
                    "id": int(classdiv.find("div", {"id": re.compile('win0divMTG_CLASS_NBR\$\d*')}).text.strip()),
                    "term": int(termid),
                    "times": classdiv.find("div", {"id": re.compile('win0divMTG_DAYTIME\$\d*')}).text.strip().split("\n"),
                    "location": classdiv.find("div", {"id": re.compile('win0divUCSS_E010_WRK_DESCR\$\d*')}).text.strip(),
                    "rooms": classdiv.find("div", {"id": re.compile('win0divMTG_ROOM\$\d*')}).text.strip().split("\n"),
                    "teachers": classdiv.find("div", {"id": re.compile('win0divMTG_INSTR\$\d*')}).text.strip().replace(", ", "").split("\n"),
                    "group": classdiv.find("div", {"id": re.compile('win0divUCSS_E010_WRK_ASSOCIATED_CLASS\$\d*')}).text.strip(),
                    "status": classdiv.find("div", {"id": re.compile('win0divDERIVED_CLSRCH_SSR_STATUS_LONG\$\d*')}).find("img")["alt"],
                    "restriction": restriction
                }

                log.debug(classdict)

                # Remove whitespace and commas from teacher names
                for teacher in range(len(classdict["teachers"])):
                    classdict["teachers"][teacher] = classdict["teachers"][teacher].strip(", ").strip()

                # upsert the object
                self.updateClass(classdict)

                # Check if this subject is in the course descriptions db or not, if not, make it
                if not obtainingDescriptions:
                    # Check if this is already in the db
                    result = self.getCourseDescription(coursenum, subjectid)

                    if not result:
                        # There is no description for this course
                        obtainingDescriptions = True
                        threadm = CourseDescriptions(subjectid, super())
                        threadm.setDaemon(True)
                        threadm.start()


                # Now we want to update the course name in the UCalgaryCourseDesc db,
                # some courses don't have a description, at least they'll have a name
                # Usually this is due to a suffix onto the course number

                classdesc = {
                    "subject": subjectid,
                    "name": descname,
                    "coursenum": coursenum
                }

                self.updateCourseDesc(classdesc)

    def updateFaculties(self):
        # Get the list
        log.info("Getting faculty list")

        # Get faculty list
        r = requests.get("http://www.ucalgary.ca/pubs/calendar/current/course-by-faculty.html")

        if r.status_code != requests.codes.ok:
            log.error("Failed to retrieve faculty list")
            return

        soup = BeautifulSoup(r.text, "lxml")

        # Iterate through each faculty
        for faculty in soup.findAll("span", {"id": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnTitle')}):
            log.debug(faculty.text)

            # Get the faculty body
            body = faculty.parent.find("span", {"id": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnBody')})

            # Replace <br> with newlines
            for br in body.find_all("br"):
                br.replace_with("\n")

            # Obtain each subject
            subjects = body.find("p").text.split("\n")

            for subject in subjects:
                # Strip the subject name
                subject = subject.strip()
                if len(subject) > 1 and " " in subject:
                    subjectcode = subject.strip().split(" ")[-1]  # 3 or 4 letter subject code

                    # Make sure the code length is proper
                    if len(subjectcode) > 1:
                        subjectdict = {
                            "subject": subjectcode,
                            "faculty": faculty.text.strip()
                        }

                        self.updateSubject(subjectdict)

        log.info("Updated faculty list")

    def insertTerms(self, terms):
        """
        Inserts the terms as active into the DB

        :param terms: **list** List of UCalgary term names as strings
        :return:
        """
        termsdb = []

        for term in terms:
            thisterm = {"id": str(self.termNameToID(term)), "name": term}
            termsdb.append(thisterm)

        self.updateTerms(termsdb)

    def scrape(self):
        """
        Scraping function that obtains updated course info

        :return:
        """
        # Update the faculties
        self.updateFaculties()

        if not self.login():
            return

        terms = self.scrapeSearchTerms()

        if not terms:
            return

        self.insertTerms(terms)

        for term in terms:
            log.info("Obtaining " + str(term) + " course data with an id of " + str(self.termNameToID(term)))

            self.getSearchTermCourses(self.termNameToID(term))


class CourseDescriptions(threading.Thread):
        """
        Mines course descriptions from the U of C public site given the subject
        """

        mainpage = "http://www.ucalgary.ca/pubs/calendar/current/"
        fullname = ""  # full name of the subject (CPSC = Computer Science)

        def __init__(self, subject, parent):
            """
            Constructor for retrieving course descriptions

            :param subject: **string** Subject code to retrieve course descriptions for
            :return:
            """

            threading.Thread.__init__(self)
            self.subject = subject
            self.super = parent

        def run(self):
            log.info("Getting course descriptions for " + self.subject)

            obtained = False
            while not obtained:
                coursedescs = False

                # Get the list of the urls for each subject
                try:
                    coursedescs = requests.get(self.mainpage + "course-desc-main.html")
                except Exception as e:
                    log.critical('There was an error while obtaining course descriptions for ' +
                                 self.subject + " | " + str(e))


                if coursedescs and coursedescs.status_code == requests.codes.ok \
                        and "Course Descriptions" in coursedescs.text:
                    # Request was successful, parse it

                    obtained = True

                    # Parse the HTML of the listings
                    soup = BeautifulSoup(coursedescs.text, "lxml")

                    # Find the subject url on the page
                    for link in soup.find("table", {"id": "ctl00_ctl00_pageContent"}).findAll("a", {"class": "link-text"}):
                        # Subject 4 letter code
                        suffix = link.text.strip().split(" ")[-1]

                        # We found the subject, get it's descriptions
                        if suffix == self.subject:
                            log.debug("Found the course description url for " + self.subject)

                            # Get the full name of the subject (CPSC = Computer Science)
                            self.fullname = link.text.strip().split(" ")
                            self.fullname = " ".join(self.fullname[0:len(self.fullname)-1])

                            # Get the course descriptions
                            self.getCoursePage(link["href"])
                            break
                else:
                    # The request was unsuccessful, wait until the next attempt
                    time.sleep(60)

        def getCoursePage(self, link):
            """
            Obtains the courses page for the subject and updates the DB info for the subject's properties

            :param link: **string** Link to the course descriptions for this subject
            :return:
            """
            obtained = False

            while not obtained:
                r = requests.get(self.mainpage + link)

                if r.status_code == requests.codes.ok:
                    obtained = True

                    soup = BeautifulSoup(r.text, "lxml")

                    header = soup.find("span", {"id": "ctl00_ctl00_pageContent_ctl01_ctl02_cnBody", "class": "generic-body"})

                    index = 0

                    instructioninfo = ""
                    notes = ""

                    for child in header.findAll(recursive=False):
                        if index == 0:
                            instructioninfo = child.text
                        else:
                            notes += child.text.strip() + "\n"
                        index += 1

                    notes = notes.replace("Notes:\n", "").strip()

                    # Make sure the details of this subject is known to the db
                    subjectdict = {
                        "subject": self.subject,
                        "name": self.fullname,
                        "notes": notes,
                        "instruction": instructioninfo
                    }

                    # Update the subject data in the DB
                    self.super.updateSubject(subjectdict)

                    log.debug("Updated DB subject for " + self.subject)

                    # Iterate the course divs on the page
                    for course in soup.findAll("table", {"bordercolor": "#000000", "bgcolor": "white", "align": "center", "width": "100%"}):
                        self.parseCourse(course)

                else:
                    log.error("Failed to obtain course descriptions for " + self.subject + ", trying again in 10s")
                    time.sleep(10)

        def parseCourse(self, course):
            """
            Parses the HTML div of a course description and updates it in the DB

            :param course: **string** HTML of the course DIV to parse
            """

            # Maps the HTML elements to the dictionary keys
            courseProperties = {
                "coursenum": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnCode'),
                "name": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnTitle'),
                "desc": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnDescription'),
                "hours": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnHours'),
                "prereq": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnPrerequisites'),
                "coreq": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnCorequisites'),
                "antireq": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnAntirequisites'),
                "notes": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnNotes'),
                "aka": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnAKA'),
                "repeat": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnRepeat'),
                "nogpa": re.compile('ctl00_ctl00_pageContent_ctl\d*_ctl\d*_cnNoGpa')
            }

            coursedata = {}

            for property in courseProperties:

                # Get the data of the element
                data = course.find("span", {"id": courseProperties[property]}).text.strip()

                if data:
                    if property == "nogpa" or property == 'repeat':
                        coursedata[property] = True
                    elif property == "hours":
                        if ";" in data:
                            unitval = data.split(";")[0].replace("units", "").replace("unit", "").strip()

                            # Try to convert it to a float
                            try:
                                coursedata["units"] = float(unitval)
                            except:
                                coursedata["units"] = unitval

                            coursedata["hours"] = data.split(";")[1].strip()
                        else:
                            coursedata[property] = data
                    else:
                        coursedata[property] = data

            coursedata["subject"] = self.subject

            # Upsert the data into the DB
            self.super.updateCourseDesc(coursedata)
