# -*- coding: utf-8 -*-
"""
Grading

"""

#these are the packages you need to install, this will try to install them, otherwise use pip to install
import time, getpass, requests, pandas as pd, json

class Helper:
    def paginate_list(sub_list, token):
        json_list = pd.read_json(sub_list.text)
        try:
            while sub_list.links['current']['url'] != sub_list.links['last']['url']:
                sub_list =  requests.get(sub_list.links['next']['url'],
                                 headers= {'Authorization': 'Bearer ' + token})
                admin_sub_table = pd.read_json(sub_list.text)
                json_list= pd.concat([json_list, admin_sub_table], sort=True)
                json_list=json_list.reset_index(drop=True)
        except KeyError:
            if sub_list.links['next'] is not None:
                sub_list =  requests.get(sub_list.links['next']['url'],
                            headers= {'Authorization': 'Bearer ' + token})
                admin_sub_table = Helper.paginate_list(sub_list, token)
                json_list= pd.concat([json_list, admin_sub_table], sort=True)
                json_list=json_list.reset_index(drop=True)

        return json_list

now = time.strftime("%c")
## date and time representation
filename = time.strftime("%c") + ".txt"

# ENTER THE FOLLOWING INFORMATION
token = getpass.getpass("Enter your token: ")

#course url
url = "https://canvas.ubc.ca"

#course number
course = input("Enter Canvas course ID: ")

#the assignment ID number
assignment_id = input("Enter Canvas assignment ID: ")

#get the assignment information
assignmentInfo = requests.get(url + '/api/v1/courses/' + str(course) + '/assignments/' + assignment_id,
                 headers= {'Authorization': 'Bearer ' + token})

#get the assignment rubric id for the assignment
assignmentInfo = json.loads(assignmentInfo.text)
rubric_id = str(assignmentInfo['rubric_settings']['id'])

#the assessment will return a list of assessments with rubric
# the artifact_id = the assignment id of the assignmentSubmissions
# the assessor_id = the person who assessed the assignment
# the score = the total score (sum of rubric points)
payload = {'include': 'peer_assessments',
           'style' : 'full'}
r = requests.get(url + '/api/v1/courses/' + str(course) + '/rubrics/' + rubric_id,
                 params = payload,
                 headers= {'Authorization': 'Bearer ' + token})

rubric_return = json.loads(r.text)

index = 0
for value in rubric_return['assessments']:
    to_delete = value['rubric_association']
    del to_delete['summary_data']

#artifact_id, artifact_type, assessor_id, score
assessments_df = pd.DataFrame(rubric_return['assessments'])

#peer review information
peerReview = requests.get(url + '/api/v1/courses/' + str(course) + '/assignments/' + assignment_id + '/peer_reviews',
                 headers= {'Authorization': 'Bearer ' + token})

peerReviewInfo = json.loads(peerReview.text)
peerReview_df = pd.read_json(peerReview.text)

peerReview_df['user_id'] = peerReview_df['user_id'].astype(str)

merged_df = pd.merge(peerReview_df, assessments_df, how='inner', left_on=['assessor_id', 'asset_id'], right_on=['assessor_id', 'artifact_id'])

#Get student list
student_list = requests.get('{}/api/v1/courses/{}/users'.format(url, course),
                            params = {'enrollment_type[]': 'student'},
                            headers = {'Authorization': 'Bearer ' + token})

no_student_id = False
if student_list.ok:
    student_df = Helper.paginate_list(student_list, token)
    student_df.to_csv('testing.csv')
    try:
        student_df = student_df[['id', 'name', 'sis_user_id']]
    except:
        student_df = student_df[['id', 'name']]
        no_student_id = True
    
    student_df.to_csv('testing.csv')
else:
    print(student_list)
    print("Not allowed.")

merged_df = pd.merge(merged_df, student_df, how='inner', left_on=['assessor_id'], right_on=['id'])
if(no_student_id):
    merged_df = merged_df.rename(columns={"name":"assessor_name"}).drop(['id'], axis=1)
else:
    merged_df = merged_df.rename(columns={"name":"assessor_name", "sis_user_id":"assessor_sis_id"}).drop(['id'], axis=1)

merged_df = pd.merge(merged_df, student_df, how='inner', left_on=['user_id'], right_on=['id'])
if(no_student_id):
    merged_df = merged_df.rename(columns={"name":"user_name"}).drop(['id'], axis=1)
    column_list = merged_df.columns.tolist()
    column_list = column_list[0:1] + column_list[-2:-1] + column_list[1:5] + column_list[-1:] + column_list[5:-2] 
else:
    merged_df = merged_df.rename(columns={"name":"user_name", "sis_user_id":"user_sis_id"}).drop(['id'], axis=1)
    column_list = merged_df.columns.tolist()
    column_list = column_list[0:1] + column_list[-4:-2] + column_list[1:5] + column_list[-2:] + column_list[5:-4]

merged_df = merged_df[column_list]

#merge the peerReview_df and the assessments_df by the assessor_id and asset_id
# in assessments df the assessor_id and artifact_id
# in the peer review df the assessor_id and asset_id
merged_df.to_csv('{}_peer review information.csv'.format(course), index=False)

#create the meanscore table with user_id and mean score
# make sure the mean score is rounded to 2, and the user_id is a string
meanScore = pd.DataFrame(merged_df.groupby('user_id')['score'].mean().round(2).reset_index())
meanScore = meanScore[pd.notnull(meanScore['score'])]
meanScore['user_id'] = meanScore['user_id'].astype(str)
meanScore.to_csv("course_" + course + "_" + "assignment_" + assignment_id + '_complete mean score.csv')
#f.write("course_" + course + "_" + "assignment_" + assignment_id + '_complete mean score.csv' + "file created \n")

#whether to upload the data to the gradebook = True OR not = False
upload = False
#upload mean score to GradeCentre
if upload==True:
    #f.write("data should be uploaded to gc \n")
    for index, row in meanScore.iterrows():

        student_id = str(row['user_id'])
        print(student_id)
        score = str(row['score'])

        #print(student_id, score)

        comment = 'this is a test to find mean score of peer reviews'

        payload = {'comment[text_comment]': comment,
                   'submission[posted_grade]': score}

        r = requests.put(url + '/api/v1/courses/' + str(course) + '/assignments/' + str(assignment_id) +'/submissions/' + str(student_id) + '/', params=payload, headers= {'Authorization': 'Bearer ' + token})
else:
    print('data not uploaded')
    #f.write("data not uploaded")

#f.close()
