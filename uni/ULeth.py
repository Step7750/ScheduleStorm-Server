"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""
from .University import University
from bs4 import BeautifulSoup
import time
import requests
import traceback

class ULeth(University):
    def __init__(self, settings):
        super().__init__(settings)

    def parseWebTerms(self, html):
        """
        Parses the HTML for the term selection web page and returns a dict of applicable terms

        :param html: **String** HTML DOM of the term selection page
        :return: **dict** Every Non-"View Only" term and the most recent view only term
        """
        soup = BeautifulSoup(html, "lxml")

        terms = []

        view_only_amount = 0

        for term in soup.find("select", {"id": "term_input_id"}).findAll("option"):
            value = term['value']

            # Allow the term if its not view only or there are no view only terms so far
            if value and "View only" in term.text:
                view_only_amount += 1
                if view_only_amount > 1:
                    break

            if value:
                this_term = {"id": value, "name": term.text.replace("(View only)", "").strip()}
                terms.append(this_term)

        return terms

    def getWebTerms(self):
        """
        Retrieves and returns a dict of the terms and their ids

        :return: **list** Term objects
        """
        r = requests.get("https://www.uleth.ca/bridge/bwckschd.p_disp_dyn_sched")

        if r.status_code == requests.codes.ok:
            return self.parseWebTerms(r.text)
        else:
            return False

    def parseWebSubjects(self, html):
        """
        Parses the web subject HTML and returns a list of subject objects

        :param html: **String** HTML of the subject page
        :return: **list** Subject objects
        """
        soup = BeautifulSoup(html, "lxml")

        subjects = []

        for subject in soup.find("select", {"id": "subj_id"}).findAll("option"):
            subjects.append({"subject": subject["value"], "name": subject.text.strip()})

        return subjects

    def getWebSubjects(self, term_id):
        """
        Retrieves and returns the subjects for the given term

        :param term_id: **String** ID of the term to retrieve subjects for
        :return:
        """
        post_data = {
            "p_calling_proc": "bwckschd.p_disp_dyn_sched",
            "p_term": term_id
        }

        r = requests.post("https://www.uleth.ca/bridge/bwckgens.p_proc_term_date", data=post_data)

        if r.status_code == requests.codes.ok:
            return self.parseWebSubjects(r.text)
        else:
            return False

    def getWebSubjectClasses(self, subj, term_id):
        """
        Retrieves the HTML DOM for the class page for the given term and subject

        :param subj: **String** Subject code to retrieve classes for
        :param term_id: **String** Term ID to retrieve classes for
        :return: **String** HTML of the class page
        """
        post_data = "term_in=" + term_id +  \
                    "&sel_subj=dummy" \
                    "&sel_day=dummy" \
                    "&sel_schd=dummy" \
                    "&sel_insm=dummy" \
                    "&sel_camp=dummy" \
                    "&sel_levl=dummy" \
                    "&sel_sess=dummy" \
                    "&sel_instr=dummy" \
                    "&sel_ptrm=dummy" \
                    "&sel_attr=dummy" \
                    "&sel_subj=" + subj + \
                    "&sel_crse=" \
                    "&sel_title=" \
                    "&sel_insm=%25" \
                    "&sel_from_cred=" \
                    "&sel_to_cred=" \
                    "&sel_camp=%25" \
                    "&sel_ptrm=%25" \
                    "&sel_instr=%25" \
                    "&sel_attr=%25" \
                    "&begin_hh=0" \
                    "&begin_mi=0" \
                    "&begin_ap=a" \
                    "&end_hh=0" \
                    "&end_mi=0" \
                    "&end_ap=a"

        r = requests.post("https://www.uleth.ca/bridge/bwckschd.p_get_crse_unsec", data=post_data)

        if r.status_code == requests.codes.ok:
            return r.text
        else:
            return False

    def parseClassHTML(self, html, term_id):
        """
        Parses the class list HTML and updates the DB

        :param html: **String** HTML of the class lst
        :param term_id: **String** Term id that was used to fetch this data
        :return:
        """
        soup = BeautifulSoup(html, "lxml")


        section_table = soup.find("table", {"class": "datadisplaytable"})

        index = 0

        current_class = {"term": term_id, "rooms": [], "teachers": [], "times": [], "group": ["1"], "status": "Open"}

        for tr in section_table.findAll("tr", recursive=False):
            if index % 2 == 0:
                if index > 0:
                    # We've found a new class, update the old one in the DB
                    self.updateClass(current_class)
                    current_class = {"term": term_id, "rooms": [], "teachers": [], "times": [], "group": ["1"], "status": "Open"}

                # Process the title and get data
                title = tr.text.strip().split(" - ")
                current_class["section"] = title[-1].strip()
                current_class["subject"] = title[-2].split(" ")[0].strip()
                current_class["coursenum"] = title[-2].split(" ")[1].strip()
                current_class["id"] = int(title[-3].replace("-", "").strip())

                # Name of the course
                name = " ".join(title[0:len(title)-3])

                # Ex. CPSC 3500, ensure its not in the title (indicates its a lab or something)
                course_name = current_class["subject"] + " " + current_class["coursenum"]

                if len(title) > 3 and course_name not in name:
                    # update the course description with this title
                    course_desc = {"name": name,
                                   "coursenum": current_class["coursenum"],
                                   "subject": current_class["subject"]}

                    self.updateCourseDesc(course_desc)

            else:
                # this is a class
                td = tr.find("td", recursive=False)

                # find the location
                for attribute in td.text.split("\n"):
                    if "Campus" in attribute:
                        # found location
                        current_class["location"] = attribute
                        break

                class_table = td.find("table", {"class": "datadisplaytable"})

                if not class_table:
                    # there are no times etc.. for this class
                    current_class["rooms"] = ["N/A"]
                    current_class["teachers"] = ["N/A"]
                    current_class["times"] = ["N/A"]
                    current_class["rooms"] = ["N/A"]
                    current_class["type"] = "N/A"
                else:
                    # proper class table

                    row_index = 0

                    # Go through each row in the table
                    for row in class_table.findAll("tr"):
                        # we don't want the first row
                        if row_index > 0:
                            column_index = 0
                            this_time = ""

                            # For each column in this row, add to the current class
                            for column in row.findAll("td"):
                                column = column.text.strip()

                                # Based upon the index, perform dict operations
                                if column_index == 1:
                                    column = column.replace(" pm", "PM").replace(" am", "AM")
                                    this_time = column
                                elif column_index == 2:
                                    this_time = column + " " + this_time
                                elif column_index == 3:
                                    current_class["rooms"].append(column)
                                elif column_index == 5:
                                    acronym = self.typeNameToAcronym(column)

                                    if acronym:
                                        current_class["type"] = acronym
                                    else:
                                        current_class["type"] = column
                                elif column_index == 6:
                                    column = column.replace(" (P)", "").replace("\xa0", " ")
                                    teachers = column.split(", ")

                                    for teacher in teachers:
                                        # reverse the name since it is currently LASTNAME MIDDLE FIRSTNAME
                                        # We want it to be FIRSTNAME MIDDLE LASTNAME
                                        teacher = teacher.strip().split(" ")

                                        # First word is the last
                                        format_teacher = teacher[len(teacher)-1]

                                        if len(teacher) > 1:
                                            format_teacher += " " + " ".join(teacher[0:len(teacher)-1])

                                        current_class["teachers"].append(format_teacher)

                                column_index += 1
                            current_class["times"].append(this_time)

                        row_index += 1
            index += 1

    def updateClassDescriptions(self):
        """
        Obtains the class descriptions and updates the DB

        :return:
        """
        description_map = {
            "title": "name",
            "credithours": "units",
            "contacthours": "hours",
            "description": "desc",
            "grading": "grading",
            "prerequisites": "prereq",
            "corequisites": "coreq",
            "note": "notes",
            "equivalent": "aka"
        }

        subject_abbreviations = {}

        self.log.info("Obtaining course descriptions")

        r = requests.get("https://www.uleth.ca/ross/sites/ross/files/imported/courses/courses.xml")

        if r.status_code == requests.codes.ok:

            self.log.info("Parsing course descriptions")

            soup = BeautifulSoup(r.text, "lxml")

            # for every course
            for course in soup.findAll("course"):

                # stores this course description
                course_desc = {}

                children = course.findChildren()

                for child in children:
                    text = child.text.strip()

                    if child.name == "subjectandnumber":
                        # Format: Computer Science XXXX
                        name_split = child.text.split(" ")

                        # Get XXXX
                        course_desc["coursenum"] = name_split[-1]

                        # C Get Computer Science
                        subject = " ".join(name_split[0:len(name_split)-1]).strip()

                        if subject not in subject_abbreviations:
                            subject_obj = {"name": subject}

                            # Get the full subject obj that corresponds to this name
                            full_obj = self.getSubject(subject_obj)

                            if full_obj:
                                # add it to the lookup
                                subject_abbreviations[subject] = full_obj["subject"]

                        # get the subject abbreviation if its in the dict
                        if subject in subject_abbreviations:
                            course_desc["subject"] = subject_abbreviations[subject]
                    else:
                        # if the key is in the map, add it to the course desc
                        if child.name in description_map:
                            course_desc[description_map[child.name]] = text

                if "subject" in course_desc:
                    # update the db
                    self.updateCourseDesc(course_desc)

        else:
            self.log.error("Failed to obtain course descriptions")

    def scrape(self):
        """
        Scrapes and updates the DB with updated course info

        :return:
        """
        # Get the terms
        terms = self.getWebTerms()

        if terms:
            # Update the terms in the DB
            self.updateTerms(terms)

            for term in terms:
                # Get the subjects for this term
                term_id = term["id"]

                self.log.info("Scraping class data for " + str(term_id))

                # Get the subject list for this term
                subjects = self.getWebSubjects(term_id)

                # update the subjects in the DB
                self.updateSubjects(subjects)

                # For each subject, get the class data
                for subject in subjects:
                    classes = self.getWebSubjectClasses(subject["subject"], term_id)
                    self.parseClassHTML(classes, term_id)

                self.log.info("Done scraping class data for " + str(term_id))

            self.updateClassDescriptions()

        self.log.info("Done scraping")

