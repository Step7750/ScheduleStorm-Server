"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
import requests
import json
import logging
import time
import pymongo
from datetime import datetime

log = logging.getLogger("UWaterloo")


# Custom UWaterlooAPI request class
class UWaterlooAPI():
    def __init__(self, api_key=None, output='.json'):
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
            log.debug('Get request failed | ' + self.baseURL + path + self.format + self.api_key)

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
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

    def scrapeCourseList(self, uw, term, subjectList):
        """
        Scrape and parsing for courses and class descriptions

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
                                  'id': course['class_number'], 'group': course['class_number'],
                                  'type': course['section'][:3], 'location': course['campus'],
                                  'rooms': [date['location']['building'], date['location']['room']],
                                  'curEnroll': course['enrollment_capacity'], 'capEnroll': course['enrollment_total'],
                                  'capwaitEnroll': course['waiting_capacity']}

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

                    if date['instructors']:
                        courseDict['teachers'] = date['instructors']
                    else:
                        courseDict['teachers'] = ['N/A']
                    courseList.append(courseDict)

                # Gets class description
                courseDesc = uw.course(subject['subject'], course['catalog_number'])
                if len(courseDesc) != 0:
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject'],
                                  'name': course['title'], 'desc': courseDesc['description'],
                                  'units': course['units'], 'prereq': courseDesc['prerequisites'],
                                  'coreq': courseDesc['corequisites'], 'antireq': courseDesc['antirequisites'],
                                  'notes': course['note']}
                else:
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject']}

                # Upserts class descriptions
                self.updateCourseDesc(courseDict)

        # Upserts class list
        self.updateClasses(courseList)

    def scrapeTerms(self, uw):
        """
        Scrapes and parses terms

        :param uw: **class object** UWaterlooapi class object
        :return:
        """

        log.info("Scraping terms")
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
        log.info('Finished scraping terms')

    def updateFaculties(self, uw):
        """
        Scrapes and parses faculties

        :param uw: **class object** UWaterlooapi class object
        :return subjectList: **list** list of all UWaterloo subjects
        """
        log.info("Getting faculty list")

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
        log.info('Finished updating faculties')

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
                    uw = UWaterlooAPI(api_key=self.settings['api_key'])

                    # Scrapes faculties and terms
                    subjectList = self.updateFaculties(uw)
                    self.scrapeTerms(uw)
                    terms = self.getTerms()

                    # For each term scrape course info
                    for term in terms:
                        log.info('Obtaining ' + terms[term] + ' course data with id ' + term)
                        self.scrapeCourseList(uw, term, subjectList)

                    log.info('Finished scraping for UWaterloo data')
                except Exception as e:
                    log.info("There was a critical exception | " + str(e))
                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")