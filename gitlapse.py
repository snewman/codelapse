import os
from subprocess import *
import tempfile
import sys

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

    sample_rate = 10
    count = 0

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
            
def main():
    tmp_dir = tempfile.mkdtemp()
    file_with_all_commits = tmp_dir + "/commits.out"
    execute('git log --format=format:"%H || %ai || %s%n" --date=iso > ' + file_with_all_commits)

    f = open(file_with_all_commits)

    data = open(tmp_dir + "/linecounts.tsv", 'w')
    print "Writing to " + data.name
    data.write("Type Of File\tDate\tLines Of Code\tNumber Blank\tNumber Comment\tScale\t3rd gen. equiv\tCommit\n")

    sample_rate = 10
    count = 0

    for line in f:
        records = line.split('||')
        if len(records) > 1:
            git_commit = records[0]
            date = records[1]

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
