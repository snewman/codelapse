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

