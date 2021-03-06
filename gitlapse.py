import os
import inspect
from subprocess import *
import tempfile
import sys
from optparse import OptionParser
from xml.dom.minidom import parseString
import re
from decimal import *

class Executor:

    def execute(self, command):
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

    def __init__(self, git_dir, working_dir, executor):
        self.git_dir = git_dir
        self.working_dir = working_dir
        self.executor = executor

    def current_head(self):
        return self.executor.execute('git --git-dir=' + self.git_dir + ' log --format=format:"%H" -1').read()

    def list_commits_to_file(self, destination_file_name):
        self.executor.execute('git --git-dir=' + self.git_dir + ' --no-pager log --format=format:"%H || %ai || %s%n" --date=iso > ' + destination_file_name)
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
        self.executor.execute('git --git-dir=' + self.git_dir + ' --work-tree=' + self.working_dir + ' reset --hard %s' % commit_hash)

class CheckstyleParser:
    
    def parse(self, checkstyle_report_content):
        dom = parseString(checkstyle_report_content)
        root = dom.getElementsByTagName('checkstyle')[0]
        classes = root.getElementsByTagName('file')
        healthy_class_names = [clazz.getAttribute('name') for clazz in classes if len(clazz.getElementsByTagName('error')) == 0]

        unhealthy_classes = []
        for clazz in classes:
            if len(clazz.getElementsByTagName('error')) > 0:
                errors = {}
                for error in clazz.getElementsByTagName('error'):
                         errors[error.getAttribute('source')] = error.getAttribute('message')

                unhealthy_classes.append(ToxicClass(clazz.getAttribute('name'), errors))


        return ToxicityReport(healthy_class_names, unhealthy_classes)


class CheckstyleExecution:

    def __init__(self, executor, path_to_install):
        self.executor = executor
        self.path_to_install = path_to_install

    def analyse(self, src_directory):
         #java -jar ../../code-time-lapse/tools/checkstyle/checkstyle-all-4.4.jar -c ../../code-time-lapse/tools/checkstyle/metrics.xml -r src -f xml

        stdout = self.executor.execute('java -jar %s/tools/checkstyle/checkstyle-all-4.4.jar -c %s/tools/checkstyle/metrics.xml -r %s -f xml' % (self.path_to_install, self.path_to_install, src_directory))
        return stdout.read()

class ToxicClass:
    
    def __init__(self, class_name, errors):
        self.errors = errors
        

class ToxicityReport:

    def __init__(self, healthy_class_names, unhealthy_class_names):
        self.healthy_class_names = healthy_class_names
        self.unhealthy_class_names = unhealthy_class_names

    def number_of_healty_classes(self):
        return len(self.healthy_class_names)

    def number_of_unhealthy_classes(self):
        return len(self.unhealthy_class_names)

class ToxicityCalculator():

    def __init__(self):
        self.handlers = {
            'com.puppycrawl.tools.checkstyle.checks.sizes.MethodLengthCheck' : self.calculate_long_method_length_cost,
            'com.puppycrawl.tools.checkstyle.checks.sizes.FileLengthCheck' : self.calculate_long_class_cost,
            'com.puppycrawl.tools.checkstyle.checks.metrics.ClassDataAbstractionCouplingCheck' : self.calculate_abstraction_coupling_cost}

    def calculate_abstraction_coupling_cost(self, message_string):
        values = self.matches('Class Data Abstraction Coupling is (\d*) \(max allowed is (\d*)\)', message_string)
        return self.cost(values[0], values[1])

    def calculate_long_method_length_cost(self, message_string):
        values = self.matches('Method length is (\d*) lines \(max allowed is (\d*)\).', message_string)
        return self.cost(values[0], values[1])

    def calculate_long_class_cost(self, message_string):
        values = self.matches('File length is (\d*) lines \(max allowed is (\d*)\)', message_string)
        return self.cost(values[0], values[1])

    def matches(self, pattern, string):
        return re.search(pattern, string).groups()

    def toxicity(self, errors):
        score = Decimal(0)

        for error_type in errors.keys():
            score = score + self.handlers[error_type](errors[error_type])

        return self.round_down(score)

    def cost(self, actual, allowed):
        return Decimal(actual) / Decimal(allowed)

    def round_down(self, decimal):
        return decimal.quantize(Decimal('.01'), rounding=ROUND_DOWN)

class SkippingAnalyser:

    def __init__(self, skipping_commits, delegate_analyser, git_repo):
        self.skipping_commits = skipping_commits
        self.delegate_analyser = delegate_analyser
        self.git_repo = git_repo
        self.current_count = 0

    def analyse(self, commit_hash, commit_date):
        self.current_count = self.current_count + 1

        if self.current_count == self.skipping_commits:
            self.git_repo.hard_reset(commit_hash)
            self.delegate_analyser.analyse(commit_hash, commit_date)
            self.current_count = 0

class ClocParser:
    
    def create_record(self, src_dir, by_date_count, cloc_line):
        records = cloc_line.split(',')

        if len(records) < 7:
            raise Exception('Cannot parse line "' + cloc_line + '"')

        number_of_files = records[0]
        language = records[1]
        number_of_blank_lines = records[2]
        lines_of_comments = records[3]
        lines_of_code = records[4]
        scale = records[5]
        third_gen = records[6]

        by_date_count.add_record(src_dir, language, lines_of_code)
        return by_date_count

    def parse(self, commit_date, commit_hash, src_directory_name, cloc_output):
        by_date_count = MetricsForCommit(commit_date, commit_hash)
        lines = cloc_output.split('\n')
    
        for line in lines:
            if 'files' in line:
                continue

            if line.isspace() or len(line) == 0:
                continue

            by_date_count = self.create_record(src_directory_name, by_date_count, line)

        return by_date_count


class TsvFormattingStore:

    def __init__(self):
        self.records_by_commit = {}

    def store(self, metrics_for_commit):
        commit = metrics_for_commit.commit

        if self.records_by_commit.has_key(commit):
            old_record = self.records_by_commit[commit]
            old_record.merge(metrics_for_commit)
        else:
            self.records_by_commit[commit] = metrics_for_commit


    def metrics_to_report(self):
        metrics_to_report = {}

        for record in self.records_by_commit.values():

            for src_dir in record.src_dirs.keys():
                metrics_for_dir = metrics_to_report.get(src_dir, set())
            
                for metric in record.src_dirs[src_dir].keys():
                    metrics_for_dir.add(metric)

                    metrics_to_report[src_dir] = metrics_for_dir
        
        return metrics_to_report

    def create_row_header(self, metrics_to_report):
        row_header = 'Date'
        for src_dir in metrics_to_report.keys():
            for language in metrics_to_report[src_dir]:
                row_header = row_header + '\t' + src_dir + '-' + language

        row_header = row_header + '\n'
        return row_header
    
    def as_csv(self):
        metrics_to_report = self.metrics_to_report()
        row_header = self.create_row_header(metrics_to_report)

        for record in self.records_by_commit.values():
            row_header = row_header + record.date
            for src_dir in metrics_to_report.keys():
                for metric in metrics_to_report[src_dir]:
                    row_header = row_header + '\t' + str(record.src_dirs.get(src_dir, {}).get(metric, 0))

            row_header = row_header + '\n'
        
        return row_header


class LinesOfCodeAnalyser:

    def __init__(self, abs_src_directory, running_from, data_store, parser = ClocParser(), executor = Executor()):
        self.executor = executor
        self.parser = parser
        self.running_from = running_from
        self.abs_src_directory = abs_src_directory
        self.data_store = data_store

    def analyse(self, commit_hash, commit_date):
        cloc_cmd = 'perl %s/tools/cloc-1.08.pl %s --csv --exclude-lang=CSS,HTML,XML --quiet' % (self.running_from, self.abs_src_directory)
        cloc_result = self.executor.execute(cloc_cmd)
        data_to_store = self.parser.parse(commit_date, commit_hash, self.abs_src_directory, cloc_result.read())
        self.data_store.store(data_to_store)
    

class CompositeAnalyser:

    def __init__(self, delegates):
        self.delegates = delegates

    def analyse(self, commit_hash, commit_date):
        for delegate in self.delegates:
            delegate.analyse(commit_hash, commit_date)

class MetricsForCommit:
    def __init__(self, date, commit):
        self.date = date
        self.commit = commit
        self.src_dirs = {}

    def add_record(self, src_dir, metric, count):
        counts_for_dir = self.src_dirs.get(src_dir, {})
        counts_for_dir[metric] = int(count)
        self.src_dirs[src_dir] = counts_for_dir

    def merge(self, other_by_date_count):
        if other_by_date_count.commit != self.commit:
            raise Exception('Can only merge records with same commit')

        for src_dir in other_by_date_count.src_dirs.keys():
            self.src_dirs[src_dir] = other_by_date_count.src_dirs[src_dir]
    

def generate_commit_list(location_for_files, git_repo):
    file_with_all_commits = location_for_files + "/commits.out"
    return git_repo.commits(file_with_all_commits)
    
def line_counts(location_for_results, sample_rate, src_dirs, git_dir, working_dir):
    data = open(location_for_results + "/line_count_by_time.tsv", 'w')

    git_repo = GitRepo(git_dir, working_dir, Executor())
    commit_list = generate_commit_list(location_for_results, git_repo)
    head = git_repo.current_head()
    
    store = TsvFormattingStore()
    delegate = CompositeAnalyser([LinesOfCodeAnalyser(src_dir, RUNNING_FROM, store) for src_dir in src_dirs])
    skipping_analyser = SkippingAnalyser(skipping_commits = sample_rate, delegate_analyser = delegate, git_repo = git_repo)

    for commit in commit_list:
        date = commit[1]
        git_commit = commit[0]
        skipping_analyser.analyse(git_commit, date)

    data.write(store.as_csv())

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
      path_to_run = path_to_run[:index_of_run]

  print "Using " + path_to_run 
  return path_to_run

RUNNING_FROM =  execution_path('run.sh')

def pwd():
    return Executor().execute('pwd').read().strip()

def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = OptionParser()
    parser.add_option("-r", "--results_dir", action="store", dest="result_dir", type="string", default=".", help="Location where results will be stored")
    parser.add_option("-s", "--source_dir", action="store", dest="src_dirs", type="string", default="src", help="A comma seperated list of directories to parse")
    parser.add_option("-f", "--frequency_of_sample", action="store", dest="sample_rate", default=100, type="int", help="How often should a sample be made")
    parser.add_option("-g", "--git_repo_dir", action="store", dest="git_repo_dir", default=pwd()+'/.git', type="string", help="The directory containing the .git file")
    parser.add_option("-w", "--working_dir", action="store", dest="working_dir", default=pwd(), type="string", help="Where will files be checked out to for line counts etc")

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
