# ScheduleStorm_Server
University Schedule Generator http://schedulestorm.com


## Rough DB Schema

UCalgary implements the following DB structure in MongoDB

I will add what the optional values are soon...

### UniversityCourseList

Contains the classes objs (DOES NOT INCLUDE CLASS DESCRIPTIONS, SEE COURSEDESC)

ex.
```json
UCalgaryCourseList
{
	"subject": "CPSC",
	"type": "LAB",
	"scheduletype": "Regular",
	"coursenum": "101",
	"id": 70349,
	"term": 2179,
	"times": ["Fr 9:00AM - 11:50AM", "Fr 1:00PM - 3:50PM"],
	"location": "Main UofC Campus",
	"rooms": ["ST 135", "ST 135"],
	"teachers": ["Staff", "Syed Zain Raza Rizvi"],
	"group": "1",
	"status": "Closed",
	"restrictions": true,
	"notes": "Notes: This is a combined section class",
	"lastupdated": 23423432
}
```

### UniversityCourseDesc
Includes the course descriptions

ex.
```javascript
{
	"coursenum": "101",
	"subject": "CPSC",
	"name": "Introduction To Unix",
	"desc": "An introduction to the Unix operating system, including the text editor \"emacs,\" its programming modes and macros; shell usage (including \"sh\" and \"tcsh\"); and some advanced Unix commands.",
	"notes": "This course is highly recommended as preparation for Computer Science 217 or 231 or 235.",
	"nogpa": false,
	"repeat": true, // can repeat it for GPA
	"antirequisites": "Credit for Computer Science 217 and any of 215, 231, 235 or Computer Engineering 339 or Engineering 233 will not be allowed.",
	"prerequisite": "Computer Science 217.",
	"corequisites": "",
	"units": 3.0,
	"hours": "H(2-2)",
	"aka": "",
	"lastupdated": 23423432
}
```

### UniversitySubjects

Contains the numerous subjects and their descriptions. Not all Universities will have a good source for faculties. If so, omit that field.

ex.
```json
{
	"subject": "CPSC",
	"name": "Computer Science",
	"notes": "Computer Science students should also see courses listed under Software Engineering.",
	"faculty": "Faculty of Science",
	"instruction": "Instruction offered by members of the Department of Computer Science in the Faculty of Science."
}
```
