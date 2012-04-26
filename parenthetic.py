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

# map from english to extreme scheme
to_scheme = defaultdict(lambda:None)
for k,v in to_english.iteritems():
    to_scheme[v] = k

def ParseError(errorString = 'unmatched parens'):
    print "Error: " + errorString
    os._exit(0)
    #raise Exception('paren mismatch')
    
def bracketsMatch(chars):
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

# parse the tokens into an AST
def parse(tokens):
    # check for errors
    if not bracketsMatch(tokens):
        ParseError('paren mismatch')
    #elif len(tokens) < 2:
    #    ParseError('too few tokens in: "' + ''.join(tokens) + '"')
    
    # to return - a list of exprs
    exprs = []
    for expr in get_exprs(tokens):
        # check for errors
        if len(expr) < 2:
            ParseError('too few tokens in: ' + ''.join(tokens))
        elif expr[0] != '(' or expr[-1] != ')':
            ParseError('expression found without () as wrapper')
        
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

# define some functions built into the default environment

def builtin_accumulate(init, accumulate, environment, params):
    result = init
    for param in params:
        value = interpret(param, environment)
        try: result = accumulate(result, value)
        except: ParseError(str(value) + ' is not the correct type')
    return result

def builtin_plus(environment, params):
    if len(params) >= 1:
        return builtin_accumulate(interpret(params[0], environment), operator.add, environment, params[1:])
    else:
        return 0.0

def builtin_minus(environment, params):
    if len(params) == 0:
        ParseError('subtraction requires at least 1 param')
    return builtin_accumulate(interpret(params[0], environment), operator.sub, environment, params[1:])

def builtin_mult(environment, params):
    return builtin_accumulate(1.0, operator.mul, environment, params)

def builtin_div(environment, params):
    if len(params) == 0:
        ParseError('division requires at least 1 param')
    return builtin_accumulate(interpret(params[0], environment), operator.div, environment, params[1:])

def builtin_LE(environment, params):
    return interpret(params[0], environment) <= interpret(params[1], environment)

def builtin_lambda(environment, params):
    
    bodies = [body for body in params[1:]]
    params = params[0][1]
    if len(bodies) == 0:
        ParseError("a function had no body")
    for kind, name in params:
        if kind != 'symbol':
            ParseError('lambda must have only symbols as arguments')

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
            ParseError("Error evaluating a function")
    return ret
        
def builtin_equal(environment, params):
    for param1, param2 in izip(params[:-1], params[1:]):
        if interpret(param1, environment) != interpret(param2, environment):
            return False
    return True

def builtin_if(environment, params):
    if len(params) != 3:
        ParseError("'if' takes in exactly 3 params")
    
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
        ParseError("car must only be called on tuples")
    return result[0]

def builtin_cdr(environment, params):
    result = interpret(params[0], environment)
    if not isinstance(result, tuple):
        ParseError("cdr must only be called on tuples")
    return result[1]

def builtin_char(environment, params):
    result = interpret(params[0], environment)
    if result != int(result):
        ParseError("char must only be called on integers")
    return chr(int(result))

def builtin_string(environment, params):
    result = ''
    cur = interpret(params[0], environment)
    while cur != ():
        if not isinstance(cur, tuple) or not isinstance(cur[1], tuple):
            ParseError("string only works on lists of chars")
        result += cur[0]
        cur = cur[1]
    return result

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

def interpret_trees(trees, environment, doprint = True):
    """Interpret a sequence of same-level trees (may contain defines)
    and output the result"""

    environment = copy.copy(environment)

    # hoist define statements (note: trees.sort is stable)
    trees.sort(key = lambda x: 0 if x[0] == 'expr' and x[1][0][1] == to_scheme['define'] else 1)
    ret = None
    for tree in trees:
        if tree[0] == 'expr' and tree[1][0][0] == 'symbol' and tree[1][0][1] == to_scheme['define']:
            try:
                symbol = tree[1][1]
                if symbol[0] != 'symbol':
                    ParseError('first argument to define must be a symbol')
                symbol = symbol[1]
                value = tree[1][2]
                environment[symbol] = interpret(value, environment)
            except:
                ParseError('error evaluating define statement')
        else:
            ret = interpret(tree, environment)
            if doprint:
                print ret
    return ret


def interpret(tree, environment):
    """Interpret a single tree (may not be a define) and return the result"""
    kind, value = tree
    if kind == 'num':
        return float(value)
    elif kind == 'symbol':
        if value in environment:
            return environment[value]
        else:
            ParseError('Unresolved symbol - ' + value)
    elif kind == 'expr':
        function = interpret(value[0], environment)
        if not hasattr(function, '__call__'):
            ParseError('Symbol "'+value[0]+'" is not a function.')
        return function(environment, value[1:])
    else:
        ParseError("Unknown tree kind")

# read in the code ignoring all characters but '(' and ')' 
code = []
for line in sys.stdin.readlines():
    code += [c for c in line if c in '()']

try:
    syntax_trees = parse(code)
    interpret_trees(syntax_trees, default_environment)
except:
    print 'Parenthesis Mismatch'