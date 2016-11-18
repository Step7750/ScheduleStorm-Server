"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
from uwaterlooapi import UWaterlooAPI
import logging
import time
import pymongo
from datetime import datetime

log = logging.getLogger("UWaterloo")


class UWaterloo(University):
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

    def scrapeCourseList(self, uw, term):
        courseList = []
        for subject in uw.term_courses(term):
            courseInfo = uw.term_subject_schedule(term, subject['subject'])
            for course in courseInfo:
                if len(courseInfo) != 0:
                    courseDict = {'coursenum': subject['catalog_number'], 'subject': subject['subject'], 'term': term,
                                  'id': course['class_number'], 'group': course['class_number'],
                                  'type': course['section'][:3], 'location': course['campus'],
                                  'status': str(course['enrollment_total'])+'/' + str(course['enrollment_capacity'])}

                    for date in courseInfo[0]['classes']:
                        courseDict['rooms'] = [date['location']['building'], date['location']['room']]

                        if date['date']['start_time']:
                            course_start_time = datetime.strptime(date['date']['start_time'], '%H:%M')
                            course_end_time = datetime.strptime(date['date']['end_time'], '%H:%M')
                            courseDict['times'] = [date['date']['weekdays'] + " " + course_start_time.strftime('%I:%M%p') +
                                                   ' - ' + course_end_time.strftime('%I:%M%p')]
                        else:
                            courseDict['times'] = ['N/A']

                        if len(date['instructors']) == 0:
                            courseDict['instructor'] = ['N/A']
                        else:
                            courseDict['instructor'] = date['instructors']
                        courseList.append(courseDict)
                else:
                    courseDict = {'coursenum': subject['catalog_number'], 'subject': subject['subject'], 'term': term,
                                  'id': 'N/A', 'rooms': ['N/A'], 'type': 'N/A', 'location': 'N/A', 'status': 'N/A',
                                  'instructor': ['N/A'], 'group': subject['catalog_number']}
                    courseList.append(courseDict)
                print(courseDict)
                courseDesc = uw.course(subject['subject'], subject['catalog_number'])
                if len(courseDesc) != 0:
                    courseDict = {'coursenum': subject['catalog_number'], 'subject': subject['subject'],
                                  'name': course['title'], 'desc': courseDesc['description'],
                                  'units': course['units'], 'prereq': courseDesc['prerequisites'],
                                  'coreq': courseDesc['corequisites'], 'antireq': courseDesc['antirequisites'],
                                  'notes': course['note']}
                else:
                    courseDict = {'coursenum': subject['catalog_number'], 'subject': subject['subject']}
                self.updateCourseDesc(courseDict)
        self.updateClasses(courseList)

    def scrapeTerms(self, uw):
        log.info("SCraping terms")
        termDictList = []
        terms = uw.terms()
        termList = terms['listings']

        for term in termList:
            for x in range(len(termList[term])):

                if termList[term][x]['id'] == terms['previous_term']:
                    termDict = {'id': terms['previous_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

                elif termList[term][x]['id'] == terms['current_term']:
                    termDict = {'id': terms['current_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

                elif termList[term][x]['id'] == terms['next_term']:
                    termDict = {'id': terms['next_term'], 'name': termList[term][x]['name']}
                    termDictList.append(termDict)

        self.updateTerms(termDictList)
        log.info('Finished scraping terms')

    def updateFaculties(self, uw):
        log.info("Getting faculty list")
        faculties = uw.group_codes()

        for subject in uw.subject_codes():
            subjectDict = {'subject': subject['subject'], 'faculty': '', 'name': subject['description']}
            for faculty in faculties:
                if subject['group'] == faculty['group_code']:
                    subjectDict['faculty'] = faculty['group_full_name']
            self.updateSubject(subjectDict)
        log.info('Finished updating faculties')

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings['scrape']:
            while True:
                try:
                    uw = UWaterlooAPI(api_key=self.settings['api_key'])
                    #print(dir(uw))

                    self.updateFaculties(uw)
                    self.scrapeTerms(uw)
                    terms = self.getTerms()

                    for term in terms:
                        log.info('Obtaining ' + terms[term] + ' course data with id ' + term)
                        self.scrapeCourseList(uw, term)

                    log.info('Finished scraping for UWaterloo data')
                except Exception as e:
                    log.info("There was a critical exception | " + str(e))
                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")