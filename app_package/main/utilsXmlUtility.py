from flask import current_app
import zipfile
import re
import os
from datetime import datetime
import time
from app_package.main.utilsApple import add_apple_to_db
import xmltodict
import logging
from logging.handlers import RotatingFileHandler
import shutil


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_main = logging.getLogger(__name__)
logger_main.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WS_ROOT_WEB'),"logs",'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_main.addHandler(file_handler)
logger_main.addHandler(stream_handler)


#starting line, next_line is how many lines after starting point do you want to go
# get_lines returns a string object
def get_lines(data, start, next_lines=1):
    line_list = [m.start() for m in re.finditer('\n', data)]
    if start == 1 and isinstance(next_lines,int):
        next_lines = next_lines - 1
        return data[0:line_list[next_lines]]
    elif start > 1 and isinstance(next_lines,int):
        start = start -2
        return data[line_list[start]:line_list[start + next_lines]]
    elif start >1 or start <0:# -- Get's all data from starting point to the end
        start = start -2
        return data[line_list[start]:]
    elif start == 1 and next_lines == None:
        return data[0:]


# Make line_list
def line_list_util(data_string, line_char_pos_list):
    line_list = []
    for i in range(0,len(line_char_pos_list)):
        if i != len(line_char_pos_list)-1:
            line_list.append(data_string[line_char_pos_list[i]:line_char_pos_list[i+1] ])
        else:
            line_list.append(data_string[line_char_pos_list[i]: ])
    return line_list


def header_fix_util(line_list):
    counter = 0
    new_string = ''
    flag_start = True
    flag_cdata_or_gt = False
    # flag_gt_watch = False
    error_counter = 0
    
    for line in line_list:
        if flag_start == True:
            if line.find('<!-- HealthKit Export ') > -1:
                new_string = new_string + line
                flag_start = False
            else:
                new_string = new_string + line
                
        elif flag_cdata_or_gt == True:
            if line.find('CDATA') > -1:#cdata
                new_string = new_string + line
            elif line.find('\n>') > -1:#gt
                new_string = new_string + line
                flag_cdata_or_gt = False
                # flag_gt_watch commented out because not being used but might be necessary
                # flag_gt_watch = True
                previous_line = line_list[counter]
            elif line.find('<!ELEM') > -1:
                logger_main.info(f"- Header Error: <!ELEMENT out of place, line: {counter}")
                #'Error resolved by adding '\n>' before current line
                error_counter += 1
                new_string = new_string + '\n>' + line
                flag_cdata_or_gt = False

                
        else:
            if line.find('<!ATTLIST') > -1:
                new_string = new_string + line
                flag_cdata_or_gt = True
            elif line.find('<!ELEM') > -1:
                new_string = new_string + line
            elif line.find('CDATA') > -1:#gt
                logger_main.info(f"- Header Error: this line shoudl go before last, line: {counter}")
                #'Error resolved by putting current line before the last'
                error_counter += 1
                new_string = new_string[:-len(previous_line)]
                new_string = new_string + line + previous_line
                
            elif line.find('\n>') > -1:
                logger_main.info(f"- Header Error: duplicate '>', line: {counter}")
                # error resolved by skipping line
                error_counter += 1
            else:#      < -----------------------Everything not '\n>', 'CDATA', or '<!ATT'
                new_string = new_string + line
        counter += 1
    logger_main.info(f"-- header_fix_util complete: {error_counter} error(s) found and resolved. -")
    return new_string


# def body_fix_util(body_list):
#     start_time = time.time()
#     counter = 0
#     string_obj = ''
#     error_count = 0
#     checkpoint = 5*10**5
# #     checkpoint = 10
    
#     for line in body_list:
#         start_date_line_list = [m.start() for m in re.finditer('startDate', line)]
#         if len(start_date_line_list)>1:
#             error_count += 1
#             string_obj = string_obj + line[:start_date_line_list[1]] + "endDate" + line[start_date_line_list[1]+len('startDate'):]
#         else:
#             string_obj = string_obj + line
        
#         if counter% checkpoint == 0:
            
#             end_time = time.time()
#             run_seconds = round(end_time - start_time)
#             if run_seconds <60:
#                 print(f'{"{:,}".format(counter)} rows have been reviewed --run_time: {str(run_seconds)} seconds')
#             elif run_seconds > 60:
#                 run_minutes =  round(run_seconds / 60)
#                 print(f'{"{:,}".format(counter)} rows have been reviewed ---- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds')

#         counter += 1
#     print(f'Completed: Found {error_count} startDate errors')
#     return string_obj



def body_fix_small_util(body_list):
    row_counter = 0
    string_obj = ''
    error_count = 0
    # checkpoint = 2.5*10**5
    
    for line in body_list:
        start_date_line_list = [m.start() for m in re.finditer('startDate', line)]
        if len(start_date_line_list)>1:
            error_count += 1
            string_obj = string_obj + line[:start_date_line_list[1]] + "endDate" + line[start_date_line_list[1]+len('startDate'):]
        else:
            string_obj = string_obj + line
        
        row_counter += 1
    return string_obj, row_counter, error_count

def body_fix_looper_util(body_line_list):
    start_time = time.time()
    fixed_body_dict = {}
    break_point_list = []
    error_count = 0
    row_count = 0
    #break list into 10 parts
    for i in range(0,10):
        break_point_list.append(int(len(body_line_list)*(i*.1)))

    #fix one of the ten parts at a time and store into a dictionary (fixed_body_dict)
    for i in range(0,10):
        start = break_point_list[i]
        if i<9:
            end = break_point_list[i+1]
            temp_string, temp_row_count, temp_error_count = body_fix_small_util(body_line_list[start:end])
            fixed_body_dict[i]= temp_string
        else:
            temp_string, temp_row_count, temp_error_count = body_fix_small_util(body_line_list[start:])
            fixed_body_dict[i]= temp_string
        
        error_count = error_count + temp_error_count
        row_count = row_count + temp_row_count
            
    body_string_fixed =''
    for _, string in fixed_body_dict.items():
        body_string_fixed = body_string_fixed + string      
        
    end_time = time.time()
    run_seconds = round(end_time - start_time)
    if run_seconds <60:
        logger_main.info(f'{"{:,}".format(row_count)} rows, {"{:,}".format(error_count)} errors --run_time: {str(run_seconds)} seconds')
    elif run_seconds > 60:
        run_minutes =  round(run_seconds / 60)
        logger_main.info(f'{"{:,}".format(row_count)} rows, {"{:,}".format(error_count)} errors -- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds')

    return body_string_fixed



def xml_get_header_body(header_string,body_string):

    #make list of header lines object:
    header = get_lines(header_string, 1 ,None)
    header_line_char_list = [x.start() for x in re.finditer('\n', header)]
    header_line_list = line_list_util(header, header_line_char_list)

    #make list of body lines object
    body = get_lines(body_string, 1,None)
    body_line_char_list = [x.start() for x in re.finditer('\n', body)]
    body_line_list = line_list_util(body, body_line_char_list)

    return header_line_list, body_line_list


#XML
def xml_file_fixer(xml_path):
    logger_main.info(f'---- In xml_file_fixer --')
    # Read uncompressed file from database/apple_health/user000#_date.xml
    with open(xml_path, 'r') as f:
        data = f.read()

    # split data (a string obj of xml) into header and body
    try:
        header_string = data[:data.find('\n]>')+3]
        body_string = data[data.find('\n]>')+3:]
        logger_main.info('-- successfully found header_string and body_string --')
    except:
        logger_main.info(f"--- xml_util: never found end of header or beginning of body strings ---")
        return "XML file never found end of header"

    # convert header and body stringst to lists
    header_line_list, body_line_list = xml_get_header_body(header_string, body_string)
    header_string_fixed = header_fix_util(header_line_list)

    # try to convert combined FIXED header and orig body string to dict
    try:
        xml_dict = xmltodict.parse(header_string_fixed + body_string)
        return xml_dict
    except:
        logger_main.info(f"--- xml_util: attempting to fix body string ---")

    # body_string_fixed = body_fix_util(body_line_list)
    body_string_fixed = body_fix_looper_util(body_line_list)

    # try to convert combined FIXED header and FIXED body string to dict
    try:
        # string to dictionary
        xml_dict = xmltodict.parse(header_string_fixed + body_string_fixed)
        # df_uploaded_record_count = add_apple_to_db(xml_dict)
        return xml_dict
    except:
        logger_main.info(f"--- xml_util: unable to convert xml to dictionary ---")
        return "Unable to process Apple Health Export"



def compress_to_save_util(decompressed_xml_file_name):
    logger_main.info('- Compressing and storing users Apple Health data')
    apple_health_dir = current_app.config.get('APPLE_HEALTH_DIR')
    # print(apple_health_dir)
    app_health_ex_dir = os.path.join(apple_health_dir,'stuff_to_compress', 'apple_health_export')
    stuff_to_compress = os.path.join(apple_health_dir,'stuff_to_compress')
    decompressed_xml = os.path.join(apple_health_dir, decompressed_xml_file_name)
    if not os.path.exists(stuff_to_compress):
        os.mkdir(stuff_to_compress)
        os.mkdir(app_health_ex_dir)
        shutil.copy(decompressed_xml, os.path.join(app_health_ex_dir,'export.xml' ))
        
    #     shutil.make_archive(app_health_ex_dir, 'zip', test_folder)
        new_name_and_path_of_zip = os.path.join(apple_health_dir, decompressed_xml_file_name[:-4])
        shutil.make_archive(new_name_and_path_of_zip, 'zip', stuff_to_compress)
        # delete directory that get's turned to compressed file
        shutil.rmtree(stuff_to_compress)
        # delete decompressed xml file becuase its now stored in a compressed directory
        # that can be reused in WS like original compressed Apple Health Export file
        os.remove(decompressed_xml)




