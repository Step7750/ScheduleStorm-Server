"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
import requests
import json
import time
import threading
from datetime import datetime


# Custom UWaterlooAPI request class
class UWaterlooAPI:
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

        :return: **dict** all info for parsing
        """

        path = '/terms/list'
        return self.request(path)

    def subject_codes(self):
        """
        Gets all UWaterloo subjects

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

    def course_id(self, course_id):
        """
        Gets UWaterloo course descriptions based on unique course_id

        :param course_id: **string** unique number assigned to a course
        :return: **dict** all info for parsing
        """

        path = '/courses/' + course_id
        return self.request(path)

    def courses(self, subject):
        """
        Gets UWaterloo class descriptions based on subject and unique catalog_number

        :param subject: **string** subject abbreviation
        :return: **dict** all info for parsing
        """

        path = '/courses/' + subject
        return self.request(path)


class UWaterloo(University):
    def __init__(self, settings):
        super().__init__(settings)

    def scrapeCourseList(self, uw, term, subjectList):
        """
        Scrape and parsing for courses

        :param uw: **class object** UWaterlooapi class object
        :param term: **string** term id
        :param subjectList: **list** list of all subjects
        :return:
        """

        self.log.info('Scraping classes')
        prevClass = ''
        startType = ''
        courseList = []
        # For each subject scrape courses
        for subject in subjectList:
            # Gets all courses based on term and subject
            for course in uw.term_subject_schedule(term, subject['subject']):

                if course['catalog_number'] != prevClass or prevClass == '':
                    group = []
                    # initialize course dictionary
                courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject'],
                              'term': term,
                              'id': course['class_number'], 'type': course['section'][:3], 'group': [],
                              'location': course['campus'], 'curEnroll': course['enrollment_capacity'],
                              'rooms': [course['classes'][0]['location']['building'], course['classes'][0]['location']['room']],
                              'capEnroll': course['enrollment_total'], 'capwaitEnroll': course['waiting_capacity'],
                              'section': course['section'][4:], 'times': ['N/A']}


                # For each class initialize course dictionary to be upserted
                for date in course['classes']:

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
                        if courseDict['times'][0] == 'N/A':
                            courseDict['times'].pop()
                        course_start_time = datetime.strptime(date['date']['start_time'], '%H:%M')
                        course_end_time = datetime.strptime(date['date']['end_time'], '%H:%M')
                        courseDict['times'].append(date['date']['weekdays'] + " " +
                                                   course_start_time.strftime('%I:%M%p') + ' - ' +
                                                   course_end_time.strftime('%I:%M%p'))

                    # Checks for assigned teacher
                    if date['instructors']:
                        teacher = date['instructors'][0].split(',')
                        courseDict['teachers'] = [teacher[1] + ' ' + teacher[0]]
                    else:
                        courseDict['teachers'] = ['N/A']

                    if prevClass != courseDict['coursenum'] or (prevClass == courseDict['coursenum'] and courseDict['type'] == startType):
                        startType = courseDict['type']
                        group.append(course['associated_class'])
                        courseDict['group'].append(course['associated_class'])
                    else:
                        if int(course['associated_class']) != 99:
                            courseDict['group'].append(course['associated_class'])
                        else:
                            courseDict['group'] = group

                    prevClass = courseDict['coursenum']
                    courseList.append(courseDict)

        # Upserts class list
        self.updateClasses(courseList)

    def scrapeCourseDesc(self, subjectList, uw):
        """
        Cycles through the subjectlist scraping course descriptions

        :param subjectList: **List** list of all subjects
        :param uw: **Class Object** UWaterlooapi class object
        :return:
        """
        self.log.info("Scraping course descriptions")

        for subject in subjectList:
            for course in uw.courses(subject['subject']):
                if not self.getCourseDescription(course['catalog_number'], course['subject']):
                    threadm = CourseDescriptions(course['course_id'], super(), uw)
                    threadm.setDaemon(True)
                    threadm.start()

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

    def scrape(self):
        """
        Scraping function that obtains updated course info

        :return:
        """
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
            self.scrapeCourseDesc(subjectList, uw)

        self.log.info('Finished scraping for UWaterloo data')


class CourseDescriptions(threading.Thread):
    """
        Mines course descriptions from the UWaterloo api given the subject and coursenum
    """
    def __init__(self, course, parent, uw):
        threading.Thread.__init__(self)
        self.super = parent
        self.course = course
        self.uw = uw

    def run(self):
        # Gets class description
        courseDesc = self.uw.course_id(self.course)

        if len(courseDesc) != 0:
            courseDict = {'coursenum': courseDesc['catalog_number'], 'subject':  courseDesc['subject'],
                          'name': courseDesc['title'], 'desc': courseDesc['description'],
                          'units': courseDesc['units'], 'prereq': courseDesc['prerequisites'],
                          'coreq': courseDesc['corequisites'], 'antireq': courseDesc['antirequisites']}
            if courseDesc['notes']:
                note = courseDesc['notes'][7:]
                note = note[:-1]
                courseDict['notes'] = note
        else:
            courseDict = {'coursenum': courseDesc['catalog_number'], 'subject': courseDesc['subject']}

        # Upserts class descriptions
        self.super.updateCourseDesc(courseDict)
