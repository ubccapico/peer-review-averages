# -*- coding: utf-8 -*-
"""
Peer Review average script.

Author(s): Victor S., Jeremy H.

"""

#these are the packages you need to install, this will try to install them, otherwise use pip to install
import getpass, requests, pandas as pd, json

class Helper:
    #Helper function deals with pagination
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

if __name__ == '__main__':
    # ENTER THE FOLLOWING INFORMATION
    token = getpass.getpass("Enter your token: ")
    
    #course url
    url = "https://canvas.ubc.ca"
    
    #course number
    course = input("Enter Canvas course ID: ")
    
    #the assignment ID number
    assignment_id = input("Enter Canvas assignment ID: ")
    
    #get the assignment information
    print("Please wait (1/4). Gathering assignment information...")
    assignmentInfo = requests.get(url + '/api/v1/courses/' + str(course) + '/assignments/' + assignment_id,
                     headers= {'Authorization': 'Bearer ' + token})
    
    if not assignmentInfo.ok:
        input("Aborted, failed to get assignment information, {}. Press any key to exit: ".format(assignmentInfo))
        exit()
    
    #get the assignment rubric id for the assignment
    assignmentInfo = json.loads(assignmentInfo.text)
    rubric_id = str(assignmentInfo['rubric_settings']['id'])
    
    #the assessment will return a list of assessments with rubric
    # the artifact_id = the assignment id of the assignmentSubmissions
    # the assessor_id = the person who assessed the assignment
    # the score = the total score (sum of rubric points)
    print("Please wait (2/4). Gathering peer reviews...")
    payload = {'include': 'peer_assessments',
               'style' : 'full'}
    r = requests.get(url + '/api/v1/courses/' + str(course) + '/rubrics/' + rubric_id,
                     params = payload,
                     headers= {'Authorization': 'Bearer ' + token})
    if not r.ok:
        input("Aborted, failed to gather peer reviews, {}. Press any key to exit: ".format(r))
        exit()
    
    rubric_return = json.loads(r.text)
    
    index = 0
    for value in rubric_return['assessments']:
        to_delete = value['rubric_association']
        del to_delete['summary_data']
    
    #artifact_id, artifact_type, assessor_id, score
    assessments_df = pd.DataFrame(rubric_return['assessments'])
    
    #peer review information
    peerReview = requests.get(url + '/api/v1/courses/' + str(course) + '/assignments/' + assignment_id + '/peer_reviews',
                              params ={'include[]': 'submission_comments'},
                              headers= {'Authorization': 'Bearer ' + token})
    
    if not peerReview.ok:
        input("Aborted, failed to gather peer reviews, {}. Press any key to exit: ".format(peerReview))
        exit()
    
    peerReviewInfo = json.loads(peerReview.text)
    peerReview_df = pd.read_json(peerReview.text)
    
    #Merge two dataframes to provide combined data on peer review
    merged_df = pd.merge(peerReview_df, assessments_df, how='left', left_on=['assessor_id', 'asset_id'], right_on=['assessor_id', 'artifact_id'])
    
    #Get student list
    print("Please wait (3/4). Gathering student information...")
    student_list = requests.get('{}/api/v1/courses/{}/users'.format(url, course),
                                params = {'enrollment_type[]': 'student'},
                                headers = {'Authorization': 'Bearer ' + token})
    
    #Decides whether SIS student ID data is missing
    no_student_id = False
    if student_list.ok:
        student_df = Helper.paginate_list(student_list, token)
        try:
            student_df = student_df[['id', 'name', 'sis_user_id']]
        except:
            student_df = student_df[['id', 'name']]
            no_student_id = True
    else:
        print(student_list)
        input("Aborted, cannot get student data, {}. Press any key to exit: ".format(student_list))
        exit()
    
    #Merge 
    merged_df = pd.merge(merged_df, student_df, how='left', left_on=['assessor_id'], right_on=['id'])
    if(no_student_id):
        merged_df = merged_df.rename(columns={"name":"assessor_name"}).drop(['id'], axis=1)
    else:
        merged_df = merged_df.rename(columns={"name":"assessor_name", "sis_user_id":"assessor_sis_id"}).drop(['id'], axis=1)
    
    
    merged_df = pd.merge(merged_df, student_df, how='inner', left_on=['user_id'], right_on=['id'])
    if(no_student_id):
        merged_df = merged_df.rename(columns={"name":"user_name"}).drop(['id'], axis=1)
        column_list = merged_df.columns.tolist()
        column_list = column_list[0:1] + column_list[-2:-1] + column_list[1:6] + column_list[-1:] + column_list[6:-2] 
    else:
        merged_df = merged_df.rename(columns={"name":"user_name", "sis_user_id":"user_sis_id"}).drop(['id'], axis=1)
        column_list = merged_df.columns.tolist()
        column_list = column_list[0:1] + column_list[-4:-2] + column_list[1:6] + column_list[-2:] + column_list[6:-4]
    
    merged_df = merged_df[column_list]
    
    #merge the peerReview_df and the assessments_df by the assessor_id and asset_id
    # in assessments df the assessor_id and artifact_id
    # in the peer review df the assessor_id and asset_id
    merged_df.to_csv('{}_peer review information.csv'.format(course), index=False)
    
    #create the meanscore table with user_id and mean score
    # make sure the mean score is rounded to 2, and the user_id is a string
    print("Please wait (4/4). Calculating averages...")
    meanScore = pd.DataFrame(merged_df.groupby('user_id')['score'].mean().round(2).reset_index())
    meanScore = meanScore[pd.notnull(meanScore['score'])]
    
    #Associating student information with average scores
    meanScore = pd.merge(student_df, meanScore, how='left', left_on=['id'], right_on=['user_id'])
    meanScore = meanScore.drop(['user_id'], axis=1)
    
    #Write to CSV
    meanScore.to_csv("course_" + course + "_" + "assignment_" + assignment_id + '_complete mean score.csv', index=False)
    
    '''
    #whether to upload the data to the gradebook = True OR not = False
    upload = False
    #upload mean score to GradeCentre
    if upload==True:
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
    '''
