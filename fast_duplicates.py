#!/usr/bin/python

import os
import sys
import pickle 
import md5
import argparse

PICKLES_DIR = './pickles'
LOGS_DIR = './logs'

def get_files_hashmap(directory, force):
    pickle_filename = md5.new(directory).hexdigest() + '.pickle'
    if os.path.isfile(os.path.join(PICKLES_DIR, pickle_filename)) and not force:
        print('Reading existing hashmap for {} from {}'.format(directory, pickle_filename))
        with open(os.path.join(PICKLES_DIR, pickle_filename), 'rb') as f:
            files_hashmap = pickle.load(f)
    else:
        print('Creating new hashmap for {} in {}'.format(directory, pickle_filename))
        files_hashmap = create_files_hashmap(directory)
        with open(os.path.join(PICKLES_DIR, pickle_filename), 'wb') as f:
            pickle.dump(files_hashmap, f)
    
    return files_hashmap


def create_files_hashmap(directory):
    list_of_files = []
    for dirpath, dirnames, filenames in os.walk(directory):
        list_of_files += [(filename, os.path.join(dirpath, filename)) for filename in filenames]

    files_hashmap = {}
    for file_name, file_path in list_of_files:
        file_size = os.path.getsize(file_path)
        if (file_name, file_size) in files_hashmap.keys():
            files_hashmap[(file_name, file_size)].append(file_path)
        else:
            files_hashmap[(file_name, file_size)] = [file_path]

    return files_hashmap

parser = argparse.ArgumentParser(description='Check if all files from one directory are present in another.')

parser.add_argument(dest='needles', help='Directory that will be used as reference')
parser.add_argument(dest='haystack', help='Directory in which we look for duplicates')
parser.add_argument('-f', '--force', action='store_true', help='Forces program to re-hash the directory')
parser.add_argument('-l', '--log', action='store_true', help='Generate log file with details per-file')

args = parser.parse_args()

def check_dir(dirname):
    if not os.path.isdir(dirname):
        print(CRED + 'directory "{}" does not exist!'.format(dirname) + CEND)
        sys.exit(1)

check_dir(args.needles)
check_dir(args.haystack)

if not os.path.isdir(PICKLES_DIR):
    os.mkdir(PICKLES_DIR)

if not os.path.isdir(LOGS_DIR):
    os.mkdir(LOGS_DIR)

if args.log:
    log_filename = '{}_{}.log'.format(os.path.basename(args.needles), os.path.basename(args.haystack))
    log_file = open(os.path.join(LOGS_DIR, log_filename), 'w')

print('Getting hashmaps...')
needle_files = get_files_hashmap(args.needles, args.force)
haystack_files = get_files_hashmap(args.haystack, args.force)

print('Comparing hashmaps...')

mismatched = 0
count_all = len(needle_files.keys())

for i, (file_name, file_size) in enumerate(needle_files.keys()):

    progress = int(round((i+1)*100.0/count_all, 0)) 
    pre = needle_files[file_name, file_size]

    if (file_name, file_size) in haystack_files.keys():
        post = haystack_files[file_name, file_size]
        status = 'matched'
    else:  
        post = 'None'
        status = 'mismatched'
        mismatched += 1

    print('({}%): {} -> {}'.format(progress,pre , post))

    if args.log:
        log_file.write("{};{};{}\n".format(status, pre, post))

if mismatched == 0:
    print('All matched!')
else:
    print( 'Not all matched!')

if args.log:
    log_file.close()
    print('Saved to log: {}'.format(log_filename))
