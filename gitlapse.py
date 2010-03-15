import os
from subprocess import *
import tempfile
import sys
from optparse import OptionParser


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

class GitRepo:

    def current_head(self):
        return execute_and_return('git log --format=format:"%H" -1').read()

    def list_commits_to_file(self, destination_file_name):
         execute('git log --format=format:"%H || %ai || %s%n" --date=iso > ' + destination_file_name)
    
    def hard_reset(self, commit_hash):
        execute('git reset --hard %s' % commit_hash)

class ByDateLineCount:
    def __init__(self, date, commit):
        self.date = date
        self.commit = commit
        self.src_dir = {}

    def add_record(self, src_dir, language, count):
        counts_for_dir = self.src_dir.get(src_dir, {})
        counts_for_dir[language] = int(count)
        self.src_dir[src_dir] = counts_for_dir
    

def create_record(src_dir, by_date_count, cloc_line):
    records = cloc_line.split(',')

    if len(records) < 7:
        raise Exception('Cannot parse line \"' + cloc_line + '\"')

    number_of_files = records[0]
    language = records[1]
    number_of_blank_lines = records[2]
    lines_of_comments = records[3]
    lines_of_code = records[4]
    scale = records[5]
    third_gen = records[6]

    by_date_count.add_record(src_dir, language, lines_of_code)
    return by_date_count

def parse_cloc_output(cloc_output, date, commit):
    by_date_count = ByDateLineCount(date, commit)

    for src_dir in cloc_output.keys():
        lines = cloc_output[src_dir].split('\n')
        
        for line in lines:
            if 'files' in line:
                continue

            if line.isspace() or len(line) == 0:
                continue

            create_record(src_dir, by_date_count, line)

    return by_date_count

def as_csv(by_date_records):
    languages_to_report = {}

    for record in by_date_records:
        for src_dir in record.src_dir.keys():
            languages_for_dir = languages_to_report.get(src_dir, set())
            
            for language in record.src_dir[src_dir].keys():
                languages_for_dir.add(language)

            languages_to_report[src_dir] = languages_for_dir

    row_header = 'Date'
    for src_dir in languages_to_report.keys():
        for language in languages_to_report[src_dir]:
            row_header = row_header + '\t' + src_dir + '-' + language

    row_header = row_header + '\n'

    for record in by_date_records:
        row_header = row_header + record.date
        for src_dir in languages_to_report.keys():
            for language in languages_to_report[src_dir]:
                row_header = row_header + '\t' + str(record.src_dir.get(src_dir, {}).get(language, 0))

        row_header = row_header + '\n'
        
    return row_header

def linecount_for_date(date, commit, src_dirs, datafile):
    cloc_for_dirs = {}
    for src_dir in src_dirs:
        cloc_for_dirs[src_dir] = execute_and_return('perl ~/tools/cloc-1.08.pl ' + src_dir + ' --csv --exclude-lang=CSS,HTML,XML --quiet').read() 

    return parse_cloc_output(cloc_for_dirs, date, commit)
            
def generate_commit_list(location_for_files):
    file_with_all_commits = location_for_files + "/commits.out"
    GitRepo().list_commits_to_file(file_with_all_commits)
    git_output_file = open(file_with_all_commits)
    list_of_commits = []

    for line in git_output_file:
        records = line.split('||')
        if len(records) > 1:
            git_commit = records[0]
            date = records[1]
            list_of_commits.append((git_commit, date))
    
    return list_of_commits

def line_counts(location_for_results, sample_rate, src_dirs):
    data = open(location_for_results + "/line_count_by_time.tsv", 'w')
    
    commit_list = generate_commit_list(location_for_results)
    head = GitRepo().current_head()
    
    count = 0
    by_date_counts = []
    for commit in commit_list:
        date = commit[1]
        git_commit = commit[0]

        count = count + 1
        if count == sample_rate:
            print "Running line count for " + git_commit
            GitRepo().hard_reset(git_commit)
            by_date_counts.append(linecount_for_date(date, git_commit, src_dirs, data))
            count = 0
        else:
            print "Skipping " + git_commit
                
    data.write(as_csv(by_date_counts))

    print "Resetting to " + head
    GitRepo().hard_reset(head)

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
    src_dirs_str = options.src_dirs
    print "Using a sample rate of " + str(sample_rate) + " reading from files " + str(src_dirs_str)

    line_counts(results_dir, sample_rate, src_dirs_str.split(','))
    

if __name__ == "__main__":
    main()
