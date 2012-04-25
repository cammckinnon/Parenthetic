import os, sys, subprocess

i = 0

def fail(test,s):
    print "...failed!"
    print s
    print "Total tests passed: "+ str(i) +" / " + str(len(tests))
    sys.exit()

print "Running tests...\n"

tests  = map(lambda s: ''.join(s.split('.')[0:-1]),filter(lambda s: s.split('.')[-1] =='in', os.listdir('./tests')))


for test in tests:
    if not os.path.exists("./tests/" + test + ".out"):
        fail(test, "No .out file for test '" + test + "'.")
    
    with open("./tests/" + test + ".out") as f:
        expected = ''.join([c for c in str.strip(''.join(f.readlines())) if c not in ["\r"]])
        actual = ''.join([c for c in str.strip(subprocess.check_output("cat ./tests/"+test+".in | python parenthetic.py",shell=True)) if c not in ["\r"]])
        print str(i+1) + ". " + test,
        if expected != actual:
            fail(test,"Incorrect output. \nExpected output: \n" + expected + "\nActual output: \n"+actual)
        
        i += 1
        print "... good.\n(" + str(i) + "/" + str(len(tests)) + " tests passed)"

print "\nCongratulations! All " + str(len(tests)) + " tests passed successfully."