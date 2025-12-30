# MiniCPP: a tiny C++-like interpreter in pure Python
# Features: variables with types, expressions, if/else, switch, for/while, print, input, comments

import sys
import re

# ----------------------------
# Tokenizer
# ----------------------------

TT = {
    'IDENT': 'IDENT', 'INT': 'INT', 'FLOAT': 'FLOAT', 'STRING': 'STRING',
    'BOOL': 'BOOL', 'OP': 'OP', 'KW': 'KW', 'SYM': 'SYM', 'EOF': 'EOF'
}

KEYWORDS = {
    'int', 'float', 'string', 'bool',
    'if', 'else', 'while', 'for', 'switch', 'case', 'default', 'break',
    'true', 'false', 'print', 'input'
}

SYMBOLS = {
    '(', ')', '{', '}', ';', ',', ':'
}

OPERATORS = [
    '==', '!=', '<=', '>=', '&&', '||',
    '+', '-', '*', '/', '%', '<', '>', '=', '!', 
]

WS = re.compile(r'\s+')

class Token:
    def __init__(self, typ, val, pos):
        self.typ = typ
        self.val = val
        self.pos = pos
    def __repr__(self):
        return f'Token({self.typ},{self.val})'

class Lexer:
    def __init__(self, src):
        self.src = src
        self.i = 0
        self.n = len(src)

    def peek(self):
        return self.src[self.i] if self.i < self.n else ''

    def advance(self, k=1):
        self.i += k

    def skip_ws_and_comments(self):
        while self.i < self.n:
            m = WS.match(self.src, self.i)
            if m:
                self.i = m.end()
                continue
            if self.src.startswith('//', self.i):
                # line comment
                while self.i < self.n and self.src[self.i] != '\n':
                    self.i += 1
                continue
            break

    def string_lit(self):
        assert self.src[self.i] == '"'
        self.i += 1
        out = []
        while self.i < self.n:
            c = self.src[self.i]
            if c == '"':
                self.i += 1
                return ''.join(out)
            if c == '\\':
                if self.i+1 < self.n:
                    nxt = self.src[self.i+1]
                    if nxt == 'n': out.append('\n')
                    elif nxt == 't': out.append('\t')
                    elif nxt == '"': out.append('"')
                    elif nxt == '\\': out.append('\\')
                    else: out.append(nxt)
                    self.i += 2
                    continue
            out.append(c)
            self.i += 1
        raise SyntaxError('Unterminated string literal')

    def number(self):
        start = self.i
        has_dot = False
        while self.i < self.n and (self.src[self.i].isdigit() or self.src[self.i] == '.'):
            if self.src[self.i] == '.':
                if has_dot:
                    break
                has_dot = True
            self.i += 1
        s = self.src[start:self.i]
        if s.count('.') == 1:
            return ('FLOAT', float(s))
        else:
            return ('INT', int(s))

    def ident_or_kw(self):
        start = self.i
        while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] == '_'):
            self.i += 1
        s = self.src[start:self.i]
        if s in KEYWORDS:
            if s in ('true', 'false'):
                return Token(TT['BOOL'], s == 'true', start)
            return Token(TT['KW'], s, start)
        return Token(TT['IDENT'], s, start)

    def operator(self):
        # try longest match
        for op in sorted(OPERATORS, key=len, reverse=True):
            if self.src.startswith(op, self.i):
                self.i += len(op)
                return Token(TT['OP'], op, self.i)
        return None

    def symbol(self):
        c = self.src[self.i]
        if c in SYMBOLS:
            self.i += 1
            return Token(TT['SYM'], c, self.i)
        return None

    def tokens(self):
        toks = []
        while True:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                toks.append(Token(TT['EOF'], '', self.i))
                break
            c = self.peek()
            if c == '"':
                s = self.string_lit()
                toks.append(Token(TT['STRING'], s, self.i))
                continue
            if c.isdigit():
                kind, val = self.number()
                toks.append(Token(TT[kind], val, self.i))
                continue
            if c.isalpha() or c == '_':
                toks.append(self.ident_or_kw())
                continue
            op = self.operator()
            if op:
                toks.append(op)
                continue
            sym = self.symbol()
            if sym:
                toks.append(sym)
                continue
            raise SyntaxError(f'Unexpected char {c!r} at {self.i}')
        return toks

# ----------------------------
# Parser and AST
# ----------------------------

class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def cur(self):
        return self.toks[self.i]

    def match(self, typ=None, val=None):
        t = self.cur()
        if (typ is None or t.typ == typ) and (val is None or t.val == val):
            self.i += 1
            return t
        return None

    def expect(self, typ=None, val=None):
        t = self.match(typ, val)
        if not t:
            raise SyntaxError(f'Expected {typ or val}, got {self.cur()}')
        return t

    # Grammar:
    # program: stmt*
    # stmt: var_decl ';' | assign ';' | print ';' | if | while | for | block | switch | break ';'
    # var_decl: type IDENT ('=' expr)?
    # assign: IDENT '=' expr
    # print: 'print' '(' expr ')' 
    # input: 'input' '(' ')'
    # block: '{' stmt* '}'
    # if: 'if' '(' expr ')' stmt ('else' stmt)?
    # while: 'while' '(' expr ')' stmt
    # for: 'for' '(' var_decl ';' expr ';' assign ')' stmt
    # switch: 'switch' '(' expr ')' '{' (case)+ (default)? '}'
    # case: 'case' expr ':' block_or_stmt
    # default: 'default' ':' block_or_stmt
    # expr: logic_or
    # logic_or: logic_and ('||' logic_and)*
    # logic_and: equality ('&&' equality)*
    # equality: rel (('=='|'!=') rel)*
    # rel: add (('<'|'>'|'<='|'>=') add)*
    # add: mul (('+'|'-') mul)*
    # mul: unary (('*'|'/'|'%') unary)*
    # unary: ('!'|'-') unary | primary
    # primary: literal | IDENT | type '(' expr ')' | '(' expr ')' | input '(' ')'

    def parse(self):
        stmts = []
        while not self.match(TT['EOF']):
            stmts.append(self.statement())
        return ('program', stmts)

    def statement(self):
        t = self.cur()
        if t.typ == TT['SYM'] and t.val == '{':
            return self.block()
        if t.typ == TT['KW'] and t.val == 'if':
            return self.if_stmt()
        if t.typ == TT['KW'] and t.val == 'while':
            return self.while_stmt()
        if t.typ == TT['KW'] and t.val == 'for':
            return self.for_stmt()
        if t.typ == TT['KW'] and t.val == 'switch':
            return self.switch_stmt()
        if t.typ == TT['KW'] and t.val in ('int','float','string','bool'):
            node = self.var_decl()
            self.expect(TT['SYM'], ';')
            return node
        if t.typ == TT['KW'] and t.val == 'print':
            node = self.print_stmt()
            self.expect(TT['SYM'], ';')
            return node
        if t.typ == TT['KW'] and t.val == 'break':
            self.expect(TT['KW'], 'break')
            self.expect(TT['SYM'], ';')
            return ('break',)
        # assignment
        if t.typ == TT['IDENT']:
            node = self.assign()
            self.expect(TT['SYM'], ';')
            return node
        raise SyntaxError(f'Unexpected token in statement: {t}')

    def block(self):
        self.expect(TT['SYM'], '{')
        items = []
        while not self.match(TT['SYM'], '}'):
            items.append(self.statement())
        return ('block', items)

    def var_decl(self):
        typ = self.expect(TT['KW']).val
        name = self.expect(TT['IDENT']).val
        init = None
        if self.match(TT['OP'], '='):
            init = self.expr()
        return ('var_decl', typ, name, init)

    def assign(self):
        name = self.expect(TT['IDENT']).val
        self.expect(TT['OP'], '=')
        e = self.expr()
        return ('assign', name, e)

    def print_stmt(self):
        self.expect(TT['KW'], 'print')
        self.expect(TT['SYM'], '(')
        e = self.expr()
        self.expect(TT['SYM'], ')')
        return ('print', e)

    def if_stmt(self):
        self.expect(TT['KW'], 'if')
        self.expect(TT['SYM'], '(')
        cond = self.expr()
        self.expect(TT['SYM'], ')')
        then = self.statement()
        else_branch = None
        if self.match(TT['KW'], 'else'):
            else_branch = self.statement()
        return ('if', cond, then, else_branch)

    def while_stmt(self):
        self.expect(TT['KW'], 'while')
        self.expect(TT['SYM'], '(')
        cond = self.expr()
        self.expect(TT['SYM'], ')')
        body = self.statement()
        return ('while', cond, body)

    def for_stmt(self):
        self.expect(TT['KW'], 'for')
        self.expect(TT['SYM'], '(')
        init = self.var_decl()
        self.expect(TT['SYM'], ';')
        cond = self.expr()
        self.expect(TT['SYM'], ';')
        step = self.assign()
        self.expect(TT['SYM'], ')')
        body = self.statement()
        return ('for', init, cond, step, body)

    def switch_stmt(self):
        self.expect(TT['KW'], 'switch')
        self.expect(TT['SYM'], '(')
        scrut = self.expr()
        self.expect(TT['SYM'], ')')
        self.expect(TT['SYM'], '{')
        cases = []
        default = None
        while not self.match(TT['SYM'], '}'):
            if self.match(TT['KW'], 'case'):
                val = self.expr()
                self.expect(TT['SYM'], ':')
                stmt = self.statement()
                cases.append(('case', val, stmt))
            elif self.match(TT['KW'], 'default'):
                self.expect(TT['SYM'], ':')
                default = self.statement()
            else:
                raise SyntaxError(f'Unexpected token in switch: {self.cur()}')
        return ('switch', scrut, cases, default)

    # Expressions
    def expr(self):
        return self.logic_or()

    def logic_or(self):
        left = self.logic_and()
        while self.match(TT['OP'], '||'):
            right = self.logic_and()
            left = ('binop', '||', left, right)
        return left

    def logic_and(self):
        left = self.equality()
        while self.match(TT['OP'], '&&'):
            right = self.equality()
            left = ('binop', '&&', left, right)
        return left

    def equality(self):
        left = self.rel()
        while True:
            if self.match(TT['OP'], '=='):
                right = self.rel()
                left = ('binop', '==', left, right)
            elif self.match(TT['OP'], '!='):
                right = self.rel()
                left = ('binop', '!=', left, right)
            else:
                break
        return left

    def rel(self):
        left = self.add()
        while True:
            if self.match(TT['OP'], '<'):
                right = self.add()
                left = ('binop', '<', left, right)
            elif self.match(TT['OP'], '>'):
                right = self.add()
                left = ('binop', '>', left, right)
            elif self.match(TT['OP'], '<='):
                right = self.add()
                left = ('binop', '<=', left, right)
            elif self.match(TT['OP'], '>='):
                right = self.add()
                left = ('binop', '>=', left, right)
            else:
                break
        return left

    def add(self):
        left = self.mul()
        while True:
            if self.match(TT['OP'], '+'):
                right = self.mul()
                left = ('binop', '+', left, right)
            elif self.match(TT['OP'], '-'):
                right = self.mul()
                left = ('binop', '-', left, right)
            else:
                break
        return left

    def mul(self):
        left = self.unary()
        while True:
            if self.match(TT['OP'], '*'):
                right = self.unary()
                left = ('binop', '*', left, right)
            elif self.match(TT['OP'], '/'):
                right = self.unary()
                left = ('binop', '/', left, right)
            elif self.match(TT['OP'], '%'):
                right = self.unary()
                left = ('binop', '%', left, right)
            else:
                break
        return left

    def unary(self):
        if self.match(TT['OP'], '!'):
            return ('unary', '!', self.unary())
        if self.match(TT['OP'], '-'):
            return ('unary', '-', self.unary())
        return self.primary()

    def primary(self):
        t = self.cur()
        if self.match(TT['SYM'], '('):
            e = self.expr()
            self.expect(TT['SYM'], ')')
            return e
        if t.typ == TT['INT']:
            self.i += 1
            return ('lit', ('int', t.val))
        if t.typ == TT['FLOAT']:
            self.i += 1
            return ('lit', ('float', t.val))
        if t.typ == TT['STRING']:
            self.i += 1
            return ('lit', ('string', t.val))
        if t.typ == TT['BOOL']:
            self.i += 1
            return ('lit', ('bool', t.val))
        if t.typ == TT['KW'] and t.val == 'input':
            self.i += 1
            self.expect(TT['SYM'], '('); self.expect(TT['SYM'], ')')
            return ('input',)
        if t.typ == TT['IDENT']:
            self.i += 1
            return ('var', t.val)
        # type constructor like int(expr)
        if t.typ == TT['KW'] and t.val in ('int','float','string','bool'):
            cast_type = t.val
            self.i += 1
            self.expect(TT['SYM'], '(')
            e = self.expr()
            self.expect(TT['SYM'], ')')
            return ('cast', cast_type, e)
        raise SyntaxError(f'Unexpected token in expression: {t}')

# ----------------------------
# Runtime / Interpreter
# ----------------------------

class MiniCPPError(Exception):
    pass

def type_default(tname):
    if tname == 'int': return 0
    if tname == 'float': return 0.0
    if tname == 'string': return ""
    if tname == 'bool': return False
    raise MiniCPPError(f'Unknown type {tname}')

def cast_value(tname, val):
    try:
        if tname == 'int':
            if isinstance(val, bool): return int(val)
            if isinstance(val, (int,float)): return int(val)
            s = str(val).strip()
            if s == '':
                raise MiniCPPError(f'Cannot cast empty string to {tname}')
            return int(s)

        if tname == 'float':
            if isinstance(val, bool): return float(val)
            if isinstance(val, (int,float)): return float(val)
            return float(str(val))
        if tname == 'string':
            return str(val)
        if tname == 'bool':
            if isinstance(val, bool): return val
            if isinstance(val, (int,float)): return val != 0
            s = str(val).strip().lower()
            return s in ('true','1','yes')
    except Exception as e:
        raise MiniCPPError(f'Cast error to {tname}: {e}')
    raise MiniCPPError(f'Unknown cast {tname}')

class Env:
    def __init__(self):
        self.vars = {}  # name -> (type, value)

    def declare(self, t, name, init=None):
        if name in self.vars:
            raise MiniCPPError(f'Variable {name} already declared')
        val = type_default(t) if init is None else cast_value(t, eval_expr(init, self))
        self.vars[name] = (t, val)

    def assign(self, name, expr):
        if name not in self.vars:
            raise MiniCPPError(f'Undefined variable {name}')
        t, _ = self.vars[name]
        val = cast_value(t, eval_expr(expr, self))
        self.vars[name] = (t, val)

    def get(self, name):
        if name not in self.vars:
            raise MiniCPPError(f'Undefined variable {name}')
        return self.vars[name][1]

    def get_type(self, name):
        if name not in self.vars:
            raise MiniCPPError(f'Undefined variable {name}')
        return self.vars[name][0]

def eval_expr(node, env: Env):
    kind = node[0]
    if kind == 'lit':
        tname, v = node[1]
        return v
    if kind == 'var':
        return env.get(node[1])
    if kind == 'cast':
        tname, expr = node[1], node[2]
        return cast_value(tname, eval_expr(expr, env))
    if kind == 'input':
        return input()
    if kind == 'unary':
        op, e = node[1], node[2]
        v = eval_expr(e, env)
        if op == '!': return not bool(v)
        if op == '-': 
            if isinstance(v, (int,float)): return -v
            raise MiniCPPError('Unary - requires numeric')
        raise MiniCPPError(f'Unknown unary {op}')
    if kind == 'binop':
        op, l, r = node[1], node[2], node[3]
        lv = eval_expr(l, env)
        rv = eval_expr(r, env)
        if op == '+':
            # string concatenation allowed
            if isinstance(lv, str) or isinstance(rv, str):
                return str(lv) + str(rv)
            return lv + rv
        if op == '-': return lv - rv
        if op == '*': return lv * rv
        if op == '/': return lv / rv
        if op == '%': return lv % rv
        if op == '==': return lv == rv
        if op == '!=': return lv != rv
        if op == '<': return lv < rv
        if op == '>': return lv > rv
        if op == '<=': return lv <= rv
        if op == '>=': return lv >= rv
        if op == '&&': return bool(lv) and bool(rv)
        if op == '||': return bool(lv) or bool(rv)
        raise MiniCPPError(f'Unknown binop {op}')
    raise MiniCPPError(f'Unknown expr node {node}')

class BreakSignal(Exception):
    pass

def exec_stmt(node, env: Env):
    tag = node[0]
    if tag == 'var_decl':
        _, t, name, init = node
        env.declare(t, name, init)
        return
    if tag == 'assign':
        _, name, expr = node
        env.assign(name, expr)
        return
    if tag == 'print':
        _, expr = node
        v = eval_expr(expr, env)
        print(v)
        return
    if tag == 'block':
        _, items = node
        for s in items:
            exec_stmt(s, env)
        return
    if tag == 'if':
        _, cond, then, else_branch = node
        if bool(eval_expr(cond, env)):
            exec_stmt(then, env)
        elif else_branch:
            exec_stmt(else_branch, env)
        return
    if tag == 'while':
        _, cond, body = node
        while bool(eval_expr(cond, env)):
            try:
                exec_stmt(body, env)
            except BreakSignal:
                break
        return
    if tag == 'for':
        _, init, cond, step, body = node
        exec_stmt(init, env)
        while bool(eval_expr(cond, env)):
            try:
                exec_stmt(body, env)
            except BreakSignal:
                pass
            exec_stmt(step, env)
        return
    if tag == 'switch':
        _, scrut, cases, default = node
        val = eval_expr(scrut, env)
        matched = False
        for _, cval, stmt in cases:
            if eval_expr(cval, env) == val:
                try:
                    exec_stmt(stmt, env)
                except BreakSignal:
                    pass
                matched = True
                break
        if not matched and default:
            try:
                exec_stmt(default, env)
            except BreakSignal:
                pass
        return
    if tag == 'break':
        raise BreakSignal()
    if tag == 'program':
        _, items = node
        for s in items:
            exec_stmt(s, env)
        return
    raise MiniCPPError(f'Unknown statement node {node}')

def run(source: str):
    lex = Lexer(source)
    toks = lex.tokens()
    parser = Parser(toks)
    ast = parser.parse()
    env = Env()
    exec_stmt(ast, env)

# ------------- CLI -------------

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("MiniCPP interpreter. Paste code, end with Ctrl-D (Unix) or Ctrl-Z (Windows).")
        src = sys.stdin.read()
        run(src)
    else:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            run(f.read())
