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
        
        datafile.write(src_dir + "-" + language + "\t" + date + "\t" + lines_of_code + "\t" + number_of_blank_lines + "\t" + lines_of_comments + "\t" + lines_of_code + "\t" + scale + "\t" + third_gen + "\t" + commit)
            

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
    
def main():
    parser = OptionParser()
    parser.add_option("-r", "--results_dir", action="store", dest="result_dir", type="string", default=".", help="Location where results will be stored")
    parser.add_option("-s", "--source_dir", action="append", dest="src_dirs", type="string", default="src", help="Which src directories to parse")
    parser.add_option("-f", "--frequency_of_sample", action="store", dest="sample_rate", default=100, type="int", help="How often should a sample be made")

    (options, args) = parser.parse_args()

    tmp_dir = options.result_dir
    sample_rate = options.sample_rate

    data = open(tmp_dir + "/line_count_by_time.tsv", 'w')
    print "Writing to " + data.name + " using a sample rate of " + str(sample_rate)
    data.write("Type Of File\tDate\tLines Of Code\tNumber Blank\tNumber Comment\tScale\t3rd gen. equiv\tCommit\n")

    count = 0

    commit_list = generate_commit_list(tmp_dir)

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

if __name__ == "__main__":
    main()
