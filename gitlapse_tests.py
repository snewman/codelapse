import nose
from nose.tools import *
import gitlapse
import tempfile
import shutil
import os

def main():
    nosemain()

def test_can_create_record():
    cloc_line = "10,Bourne Shell,56,155,252,3.81,960.12"
    by_date_count = gitlapse.ByDateLineCount('somedate', 'somecommit')
    by_date_count = gitlapse.create_record('src', by_date_count, cloc_line)
    assert_equal(by_date_count.src_dir['src']['Bourne Shell'], 252)

def test_can_convert_multiple_clocs_to_by_date_record():
    cloc_output_1 = """
files,language,blank,comment,code,scale,3rd gen. equiv,"http://cloc.sourceforge.net v 1.08  T=0.5 s (24.0 files/s, 1206.0 lines/s)"
10,Bourne Shell,56,155,252,3.81,960.12
2,Python,28,0,112,4.2,470.4"""

    cloc_output_2 = """
files,language,blank,comment,code,scale,3rd gen. equiv,"http://cloc.sourceforge.net v 1.08  T=0.5 s (24.0 files/s, 1206.0 lines/s)"
2,Python,28,0,32,4.2,470.4"""

    by_date_count = gitlapse.parse_cloc_output({'src':cloc_output_1, 'test':cloc_output_2}, "somedate", "somecommit")
    assert_equal("somedate", by_date_count.date)
    assert_equal("somecommit", by_date_count.commit)

    assert_equal(112, by_date_count.src_dir['src']['Python'])
    assert_equal(252, by_date_count.src_dir['src']['Bourne Shell'])

def test_can_convert_cloc_to_by_date_record():
    cloc_output = """
files,language,blank,comment,code,scale,3rd gen. equiv,"http://cloc.sourceforge.net v 1.08  T=0.5 s (24.0 files/s, 1206.0 lines/s)"
10,Bourne Shell,56,155,252,3.81,960.12
2,Python,28,0,112,4.2,470.4"""

    by_date_count = gitlapse.parse_cloc_output({'src':cloc_output}, "somedate", "somecommit")
    assert_equal("somedate", by_date_count.date)
    assert_equal("somecommit", by_date_count.commit)

    assert_equal(112, by_date_count.src_dir['src']['Python'])
    assert_equal(252, by_date_count.src_dir['src']['Bourne Shell'])

def test_can_format_empty_date_counts_as_tsv():
    csv_output = gitlapse.as_csv([])
    lines = csv_output.split('\n')

    assert_equal(lines[0], 'Date')

def test_can_format_single_dir_date_counts_as_tsv():
    first_counts = gitlapse.ByDateLineCount('1st March', 'commit')
    first_counts.add_record('src', 'Java', 123)

    second_counts = gitlapse.ByDateLineCount('2nd March', 'commit')
    second_counts.add_record('src', 'Java', 124)
    second_counts.add_record('src', 'C', 4452)

    csv_output = gitlapse.as_csv([first_counts, second_counts])
    lines = csv_output.split('\n')
    assert_equal(lines[0], 'Date\tsrc-C\tsrc-Java')
    assert_equal(lines[1], '1st March\t0\t123')
    assert_equal(lines[2], '2nd March\t4452\t124')

def test_can_format_multiple_dirs_date_counts_as_tsv():
    first_counts = gitlapse.ByDateLineCount('1st March', 'commit')
    first_counts.add_record('src', 'Java', 123)

    second_counts = gitlapse.ByDateLineCount('2nd March', 'commit')
    second_counts.add_record('src', 'Java', 124)
    second_counts.add_record('test', 'Java', 5)
    second_counts.add_record('test', 'C', 4452)

    csv_output = gitlapse.as_csv([first_counts, second_counts])
    lines = csv_output.split('\n')
    assert_equal(lines[0], 'Date\ttest-C\ttest-Java\tsrc-Java')
    assert_equal(lines[1], '1st March\t0\t0\t123')
    assert_equal(lines[2], '2nd March\t4452\t5\t124')

def test_can_generate_gnuplot_for_table_data():
    table_data = "Date	test-Javascript	test-Java	src-Java	web-Javascript	web-PHP"
    gnuplot_data = gitlapse.to_gnuplot(table_data)
    assert_equals("""plot "line_count_by_time.tsv" using 1:4 title "test-Javascript", \
"line_count_by_time.tsv" using 1:5 title "test-Java", \
"line_count_by_time.tsv" using 1:6 title "src-Java", \
"line_count_by_time.tsv" using 1:7 title "web-Javascript", \
"line_count_by_time.tsv" using 1:8 title "web-PHP", \
""", gnuplot_data)

def test_end_to_end():
    tmp_dir = tempfile.mkdtemp()
    shutil.copytree('.git', tmp_dir + '/repodir')
    gitlapse.main(['--git_repo_dir', tmp_dir + '/repodir', '--working_dir', tmp_dir, '--frequency_of_sample', '5', '--results_dir', tmp_dir, '--source_dir', '.'])
    files = os.listdir(tmp_dir)
    assert_true('line_count_by_time.tsv' in files, 'Cannot find results in ' + str(files))

if __name__ == "__main__":
    main()
