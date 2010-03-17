import os
import inspect
from subprocess import *
import tempfile
import sys
from optparse import OptionParser

def execute(command):
    try:
        print "Running " + command
        p = Popen(command, shell=True, stdout=PIPE)
        retcode = os.waitpid(p.pid, 0)[1]
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
            sys.exit(retcode)
        else:
            return p.stdout
    except OSError, e:
        print >>sys.stderr, "Execution failed:", e
        sys.exit(2)

class GitRepo:

    def __init__(self, git_dir, working_dir):
        self.git_dir = git_dir
        self.working_dir = working_dir

    def current_head(self):
        return execute('git --git-dir=' + self.git_dir + ' log --format=format:"%H" -1').read()

    def list_commits_to_file(self, destination_file_name):
        execute('git --git-dir=' + self.git_dir + ' --no-pager log --format=format:"%H || %ai || %s%n" --date=iso > ' + destination_file_name)
        return open(destination_file_name)

    def commits(self, destination_file_name):
        git_output_file = self.list_commits_to_file(destination_file_name)
        list_of_commits = []

        for line in git_output_file:
            records = line.split('||')
            if len(records) > 1:
                git_commit = records[0]
                date = records[1]
                list_of_commits.append((git_commit, date))
    
        return list_of_commits
    
    def hard_reset(self, commit_hash):
        execute('git --git-dir=' + self.git_dir + ' --work-tree=' + self.working_dir + ' reset --hard %s' % commit_hash)

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

def linecount_for_date(date, commit, src_dirs, datafile, working_dir):
    cloc_for_dirs = {}
    for src_dir in src_dirs:
        cloc_for_dirs[src_dir] = execute('perl ' + RUNNING_FROM + '/tools/cloc-1.08.pl ' + working_dir + '/' + src_dir + ' --csv --exclude-lang=CSS,HTML,XML --quiet').read() 

    return parse_cloc_output(cloc_for_dirs, date, commit)
            
def generate_commit_list(location_for_files, git_repo):
    file_with_all_commits = location_for_files + "/commits.out"
    return git_repo.commits(file_with_all_commits)
    
def line_counts(location_for_results, sample_rate, src_dirs, git_dir, working_dir):
    data = open(location_for_results + "/line_count_by_time.tsv", 'w')

    git_repo = GitRepo(git_dir, working_dir)
    commit_list = generate_commit_list(location_for_results, git_repo)
    head = git_repo.current_head()
    
    count = 0
    by_date_counts = []
    for commit in commit_list:
        date = commit[1]
        git_commit = commit[0]

        count = count + 1
        if count == sample_rate:
            print "Running line count for " + git_commit
            git_repo.hard_reset(git_commit)
            by_date_counts.append(linecount_for_date(date, git_commit, src_dirs, data, working_dir))
            count = 0
        else:
            print "Skipping " + git_commit
                
    data.write(as_csv(by_date_counts))

    print "Resetting to " + head
    git_repo.hard_reset(head)

    print data.name
    data.close()
    
def to_gnuplot(data_table):
    header_row = data_table.split('\n')[0]
    columns = header_row.split('\t')[1:]

    gnuplot = 'plot '
    count = 4 # The first 3 columns contain the date
    
    for column in columns:
        gnuplot = gnuplot + ('"line_count_by_time.tsv" using 1:%d title "%s", ' % (count, column))
        count = count + 1

    return gnuplot

def execution_path(filename):
  execution_path = os.path.join(os.path.dirname(inspect.getfile(sys._getframe(1))), 'run.sh')
  path_to_run = os.path.abspath(execution_path)
  if path_to_run.endswith('run.sh'):
      index_of_run = len(path_to_run) - 6
      return path_to_run[:index_of_run]
  else:
      return path_to_run

RUNNING_FROM =  execution_path('run.sh')

def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = OptionParser()
    parser.add_option("-r", "--results_dir", action="store", dest="result_dir", type="string", default=".", help="Location where results will be stored")
    parser.add_option("-s", "--source_dir", action="store", dest="src_dirs", type="string", default="src", help="A comma seperated list of directories to parse")
    parser.add_option("-f", "--frequency_of_sample", action="store", dest="sample_rate", default=100, type="int", help="How often should a sample be made")
    parser.add_option("-g", "--git_repo_dir", action="store", dest="git_repo_dir", default=".", type="string", help="The directory containing the .git file")
    parser.add_option("-w", "--working_dir", action="store", dest="working_dir", default=".", type="string", help="Where will files be checked out to for line counts etc")

    (options, args) = parser.parse_args(argv)

    results_dir = options.result_dir
    sample_rate = options.sample_rate
    src_dirs_str = options.src_dirs
    git_dir = options.git_repo_dir
    working_dir = options.working_dir
    print "Using a sample rate of " + str(sample_rate) + " reading from files " + str(src_dirs_str)

    line_counts(results_dir, sample_rate, src_dirs_str.split(','), git_dir, working_dir)
    

if __name__ == "__main__":
    main()
