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

    for line in linecount_records:
        if 'files' in line:
            continue
        records = line.split(',')
        datafile.write(src_dir + "\t" + date + "\t" + commit + "\t" + records[0] + "\t" + records[1] + "\t" + records[2] + "\t" + records[3] + "\t" + records[4] + "\t" + records[5] + "\t" + records[6])

def main():
    # the main code goes here perl cloc-1.08.pl ../Development/Autotrader/sauron-git/src
    tmp_dir = tempfile.mkdtemp()
    file_with_all_commits = tmp_dir + "/commits.out"
    execute('git log --format=format:"%H || %ai || %s%n" --date=iso > ' + file_with_all_commits)

    f = open(file_with_all_commits)

    data = open(tmp_dir + "/linecounts.tsv", 'w')
    print data

    for line in f:
        records = line.split('||')
        if len(records) > 1:
            git_commit = records[0]
            date = records[1]

            print "Running line count for " + git_commit
            execute('git reset --hard %s' % git_commit)
            linecount(date, git_commit, 'src', data)
            linecount(date, git_commit, 'test', data)

            #p = Popen('perl ~/tools/cloc-1.08.pl src --csv --quiet', shell=True)
            #retval = os.waitpid(p.pid, 0)[1]

            #if retval <> 0:
            #    sys.exit(retval)

            #os.system('perl ~/tools/cloc-1.08.pl src --csv --quiet')
            #data.write(records[0] + "\t" + records[1])
            #retval = os.system('git reset --hard %s' % records[0])
            #if retval <> 0:
            #    sys.exit(retval)
                
    print data
    data.close()

if __name__ == "__main__":
    main()
