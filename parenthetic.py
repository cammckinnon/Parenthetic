from collections import defaultdict
from itertools import izip
import copy
import operator
import os
import sys

# map from paren strings to english names
# for the predefined symbols (lambda, etc)
to_english = defaultdict(lambda:None,\
    {'()': 'lambda',
     '()()': 'define',
     '(())': 'plus',
     '(()())': 'minus',
     '()(())': 'mult',
     '(())()': 'div',
     '()()()': 'if',
     '(())(())': 'equal',
     '()(())()': 'LE',
     '()(()())': 'not',
     '((()))': 'empty',
     '((()))()': 'cons',
     '((()))(())': 'car',
     '((()))()()': 'cdr',
     '(())(())()': 'char',
     '(())()(())': 'string'})

# map from english to parenthetic
to_scheme = defaultdict(lambda:None)
for k,v in to_english.iteritems():
    to_scheme[v] = k

def Error(errorString = 'unmatched parens', debug_mode = False):
    """Handle errors. If in debug_mode, prints the error string.
    Otherwise raises an exception to trigger the ambiguous
    'Parenthesis Mismatch' error.
    """
    
    if debug_mode:
        print "Error: " + errorString
        sys.exit()
    else:
        raise Exception('paren mismatch')
    
def bracketsMatch(chars):
    """Returns False if any parentheses in `chars` are not matched
    properly. Returns True otherwise.
    """

    level = 0
    for p in chars:
        if p == '(':
            level += 1
        elif p == ')':
            level -= 1
        if level < 0:
            return False
    
    return level == 0

def get_exprs(chars):
    """Returns a list of character sequences such that for each sequence,
    the first and last parenthesis match.

    For example, "(())()()" would be split into ["(())", "()", "()"]
    """

    level = 0
    current = []
    for p in chars:
        if p == '(' or p == ')':
            current.append(p)
        if p == '(':
            level += 1
        elif p == ')':
            level -= 1
        if level == 0:
            yield current
            current = []



## built-in functions ##
def builtin_accumulate(init, accumulate, environment, params):
    """Helper function that handles common logic for builtin functions.

    Given an initial value, and a two-parameter function, the environment, and
    a list of params to reduce, this function will reduce [init] + params using
    the accumulate function and finally returns the resulting value.
    """
    result = init
    for param in params:
        value = interpret(param, environment)
        try: result = accumulate(result, value)
        except: Error(str(value) + ' is not the correct type')
    return result

def builtin_plus(environment, params):
    if len(params) >= 1:
        return builtin_accumulate(interpret(params[0], environment), operator.add, environment, params[1:])
    else:
        return 0.0

def builtin_minus(environment, params):
    if len(params) == 0:
        Error('subtraction requires at least 1 param')
    return builtin_accumulate(interpret(params[0], environment), operator.sub, environment, params[1:])

def builtin_mult(environment, params):
    return builtin_accumulate(1.0, operator.mul, environment, params)

def builtin_div(environment, params):
    if len(params) == 0:
        Error('division requires at least 1 param')
    return builtin_accumulate(interpret(params[0], environment), operator.div, environment, params[1:])

def builtin_LE(environment, params):
    return interpret(params[0], environment) <= interpret(params[1], environment)

def builtin_lambda(environment, params):
    
    bodies = [body for body in params[1:]]
    params = params[0][1]
    if len(bodies) == 0:
        Error("a function had no body")
    for kind, name in params:
        if kind != 'symbol':
            Error('lambda must have only symbols as arguments')

    def ret(old_environment, arguments):
        #print bodies
        try:
            # create new environment based on args
            environment = copy.copy(old_environment)
            for param, arg in izip(params, arguments):
                environment[param[1]] = interpret(arg, old_environment)
            # evaluate the function bodies using the new environment
            return interpret_trees(bodies, environment, False)
        except:
            Error("Error evaluating a function")
    return ret
        
def builtin_equal(environment, params):
    for param1, param2 in izip(params[:-1], params[1:]):
        if interpret(param1, environment) != interpret(param2, environment):
            return False
    return True

def builtin_if(environment, params):
    if len(params) != 3:
        Error("'if' takes in exactly 3 params")
    
    if interpret(params[0], environment):
        return interpret(params[1], environment)
    return interpret(params[2], environment)

def builtin_not(environment, params):
    return False if interpret(params[0], environment) else True

def builtin_cons(environment, params):
    return (interpret(params[0], environment), interpret(params[1], environment))

def builtin_car(environment, params):
    result = interpret(params[0], environment)
    if not isinstance(result, tuple):
        Error("car must only be called on tuples")
    return result[0]

def builtin_cdr(environment, params):
    result = interpret(params[0], environment)
    if not isinstance(result, tuple):
        Error("cdr must only be called on tuples")
    return result[1]

def builtin_char(environment, params):
    result = interpret(params[0], environment)
    if result != int(result):
        Error("char must only be called on integers")
    return chr(int(result))

def builtin_string(environment, params):
    result = ''
    cur = interpret(params[0], environment)
    while cur != ():
        if not isinstance(cur, tuple) or not isinstance(cur[1], tuple):
            Error("string only works on lists of chars")
        result += cur[0]
        cur = cur[1]
    return result

# define the default (top-level) scope
default_environment = \
    {to_scheme['plus']: builtin_plus,
     to_scheme['minus']: builtin_minus,
     to_scheme['mult']: builtin_mult,
     to_scheme['div']: builtin_div,
     to_scheme['lambda']: builtin_lambda,
     to_scheme['if']: builtin_if,
     to_scheme['equal']: builtin_equal,
     to_scheme['LE']: builtin_LE,
     to_scheme['not']: builtin_not,
     to_scheme['empty']: (),
     to_scheme['car']: builtin_car,
     to_scheme['cdr']: builtin_cdr,
     to_scheme['cons']: builtin_cons,
     to_scheme['char']: builtin_char,
     to_scheme['string']: builtin_string}

# parse the tokens into an AST
def parse(tokens):
    """Accepts a list of parentheses and returns a list of ASTs.

    Each AST is a pair (type, value).
    If type is 'symbol', value will be the paren sequence corresponding
    to the symbol.
    If type is 'int', value will be a float that is equal to an int.
    If type is expr, value will be a list of ASTs.
    """

    # check for errors
    if not bracketsMatch(tokens):
        Error('paren mismatch')
    # to return - a list of exprs
    exprs = []
    for expr in get_exprs(tokens):
        # check for errors
        if len(expr) < 2:
            Error('too few tokens in: ' + ''.join(tokens))
        elif expr[0] != '(' or expr[-1] != ')':
            Error('expression found without () as wrapper')
        
        # pop off starting and ending ()s
        expr = expr[1:-1]
        
        # symbol
        if expr[:2] == ['(', ')'] and len(expr) > 2:
            exprs.append(('symbol', ''.join(expr[2:])))
        # integer
        elif expr[:4] == ['(', '(', ')', ')'] and len(expr) >= 4:
            exprs.append(('num', expr[4:].count('(')))
        # expr
        else:
            exprs.append(('expr', parse(expr)))

    return exprs


def interpret(tree, environment):
    """Interpret a single tree (may not be a define) and return the result"""
    kind, value = tree
    if kind == 'num':
        return float(value)
    elif kind == 'symbol':
        if value in environment:
            return environment[value]
        else:
            Error('Unresolved symbol - ' + value)
    elif kind == 'expr':
        function = interpret(value[0], environment)
        if not hasattr(function, '__call__'):
            Error('Symbol "'+value[0]+'" is not a function.')
        return function(environment, value[1:])
    else:
        Error("Unknown tree kind")

def interpret_trees(trees, environment, doprint = True):
    """Interpret a sequence of trees (may contain defines)
    and output the result.

    The trees passed in should be ASTs as returned by parse().
    If doprint is true, the post-interpretation value of each tree is printed.
    """

    environment = copy.copy(environment)

    # hoist define statements (note: trees.sort is stable)
    trees.sort(key = lambda x: 0 if x[0] == 'expr' and x[1][0][1] == to_scheme['define'] else 1)
    ret = None
    for tree in trees:
        if tree[0] == 'expr' and tree[1][0][0] == 'symbol' and tree[1][0][1] == to_scheme['define']:
            try:
                symbol = tree[1][1]
                if symbol[0] != 'symbol':
                    Error('first argument to define must be a symbol')
                symbol = symbol[1]
                value = tree[1][2]
                environment[symbol] = interpret(value, environment)
            except:
                Error('error evaluating define statement')
        else:
            ret = interpret(tree, environment)
            if doprint:
                print ret
    return ret

# read in the code ignoring all characters but '(' and ')' 
code = []
for line in sys.stdin.readlines():
    code += [c for c in line if c in '()']

# parse and interpret the code. print 'Parenthesis Mismatch'
# if an error occured.
try:
    syntax_trees = parse(code)
    interpret_trees(syntax_trees, default_environment)
except:
    print 'Parenthesis Mismatch'