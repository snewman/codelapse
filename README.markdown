About
-----

Codelapse runs against a local Git repo to extract metrics over the
lifecycle of the codebase. Currently, inly lines of code are
supported, but toxicity over time (powered by checktyle) is planned
for the near future.

Its core job is to generate the raw data for further analysis,
although some basic support to produce gnuplot output is planned to
enable simple-case graphing.

Requirements
------------

codelapse has been built & tested on OSX using Python 2.6 (although it should work on
any *NIX system). It currently does not require any non-standard
python libraries, however it does assume that perl is on the path (to
run cloc).

Building
--------

You'll need nose and coverage if you want to run the tests:

$ sudo easy_setup nose
$ sudo easy_setup coverage

Then to run the tests:

$ ./run.sh

