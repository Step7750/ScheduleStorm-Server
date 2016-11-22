"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
import requests
import json
import time
import pymongo
import threading
from datetime import datetime


# Custom UWaterlooAPI request class
class UWaterlooAPI():
    def __init__(self, log, api_key=None, output='.json'):
        self.log = log
        self.api_key = '?key=' + api_key
        self.baseURL = "https://api.uwaterloo.ca/v2"
        self.format = output

    def request(self, path):
        """
        General UWaterloo request function

        :param path: **string** path for get request
        :return: **dict** all info for parsing
        """

        r = requests.get(self.baseURL + path + self.format + self.api_key, timeout=20)

        # Checks id request was successful and returns info to be parsed
        if r.status_code == requests.codes.ok:
            return json.loads(r.text)['data']
        else:
            self.log.debug('Get request failed | ' + self.baseURL + path + self.format + self.api_key)

    def term_subject_schedule(self, term, subject):
        """
        Gets all UWaterloo courses based on term and subject

        :param term: **string** term id
        :param subject: **string** subject abbreviation
        :return: **dict** all info for parsing
        """

        path = '/terms/' + term + '/' + subject + '/schedule'
        return self.request(path)

    def terms(self):
        """
        Gets a list of all UWaterloo terms

        :param term: **string** term id
        :param subject: **string** subject abbreviation
        :return: **dict** all info for parsing
        """

        path = '/terms/list'
        return self.request(path)

    def subject_codes(self):
        """
        Gets all UWaterloo subjects

        :param term: **string** term id
        :param subject: **string** subject abbreviation
        :return: **dict** all info for parsing
        """

        path = '/codes/subjects'
        return self.request(path)

    def group_codes(self):
        """
        Gets all UWaterloo faculties

        :return: **dict** all info for parsing
        """

        path = '/codes/groups'
        return self.request(path)

    def course(self, subject, catalog_number):
        """
        Gets UWaterloo class descriptions based on subject and unique catalog_number

        :param subject: **string** subject abbreviation
        :param catalog_number: **string** unique id number for class
        :return: **dict** all info for parsing
        """

        path = '/courses/' + subject + '/' + catalog_number + ''
        return self.request(path)


class UWaterloo(University):
    def __init__(self, settings):
        super().__init__(settings)
        self.db = pymongo.MongoClient().ScheduleStorm

    def scrapeCourseList(self, uw, term, subjectList):
        """
        Scrape and parsing for courses

        :param uw: **class object** UWaterlooapi class object
        :param term: **string** term id
        :param subjectList: **list** list of all subjects
        :return:
        """

        courseList = []

        # For each subject scrape courses
        for subject in subjectList:

            # Gets all courses based on term and subject
            for course in uw.term_subject_schedule(term, subject['subject']):

                # For each class initialize course dictionary to be upserted
                for date in course['classes']:

                    # initialize course dictionary
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject'], 'term': term,
                                  'id': course['class_number'], 'type': course['section'][:3], 'group': [],
                                  'location': course['campus'], 'curEnroll': course['enrollment_capacity'],
                                  'rooms': [date['location']['building'], date['location']['room']],
                                  'capEnroll': course['enrollment_total'], 'capwaitEnroll': course['waiting_capacity']}

                    # Checks if class is open, closed, or has a waiting list
                    if course['enrollment_capacity'] != 0 and course['enrollment_total']/course['enrollment_capacity'] >= 1:

                        # Checks waiting list and closed status
                        if course['waiting_capacity'] != 0:
                            courseDict['status'] = 'Wait List'
                            courseDict['waitEnroll'] = course['waiting_total']
                        else:
                            courseDict['status'] = 'Closed'
                    else:
                        courseDict['status'] = 'Open'

                    # Checks to see if class has a start and end time
                    if date['date']['start_time']:
                        course_start_time = datetime.strptime(date['date']['start_time'], '%H:%M')
                        course_end_time = datetime.strptime(date['date']['end_time'], '%H:%M')
                        courseDict['times'] = [date['date']['weekdays'] + " " + course_start_time.strftime('%I:%M%p') +
                                               ' - ' + course_end_time.strftime('%I:%M%p')]
                    else:
                        courseDict['times'] = ['N/A']

                    # Checks for assigned teacher
                    if date['instructors']:
                        teacher = date['instructors'][0].split(',')
                        courseDict['teachers'] = [teacher[1] + ' ' + teacher[0]]
                    else:
                        courseDict['teachers'] = ['N/A']

                    if course['note'] == "Choose TUT section for Related 1." and (courseDict['type'] == 'LEC' or courseDict['type'] == 'TUT'):
                        courseDict['group'].append('99')
                        if courseDict['type'] == 'LEC' and course['related_component_2']:
                            courseDict['group'].append(course['related_component_2'])
                    elif course['note'] == "Choose SEM section for Related 1." and (courseDict['type'] == 'LEC' or courseDict['type'] == 'SEM'):
                        courseDict['group'].append('99')
                        if courseDict['type'] == 'LEC' and course['related_component_2']:
                            courseDict['group'].append(course['related_component_2'])
                    else:
                        if course['associated_class'] != 99:
                            courseDict['group'].append(str(course['associated_class']))
                        else:
                            courseDict['group'].append(course['section'][4:])

                        if course['related_component_1'] and course['related_component_1'] != "99":
                            courseDict['group'].append(str(course['related_component_1']))

                        if course['related_component_2']:
                            courseDict['group'].append(str(course['related_component_2']))
                    courseList.append(courseDict)

                if not self.getCourseDescription(courseDict['coursenum'], courseDict['subject']):
                    threadm = CourseDescriptions(subject['subject'], course['catalog_number'], super(), uw)
                    threadm.setDaemon(True)
                    threadm.start()

        # Upserts class list
        self.updateClasses(courseList)

    def scrapeTerms(self, uw):
        """
        Scrapes and parses terms

        :param uw: **class object** UWaterlooapi class object
        :return:
        """

        self.log.info("Scraping terms")
        termDictList = []

        # Gets all terms recorded in UWaterlooAPI
        terms = uw.terms()
        termList = terms['listings']

        # For each term find previous, current, and next term
        for term in termList:
            for x in range(len(termList[term])):

                # Checks for previous term
                if termList[term][x]['id'] == terms['previous_term']:
                    termDict = {'id': terms['previous_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

                # Checks for current term
                elif termList[term][x]['id'] == terms['current_term']:
                    termDict = {'id': terms['current_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

                # Checks for next term
                elif termList[term][x]['id'] == terms['next_term']:
                    termDict = {'id': terms['next_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

        # Upserts all terms to be scraped
        self.updateTerms(termDictList)
        self.log.info('Finished scraping terms')

    def updateFaculties(self, uw):
        """
        Scrapes and parses faculties

        :param uw: **class object** UWaterlooapi class object
        :return subjectList: **list** list of all UWaterloo subjects
        """
        self.log.info("Getting faculty list")

        # Gets all faculty info
        faculties = uw.group_codes()
        subjectList = []

        # For each subject match faculty
        for subject in uw.subject_codes():
            subjectDict = {'subject': subject['subject'], 'faculty': '', 'name': subject['description']}

            for faculty in faculties:
                if subject['group'] == faculty['group_code']:
                    subjectDict['faculty'] = faculty['group_full_name']
            subjectList.append(subjectDict)

        # Upserts all subjects at once
        self.updateSubjects(subjectList)
        self.log.info('Finished updating faculties')

        # Returns a list of all subjects for future use
        return subjectList

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings['scrape']:
            while True:
                try:
                    # Initializes UWaterlooAPI class
                    uw = UWaterlooAPI(self.log, api_key=self.settings['api_key'])

                    # Scrapes faculties and terms
                    subjectList = self.updateFaculties(uw)
                    self.scrapeTerms(uw)
                    terms = self.getTerms()

                    # For each term scrape course info
                    for term in terms:
                        self.log.info('Obtaining ' + terms[term] + ' course data with id ' + term)
                        self.scrapeCourseList(uw, term, subjectList)

                    self.log.info('Finished scraping for UWaterloo data')
                except Exception as e:
                    self.log.info("There was a critical exception | " + str(e))
                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            self.log.info("Scraping is disabled")


class CourseDescriptions(threading.Thread):
    """
        Mines course descriptions from the UWaterloo api given the subject and coursenum
    """
    def __init__(self, subject, coursenum, parent, uw):
        threading.Thread.__init__(self)
        self.super = parent
        self.subject = subject
        self.coursenum = coursenum
        self.uw = uw

    def run(self):
        # Gets class description
        courseDesc = self.uw.course(self.subject, self.coursenum)
        if len(courseDesc) != 0:
            courseDict = {'coursenum': self.coursenum, 'subject': self.subject,
                          'name': courseDesc['title'], 'desc': courseDesc['description'],
                          'units': courseDesc['units'], 'prereq': courseDesc['prerequisites'],
                          'coreq': courseDesc['corequisites'], 'antireq': courseDesc['antirequisites']}
            if courseDesc['notes']:
                note = courseDesc['notes'][7:]
                note = note[:-1]
                courseDict['notes'] = note
        else:
            courseDict = {'coursenum': self.coursenum, 'subject': self.coursenum}

        # Upserts class descriptions
        self.super.updateCourseDesc(courseDict)