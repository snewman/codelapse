import nose
from nose.tools import *
import gitlapse
import tempfile
import shutil
import os
import unittest
from decimal import Decimal
from nose.plugins.attrib import attr

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
        
class CheckstyleExecutionTests(unittest.TestCase):
    
    def test_can_run_analysis_on_src_dir(self):
        executor = MockExecutor('Some XML')
        install_dir = '/some/install/dir'
        src_dir = 'src'
        format = 'xml'

        expected_command = 'java -jar %s/tools/checkstyle/checkstyle-all-4.4.jar -c %s/tools/checkstyle/metrics.xml -r %s -f %s' % (install_dir, install_dir, src_dir, format)

        analyser = gitlapse.CheckstyleExecution(executor, "/some/install/dir")
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

    def test_can_calculate_the_toxicity_for_long_method_line_count(self):
        errors = {'com.puppycrawl.tools.checkstyle.checks.sizes.MethodLengthCheck' : 'Method length is 38 lines (max allowed is 30).'}

        calculator = gitlapse.ToxicityCalculator()
        assert_equals(Decimal('1.26'), calculator.toxicity(errors))

    def test_can_calculate_the_toxicity_for_long_classes(self):
        errors = {'com.puppycrawl.tools.checkstyle.checks.sizes.FileLengthCheck' : 'File length is 594 lines (max allowed is 500).'}

        calculator = gitlapse.ToxicityCalculator()
        assert_equals(Decimal('1.18'), calculator.toxicity(errors))

    def test_can_calculate_toxicity_for_class_abstraction_coupling(self):
        errors = {'com.puppycrawl.tools.checkstyle.checks.metrics.ClassDataAbstractionCouplingCheck': 'Class Data Abstraction Coupling is 20 (max allowed is 10) classes [A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T].'}

        calculator = gitlapse.ToxicityCalculator()
        assert_equals(Decimal('2.00'), calculator.toxicity(errors))


class ClocParserTests(unittest.TestCase):

    def test_can_parse_one_line(self):
        parser = gitlapse.ClocParser()
        cloc_line = "10,Bourne Shell,56,155,252,3.81,960.12"
        by_date_count = parser.parse('somedate', 'somecommit', 'src', cloc_line)
        assert_equal(by_date_count.src_dirs['src']['Bourne Shell'], 252)

    def test_can_parse_multiline_cloc_output(self):
        cloc_output = """
files,language,blank,comment,code,scale,3rd gen. equiv,"http://cloc.sourceforge.net v 1.08  T=0.5 s (24.0 files/s, 1206.0 lines/s)"
10,Bourne Shell,56,155,252,3.81,960.12
2,Python,28,0,112,4.2,470.4"""

        parser = gitlapse.ClocParser()
        by_date_count = parser.parse('somedate', 'somecommit', 'src', cloc_output)

        assert_equal("somedate", by_date_count.date)
        assert_equal("somecommit", by_date_count.commit)

        assert_equal(112, by_date_count.src_dirs['src']['Python'])
        assert_equal(252, by_date_count.src_dirs['src']['Bourne Shell'])


class TsvFormattingStoreTests(unittest.TestCase):

    def test_can_format_when_no_results(self):
        store = gitlapse.TsvFormattingStore()
        lines = store.as_csv()
        assert_equal(lines, 'Date\n')

    def test_can_format_with_single_record(self):
        first_counts = gitlapse.MetricsForCommit('1st March', 'commit1')
        first_counts.add_record('src', 'Java', 123)

        second_counts = gitlapse.MetricsForCommit('2nd March', 'commit2')
        second_counts.add_record('src', 'Java', 124)
        second_counts.add_record('src', 'C', 4452)

        store = gitlapse.TsvFormattingStore()
        store.store(first_counts)
        store.store(second_counts)

        lines = store.as_csv().split('\n')
        assert_equal(lines[0], 'Date\tsrc-C\tsrc-Java')
        assert_equal(lines[1], '2nd March\t4452\t124')
        assert_equal(lines[2], '1st March\t0\t123')
       
    def test_can_format_multiple_records_for_the_same_commit(self): 
        first_counts = gitlapse.MetricsForCommit('1st March', 'commit3')
        first_counts.add_record('src', 'Java', 123)

        second_counts = gitlapse.MetricsForCommit('1st March', 'commit3')
        second_counts.add_record('test', 'Java', 124)
        second_counts.add_record('test', 'C', 4452)

        store = gitlapse.TsvFormattingStore()
        store.store(first_counts)
        store.store(second_counts)
                
        lines = store.as_csv().split('\n')
        assert_equal(lines[0], 'Date\ttest-C\ttest-Java\tsrc-Java')
        assert_equal(lines[1], '1st March\t4452\t124\t123')
            

class CompositeAnalyserTests(unittest.TestCase):

    def test_should_invoke_all_delegates(self):
        delegate1 = MockAnalyser()
        delegate2 = MockAnalyser()

        composite = gitlapse.CompositeAnalyser([delegate1, delegate2])

        composite.analyse('hash1', 'date2')

        assert_equals('hash1', delegate1.analysed)
        assert_equals('date2', delegate1.commit_date)
        assert_equals('hash1', delegate2.analysed)
        assert_equals('date2', delegate2.commit_date)

class GitLapseTests(unittest.TestCase):

    def test_can_generate_gnuplot_for_table_data(self):
        table_data = "Date	test-Javascript	test-Java	src-Java	web-Javascript	web-PHP"
        gnuplot_data = gitlapse.to_gnuplot(table_data)
        assert_equals("""plot "line_count_by_time.tsv" using 1:4 title "test-Javascript", \
"line_count_by_time.tsv" using 1:5 title "test-Java", \
"line_count_by_time.tsv" using 1:6 title "src-Java", \
"line_count_by_time.tsv" using 1:7 title "web-Javascript", \
"line_count_by_time.tsv" using 1:8 title "web-PHP", \
""", gnuplot_data)

class MockAnalyser():

        def __init__(self):
            self.analysed = None
        
        def analyse(self, commit_hash, commit_date):
            self.analysed = commit_hash
            self.commit_date = commit_date

class SkippingAnalyserTests(unittest.TestCase):

    class MockGitRepo():

        def __init__(self):
            self.last_hard_reset = None

        def hard_reset(self, last_hard_reset):
            self.last_hard_reset = last_hard_reset

    def test_should_not_invoke_analyser_if_commit_limit_not_reached(self):
        mock_analyser_delegate = MockAnalyser()
        mock_git_repo = self.MockGitRepo()

        skipping_analyser = gitlapse.SkippingAnalyser(skipping_commits = 2, delegate_analyser = mock_analyser_delegate, git_repo = mock_git_repo)
        skipping_analyser.analyse('some_hash', 'some_date')

        assert_equals(None, mock_analyser_delegate.analysed)
        assert_equals(None, mock_git_repo.last_hard_reset)

    def test_should_only_invoke_analyser_if_commit_limit_reached(self):
        mock_analyser_delegate = MockAnalyser()
        mock_git_repo = self.MockGitRepo()

        skipping_analyser = gitlapse.SkippingAnalyser(skipping_commits = 1, delegate_analyser = mock_analyser_delegate, git_repo = mock_git_repo)
        skipping_analyser.analyse('some_hash', 'some_date')
        skipping_analyser.analyse('some_other_hash', 'some_other_date')

        assert_equals('some_other_hash', mock_analyser_delegate.analysed)
        assert_equals('some_other_hash', mock_git_repo.last_hard_reset)


class LinesOfCodeAnalyserTests(unittest.TestCase):

    class MockParser:
        def __init__(self, returning):
            self.returning = returning
            self.last_parse = None

        def parse(self, date, commit, src, string_to_parse):
            self.last_parse = string_to_parse
            return self.returning

    class MockTimeSeriesStore:
        def __init__(self):
            self.last_store = None

        def store(self, what_to_store):
            self.last_store = what_to_store

    def test_should_invoke_cloc_on_source_directory(self):
        mock_executor = MockExecutor('cloc_output')
        mock_parser = self.MockParser(returning = 'lines_of_code_data')
        mock_store = self.MockTimeSeriesStore()

        analyser = gitlapse.LinesOfCodeAnalyser(executor = mock_executor, parser = mock_parser, running_from = '/running/from', data_store = mock_store, abs_src_directory = '/path/to/src')

        analyser.analyse('some_hash', None)
        assert_equals('perl /running/from/tools/cloc-1.08.pl /path/to/src --csv --exclude-lang=CSS,HTML,XML --quiet', mock_executor.last_command)
        assert_equals('cloc_output', mock_parser.last_parse)
        assert_equals('lines_of_code_data', mock_store.last_store)

class EndToEndTests(unittest.TestCase):

    @attr('large')
    def test_end_to_end(self):
        tmp_dir = tempfile.mkdtemp()
        shutil.copytree('.git', tmp_dir + '/repodir')
        gitlapse.main(['--git_repo_dir', tmp_dir + '/repodir', '--working_dir', tmp_dir, '--frequency_of_sample', '5', '--results_dir', tmp_dir, '--source_dir', '.'])
        files = os.listdir(tmp_dir)
        assert_true('line_count_by_time.tsv' in files, 'Cannot find results in ' + str(files))


if __name__ == "__main__":
    main()
