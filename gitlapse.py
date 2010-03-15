import os
from subprocess import *
import tempfile
import sys
from optparse import OptionParser

class LineCountRecord:
    def __init__(self, date, commit):
        self.date = date
        self.commit = commit
        self.records = {}

    def add_record(self, language, count):
        self.records[language] = int(count)
    
def execute(command):
    try:
        retcode = call(command, shell=True)
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
            sys.exit(retcode)
    except OSError, e:
        print >>sys.stderr, "Execution failed:", e

def execute_and_return(command):
    try:
        p = Popen(command, shell=True, stdout=PIPE)
        retcode = os.waitpid(p.pid, 0)[1]
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
            sys.exit(retcode)
        else:
            return p.stdout
    except OSError, e:
        print >>sys.stderr, "Execution failed:", e

def create_record(date, commit, cloc_line):
    record = LineCountRecord(date, commit)

    records = cloc_line.split(',')
    number_of_files = records[0]
    language = records[1]
    number_of_blank_lines = records[2]
    lines_of_comments = records[3]
    lines_of_code = records[4]
    scale = records[5]
    third_gen = records[6]

    record.add_record(language, lines_of_code)
    return record

def linecount(date, commit, src_dir, datafile):
    linecount_records = execute_and_return('perl ~/tools/cloc-1.08.pl ' + src_dir + ' --csv --exclude-lang=CSS,HTML,XML --quiet')

    for line in linecount_records:
        if 'files' in line:
            continue
               
        records = line.split(',')
        number_of_files = records[0]
        language = records[1]
        number_of_blank_lines = records[2]
        lines_of_comments = records[3]
        lines_of_code = records[4]
        scale = records[5]
        third_gen = records[6]

        datafile.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (src_dir + language, date, lines_of_code, number_of_blank_lines, lines_of_comments, scale, third_gen, commit))
            
def generate_commit_list(location_for_files):
    file_with_all_commits = location_for_files + "/commits.out"
    execute('git log --format=format:"%H || %ai || %s%n" --date=iso > ' + file_with_all_commits)
    git_output_file = open(file_with_all_commits)
    list_of_commits = []

    for line in git_output_file:
        records = line.split('||')
        if len(records) > 1:
            git_commit = records[0]
            date = records[1]
            list_of_commits.append((git_commit, date))
    
    return list_of_commits

def line_counts(location_for_results, sample_rate):
    data = open(location_for_results + "/line_count_by_time.tsv", 'w')
    data.write("Type Of File\tDate\tLines Of Code\tNumber Blank\tNumber Comment\tScale\t3rd gen. equiv\tCommit\n")

    commit_list = generate_commit_list(location_for_results)
    
    count = 0

    for commit in commit_list:
        date = commit[1]
        git_commit = commit[0]

        count = count + 1
        if count == sample_rate:
            print "Running line count for " + git_commit
            execute('git reset --hard %s' % git_commit)
            linecount(date, git_commit, 'src', data)
            linecount(date, git_commit, 'test', data)
            count = 0
        else:
            print "Skipping " + git_commit
                
    print data.name
    data.close()
    
def main():
    parser = OptionParser()
    parser.add_option("-r", "--results_dir", action="store", dest="result_dir", type="string", default=".", help="Location where results will be stored")
    parser.add_option("-s", "--source_dir", action="store", dest="src_dirs", type="string", default="src", help="A comma seperated list of directories to parse")
    parser.add_option("-f", "--frequency_of_sample", action="store", dest="sample_rate", default=100, type="int", help="How often should a sample be made")

    (options, args) = parser.parse_args()

    results_dir = options.result_dir
    sample_rate = options.sample_rate
    src_dirs = options.src_dirs
    print "Using a sample rate of " + str(sample_rate) + " reading from files " + str(src_dirs)

    line_counts(results_dir, sample_rate)
    

if __name__ == "__main__":
    main()
