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

    def scrapeCourseList(self, uw, term, subjectList):
        courseList = []

        for subject in subjectList:
            courseInfo = uw.term_subject_schedule(1165, subject['subject'])
            for course in courseInfo:
                for date in course['classes']:
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject'], 'term': 1165,
                                  'id': course['class_number'], 'group': course['class_number'],
                                  'type': course['section'][:3], 'location': course['campus'],
                                  'rooms': [date['location']['building'], date['location']['room']],
                                  'curEnroll': course['enrollment_capacity'], 'capEnroll': course['enrollment_total']}
                    if course['enrollment_total']/course['enrollment_capacity'] >= 1:
                        if course['waiting_capacity'] != 0:
                            courseDict['status'] = 'Wait List'
                            courseDict['waitEnroll'] = course['waiting_total']
                        else:
                            courseDict['status'] = 'Closed'
                    else:
                        courseDict['status'] = 'Open'
                    if date['date']['start_time']:
                        course_start_time = datetime.strptime(date['date']['start_time'], '%H:%M')
                        course_end_time = datetime.strptime(date['date']['end_time'], '%H:%M')
                        courseDict['times'] = [date['date']['weekdays'] + " " + course_start_time.strftime('%I:%M%p') +
                                               ' - ' + course_end_time.strftime('%I:%M%p')]
                    else:
                        courseDict['times'] = ['N/A']

                    if date['instructors']:
                        courseDict['instructor'] = date['instructors']
                    else:
                        courseDict['instructor'] = ['N/A']
                    courseList.append(courseDict)

                courseDesc = uw.course(subject['subject'], course['catalog_number'])
                if len(courseDesc) != 0:
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject'],
                                  'name': course['title'], 'desc': courseDesc['description'],
                                  'units': course['units'], 'prereq': courseDesc['prerequisites'],
                                  'coreq': courseDesc['corequisites'], 'antireq': courseDesc['antirequisites'],
                                  'notes': course['note']}
                else:
                    courseDict = {'coursenum': course['catalog_number'], 'subject': subject['subject']}
                #self.updateCourseDesc(courseDict)
        #self.updateClasses(courseList)

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
        subjectList = []
        for subject in uw.subject_codes():
            subjectDict = {'subject': subject['subject'], 'faculty': '', 'name': subject['description']}

            for faculty in faculties:
                if subject['group'] == faculty['group_code']:
                    subjectDict['faculty'] = faculty['group_full_name']
            subjectList.append(subjectDict)
        self.updateSubjects(subjectList)
        log.info('Finished updating faculties')
        return subjectList

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings['scrape']:
            while True:
                try:
                    uw = UWaterlooAPI(api_key=self.settings['api_key'])

                    subjectList = self.updateFaculties(uw)
                    self.scrapeTerms(uw)
                    terms = self.getTerms()

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