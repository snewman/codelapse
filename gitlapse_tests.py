import nose
from nose.tools import *
from gitlapse import *

def main():
    nosemain()

def test_can_create_record():
    cloc_line = "10,Bourne Shell,56,155,252,3.81,960.12"
    record = create_record('2009-01-29 16:37:36 +0000', '36b40c7c1168726cc63ad9b7d63d5d209d02da90', cloc_line)
    assert_equal(record.records['Bourne Shell'], 252)

if __name__ == "__main__":
    main()
