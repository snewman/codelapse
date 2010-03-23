import nose
from nose.tools import *
import gitlapse
import tempfile
import shutil
import os
import unittest

def main():
    nosemain()

class FakeOutput:

    def __init__(self, expected_result):
        self.expected_result = expected_result

    def read(self):
        return self.expected_result
 
class MockExecutor:

    def __init__(self, expected_result):
        self.last_command = None
        self.output = FakeOutput(expected_result)

    def execute(self, command):
        self.last_command = command
        return self.output

class GitRepoTests(unittest.TestCase):

    def test_can_get_head_of_current_branch(self):
        executor = MockExecutor("1234")
        repo = gitlapse.GitRepo('gitdir', 'workingdir', executor)
        repo.current_head()
        expected_command = 'git --git-dir=gitdir log --format=format:"%H" -1'
        assert_equals(expected_command, executor.last_command)
        
class CheckstyleAnalyserTests(unittest.TestCase):
    
    def test_can_run_analysis_on_src_dir(self):
        executor = MockExecutor('Some XML')
        install_dir = '/some/install/dir'
        src_dir = 'src'
        format = 'xml'

        expected_command = 'java -jar %s/tools/checkstyle/checkstyle-all-4.4.jar -c %s/tools/checkstyle/metrics.xml -r %s -f %s' % (install_dir, install_dir, src_dir, format)

        analyser = gitlapse.CheckstyleAnalyser(executor, "/some/install/dir")
        assert_equal('Some XML', analyser.analyse(src_dir))
        assert_equal(expected_command, executor.last_command)
        
   
class CheckstyleReportParserTests(unittest.TestCase):
    def test_can_get_number_of_healty_classes(self):
        sample_checkstyle_report = """<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="4.4">
<file name="src/some/package/DoStuff.java">
</file>
<file name="src/some/package/SomethingElse.java">
</file>
<file name="src/some/other/package/DoStuff.java">
</file>
</checkstyle>
"""
        parser = gitlapse.CheckstyleParser()
        report = parser.parse(sample_checkstyle_report)
        assert_equals(3, report.number_of_healty_classes())
 
    def test_can_determine_unhealthy_classes(self):
        sample_checkstyle_report = """<?xml version="1.0" encoding="UTF-8"?>
<checkstyle version="4.4">
<file name="src/some/package/DoStuff.java">
<error line="1" severity="warning" message="File length is 541 lines (max allowed is 500)." source="com.puppycrawl.tools.checkstyle.checks.sizes.FileLengthCheck"/>
</file>
<file name="src/some/package/SomethingElse.java">
</file>
<file name="src/some/other/package/DoStuff.java">
<error line="60" column="12" severity="warning" message="More than 6 parameters." source="com.puppycrawl.tools.checkstyle.checks.sizes.ParameterNumberCheck"/>
<error line="81" column="5" severity="warning" message="Method length is 38 lines (max allowed is 30)." source="com.puppycrawl.tools.checkstyle.checks.sizes.MethodLengthCheck"/>
</file>
</checkstyle>
"""
        parser = gitlapse.CheckstyleParser()
        report = parser.parse(sample_checkstyle_report)
        assert_equals(1, report.number_of_healty_classes())
        assert_equals(2, report.number_of_unhealthy_classes())
   
class ToxicityCalculatorTests(unittest.TestCase):

    def test_can_calculate_the_toxicity_for_high_method_line_count(self):
        errors = {'com.puppycrawl.tools.checkstyle.checks.sizes.MethodLengthCheck' : 'Method length is 38 lines (max allowed is 30).'}

        calculator = gitlapse.ToxicityCalculator()
        assert_equals(1.3, calculator.toxicity(errors))


class GitLapseTests(unittest.TestCase):

    def test_can_create_record(self):
        cloc_line = "10,Bourne Shell,56,155,252,3.81,960.12"
        by_date_count = gitlapse.ByDateLineCount('somedate', 'somecommit')
        by_date_count = gitlapse.create_record('src', by_date_count, cloc_line)
        assert_equal(by_date_count.src_dir['src']['Bourne Shell'], 252)

    def test_can_convert_multiple_clocs_to_by_date_record(self):
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

    def test_can_convert_cloc_to_by_date_record(self):
        cloc_output = """
files,language,blank,comment,code,scale,3rd gen. equiv,"http://cloc.sourceforge.net v 1.08  T=0.5 s (24.0 files/s, 1206.0 lines/s)"
10,Bourne Shell,56,155,252,3.81,960.12
2,Python,28,0,112,4.2,470.4"""

        by_date_count = gitlapse.parse_cloc_output({'src':cloc_output}, "somedate", "somecommit")
        assert_equal("somedate", by_date_count.date)
        assert_equal("somecommit", by_date_count.commit)

        assert_equal(112, by_date_count.src_dir['src']['Python'])
        assert_equal(252, by_date_count.src_dir['src']['Bourne Shell'])

    def test_can_format_empty_date_counts_as_tsv(self):
        csv_output = gitlapse.as_csv([])
        lines = csv_output.split('\n')

        assert_equal(lines[0], 'Date')

    def test_can_format_single_dir_date_counts_as_tsv(self):
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

    def test_can_format_multiple_dirs_date_counts_as_tsv(self):
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

    def test_can_generate_gnuplot_for_table_data(self):
        table_data = "Date	test-Javascript	test-Java	src-Java	web-Javascript	web-PHP"
        gnuplot_data = gitlapse.to_gnuplot(table_data)
        assert_equals("""plot "line_count_by_time.tsv" using 1:4 title "test-Javascript", \
"line_count_by_time.tsv" using 1:5 title "test-Java", \
"line_count_by_time.tsv" using 1:6 title "src-Java", \
"line_count_by_time.tsv" using 1:7 title "web-Javascript", \
"line_count_by_time.tsv" using 1:8 title "web-PHP", \
""", gnuplot_data)

class EndToEndTests(unittest.TestCase):

    def test_end_to_end(self):
        tmp_dir = tempfile.mkdtemp()
        shutil.copytree('.git', tmp_dir + '/repodir')
        gitlapse.main(['--git_repo_dir', tmp_dir + '/repodir', '--working_dir', tmp_dir, '--frequency_of_sample', '5', '--results_dir', tmp_dir, '--source_dir', '.'])
        files = os.listdir(tmp_dir)
        assert_true('line_count_by_time.tsv' in files, 'Cannot find results in ' + str(files))

if __name__ == "__main__":
    main()
