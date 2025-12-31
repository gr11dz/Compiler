import sys
import re
from typing import List, Tuple, Optional, Any, Dict

# -------------------------------
# Lexer
# -------------------------------

KEYWORDS = {
    "int", "float", "string", "bool",
    "if", "else", "while", "for", "switch", "case", "default", "break",
    "cin", "cout", "endl", "true", "false"
}

TOKEN_SPEC = [
    ("COMMENT",   r"//[^\n]*"),
    ("MCOMMENT",  r"/\*.*?\*/"),
    ("STRING",    r'"[^"\n]*"'),
    ("NUMBER",    r'\d+\.\d+|\d+'),
    ("BOOL",      r'\btrue\b|\bfalse\b'),
    ("ID",        r'[A-Za-z_]\w*'),
    ("SHIFT_IN",  r'>>'),         # cin >> x
    ("SHIFT_OUT", r'<<'),         # cout << x
    ("EQ",        r'=='),
    ("NE",        r'!='),
    ("LE",        r'<='),
    ("GE",        r'>='),
    ("AND",       r'&&'),
    ("OR",        r'\|\|'),
    ("ASSIGN",    r'='),
    ("LT",        r'<'),
    ("GT",        r'>'),
    ("PLUS",      r'\+'),
    ("MINUS",     r'-'),
    ("MUL",       r'\*'),
    ("DIV",       r'/'),
    ("MOD",       r'%'),
    ("NOT",       r'!'),
    ("LPAREN",    r'\('),
    ("RPAREN",    r'\)'),
    ("LBRACE",    r'\{'),
    ("RBRACE",    r'\}'),
    ("SEMICOL",   r';'),
    ("COLON",     r':'),
    ("COMMA",     r','),
    ("WS",        r'[ \t\r\n]+'),
]

Token = Tuple[str, str, int, int]  # (type, value, line, col)

def tokenize(code: str) -> List[Token]:
    regex = "|".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC)
    tokens: List[Token] = []
    line = 1
    col = 1
    pos = 0
    for m in re.finditer(regex, code, re.DOTALL):
        typ = m.lastgroup
        val = m.group(typ)
        start = m.start()
        # update line/col based on code slice from pos to start
        chunk = code[pos:start]
        line += chunk.count("\n")
        if "\n" in chunk:
            col = len(chunk.split("\n")[-1]) + 1
        else:
            col += len(chunk)
        pos = m.end()

        if typ in ("WS", "COMMENT", "MCOMMENT"):
            continue
        if typ == "ID" and val in KEYWORDS:
            tokens.append((val.upper(), val, line, col))
        elif typ == "NUMBER":
            tokens.append(("NUMBER", val, line, col))
        elif typ == "STRING":
            tokens.append(("STRING", val[1:-1], line, col))
        elif typ == "BOOL":
            tokens.append(("BOOL", val, line, col))
        else:
            tokens.append((typ, val, line, col))
    return tokens

# -------------------------------
# Parser: AST Nodes
# -------------------------------

class Node: pass

class Program(Node):
    def __init__(self, decls: List[Node]):
        self.decls = decls

class Block(Node):
    def __init__(self, stmts: List[Node]):
        self.stmts = stmts

class VarDecl(Node):
    def __init__(self, dtype: str, name: str, init: Optional[Node], line: int, col: int):
        self.dtype, self.name, self.init, self.line, self.col = dtype, name, init, line, col

class Assign(Node):
    def __init__(self, name: str, expr: Node):
        self.name, self.expr = name, expr

class If(Node):
    def __init__(self, cond: Node, then: Node, else_branch: Optional[Node]):
        self.cond, self.then, self.else_branch = cond, then, else_branch

class While(Node):
    def __init__(self, cond: Node, body: Node):
        self.cond, self.body = cond, body

class For(Node):
    def __init__(self, init: Optional[Node], cond: Optional[Node], post: Optional[Node], body: Node):
        self.init, self.cond, self.post, self.body = init, cond, post, body

class Switch(Node):
    def __init__(self, expr: Node, cases: List[Tuple[Optional[Node], Block]]):
        self.expr, self.cases = expr, cases  # case value None for default

class Break(Node): pass

class ExprStmt(Node):
    def __init__(self, expr: Node):
        self.expr = expr

class Cout(Node):
    def __init__(self, parts: List[Node]):
        self.parts = parts  # sequence of expressions and sentinel Endl

class Cin(Node):
    def __init__(self, targets: List[str]):
        self.targets = targets

class Endl(Node): pass

# Expressions
class BinOp(Node):
    def __init__(self, op: str, left: Node, right: Node):
        self.op, self.left, self.right = op, left, right

class UnaryOp(Node):
    def __init__(self, op: str, expr: Node):
        self.op, self.expr = op, expr

class Literal(Node):
    def __init__(self, value: Any, typ: str):
        self.value, self.typ = value, typ

class Var(Node):
    def __init__(self, name: str):
        self.name = name

# -------------------------------
# Parser: Recursive Descent
# -------------------------------

class ParserError(Exception): pass

class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self, k=0) -> Optional[Token]:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def match(self, *types) -> Optional[Token]:
        tok = self.peek()
        if tok and tok[0] in types:
            self.i += 1
            return tok
        return None

    def expect(self, *types) -> Token:
        tok = self.match(*types)
        if not tok:
            got = self.peek()
            raise ParserError(f"Expected {types}, got {got}")
        return tok

    def parse(self) -> Program:
        decls = []
        while self.peek():
            decls.append(self.statement())
        return Program(decls)

    # Statements
    def statement(self) -> Node:
        tok = self.peek()
        if not tok:
            raise ParserError("Unexpected EOF")

        if tok[0] in ("INT", "FLOAT", "STRING", "BOOL"):
            return self.vardecl()

        if tok[0] == "IF":
            return self.ifstmt()

        if tok[0] == "WHILE":
            return self.whilestmt()

        if tok[0] == "FOR":
            return self.forstmt()

        if tok[0] == "SWITCH":
            return self.switchstmt()

        if tok[0] == "COUT":
            return self.coutstmt()

        if tok[0] == "CIN":
            return self.cinstmt()

        if tok[0] == "LBRACE":
            return self.block()

        if tok[0] == "BREAK":
            self.expect("BREAK")
            self.expect("SEMICOL")
            return Break()

        # assignment or expression
        # Lookahead: ID '=' ...
        if tok[0] == "ID":
            idtok = self.peek()
            if self.peek(1) and self.peek(1)[0] == "ASSIGN":
                name = self.expect("ID")[1]
                self.expect("ASSIGN")
                expr = self.expr()
                self.expect("SEMICOL")
                return Assign(name, expr)
        # expression statement
        expr = self.expr()
        self.expect("SEMICOL")
        return ExprStmt(expr)

    def block(self) -> Block:
        self.expect("LBRACE")
        stmts = []
        while self.peek() and self.peek()[0] != "RBRACE":
            stmts.append(self.statement())
        self.expect("RBRACE")
        return Block(stmts)

    def vardecl(self) -> VarDecl:
        dtype_tok = self.expect("INT", "FLOAT", "STRING", "BOOL")
        dtype = dtype_tok[1]
        name_tok = self.expect("ID")
        init = None
        if self.match("ASSIGN"):
            init = self.expr()
        sem = self.expect("SEMICOL")
        return VarDecl(dtype, name_tok[1], init, dtype_tok[2], dtype_tok[3])

    def ifstmt(self) -> If:
        self.expect("IF")
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        then = self.statement()
        else_branch = None
        if self.match("ELSE"):
            else_branch = self.statement()
        return If(cond, then, else_branch)

    def whilestmt(self) -> While:
        self.expect("WHILE")
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        body = self.statement()
        return While(cond, body)

    def forstmt(self) -> For:
        self.expect("FOR")
        self.expect("LPAREN")
        init = None
        # init can be decl, assign, or empty
        if self.peek() and self.peek()[0] != "SEMICOL":
            if self.peek()[0] in ("INT", "FLOAT", "STRING", "BOOL"):
                init = self.vardecl()
            else:
                # assignment or exprstmt until semicolon
                if self.peek()[0] == "ID" and self.peek(1) and self.peek(1)[0] == "ASSIGN":
                    name = self.expect("ID")[1]
                    self.expect("ASSIGN")
                    expr = self.expr()
                    self.expect("SEMICOL")
                    init = Assign(name, expr)
                else:
                    expr0 = self.expr()
                    self.expect("SEMICOL")
                    init = ExprStmt(expr0)
        else:
            self.expect("SEMICOL")

        # condition
        cond = None
        if self.peek() and self.peek()[0] != "SEMICOL":
            cond = self.expr()
        self.expect("SEMICOL")

        # post
        post = None
        if self.peek() and self.peek()[0] != "RPAREN":
            # support assignment or expression
            if self.peek()[0] == "ID" and self.peek(1) and self.peek(1)[0] == "ASSIGN":
                name = self.expect("ID")[1]
                self.expect("ASSIGN")
                expr = self.expr()
                post = Assign(name, expr)
            else:
                post = ExprStmt(self.expr())
        self.expect("RPAREN")
        body = self.statement()
        return For(init, cond, post, body)

    def switchstmt(self) -> Switch:
        self.expect("SWITCH")
        self.expect("LPAREN")
        expr = self.expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        cases: List[Tuple[Optional[Node], Block]] = []
        while self.peek() and self.peek()[0] != "RBRACE":
            if self.peek()[0] == "CASE":
                self.expect("CASE")
                val = self.expr()
                self.expect("COLON")
                # collect until next case/default or RBRACE
                stmts = []
                while self.peek() and self.peek()[0] not in ("CASE", "DEFAULT", "RBRACE"):
                    stmts.append(self.statement())
                cases.append((val, Block(stmts)))
            elif self.peek()[0] == "DEFAULT":
                self.expect("DEFAULT")
                self.expect("COLON")
                stmts = []
                while self.peek() and self.peek()[0] != "RBRACE":
                    stmts.append(self.statement())
                cases.append((None, Block(stmts)))
                break
            else:
                raise ParserError(f"Unexpected token in switch: {self.peek()}")
        self.expect("RBRACE")
        return Switch(expr, cases)

    def coutstmt(self) -> Cout:
        self.expect("COUT")
        parts: List[Node] = []
        # Expect << expr [<< expr ...] << endl [optional]
        if not self.match("SHIFT_OUT"):
            raise ParserError("Expected '<<' after cout")
        while True:
            if self.peek() and self.peek()[0] == "ENDL":
                self.expect("ENDL")
                parts.append(Endl())
            else:
                parts.append(self.expr())
            if self.peek() and self.peek()[0] == "SHIFT_OUT":
                self.expect("SHIFT_OUT")
                continue
            break
        self.expect("SEMICOL")
        return Cout(parts)

    def cinstmt(self) -> Cin:
        self.expect("CIN")
        targets: List[str] = []
        if not self.match("SHIFT_IN"):
            raise ParserError("Expected '>>' after cin")
        while True:
            name = self.expect("ID")[1]
            targets.append(name)
            if self.peek() and self.peek()[0] == "SHIFT_IN":
                self.expect("SHIFT_IN")
                continue
            break
        self.expect("SEMICOL")
        return Cin(targets)

    # Expressions with precedence
    def expr(self) -> Node:
        return self.logical_or()

    def logical_or(self) -> Node:
        left = self.logical_and()
        while self.match("OR"):
            op = "||"
            right = self.logical_and()
            left = BinOp(op, left, right)
        return left

    def logical_and(self) -> Node:
        left = self.equality()
        while self.match("AND"):
            op = "&&"
            right = self.equality()
            left = BinOp(op, left, right)
        return left

    def equality(self) -> Node:
        left = self.relational()
        while True:
            if self.match("EQ"):
                right = self.relational()
                left = BinOp("==", left, right)
            elif self.match("NE"):
                right = self.relational()
                left = BinOp("!=", left, right)
            else:
                break
        return left

    def relational(self) -> Node:
        left = self.additive()
        while True:
            if self.match("LT"):
                right = self.additive()
                left = BinOp("<", left, right)
            elif self.match("LE"):
                right = self.additive()
                left = BinOp("<=", left, right)
            elif self.match("GT"):
                right = self.additive()
                left = BinOp(">", left, right)
            elif self.match("GE"):
                right = self.additive()
                left = BinOp(">=", left, right)
            else:
                break
        return left

    def additive(self) -> Node:
        left = self.multiplicative()
        while True:
            if self.match("PLUS"):
                right = self.multiplicative()
                left = BinOp("+", left, right)
            elif self.match("MINUS"):
                right = self.multiplicative()
                left = BinOp("-", left, right)
            else:
                break
        return left

    def multiplicative(self) -> Node:
        left = self.unary()
        while True:
            if self.match("MUL"):
                right = self.unary()
                left = BinOp("*", left, right)
            elif self.match("DIV"):
                right = self.unary()
                left = BinOp("/", left, right)
            elif self.match("MOD"):
                right = self.unary()
                left = BinOp("%", left, right)
            else:
                break
        return left

    def unary(self) -> Node:
        if self.match("NOT"):
            return UnaryOp("!", self.unary())
        if self.match("PLUS"):
            return UnaryOp("+", self.unary())
        if self.match("MINUS"):
            return UnaryOp("-", self.unary())
        return self.primary()

    def primary(self) -> Node:
        tok = self.peek()
        if not tok:
            raise ParserError("Unexpected EOF in expression")
        if tok[0] == "LPAREN":
            self.expect("LPAREN")
            e = self.expr()
            self.expect("RPAREN")
            return e
        if tok[0] == "NUMBER":
            val = self.expect("NUMBER")[1]
            if "." in val:
                return Literal(float(val), "float")
            return Literal(int(val), "int")
        if tok[0] == "STRING":
            val = self.expect("STRING")[1]
            return Literal(val, "string")
        if tok[0] == "BOOL":
            val = self.expect("BOOL")[1]
            return Literal(True if val == "true" else False, "bool")
        if tok[0] == "ID":
            name = self.expect("ID")[1]
            return Var(name)
        raise ParserError(f"Unexpected token in primary: {tok}")

# -------------------------------
# Semantic context
# -------------------------------

class Context:
    def __init__(self):
        self.types: Dict[str, str] = {}  # variable name -> dtype

# -------------------------------
# Code Generation: Python
# -------------------------------

class CodeGen:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.out: List[str] = []
        self.indent = 0
        self.break_label_stack: List[str] = []  # used for switch emulation if needed
        self.temp_counter = 0

    def emit(self, line: str = ""):
        self.out.append(("    " * self.indent) + line)

    def fresh(self, prefix="_t"):
        self.temp_counter += 1
        return f"{prefix}{self.temp_counter}"

    def compile(self, node: Program) -> str:
        self.emit("import sys")
        self.emit("")
        self.emit("def _to_bool(v):")
        self.indent += 1
        self.emit("return bool(v)")
        self.indent -= 1
        self.emit("")
        for decl in node.decls:
            self.gen_stmt(decl)
        self.emit("")
        return "\n".join(self.out)

    def gen_block(self, block: Block):
        for s in block.stmts:
            self.gen_stmt(s)

    def gen_stmt(self, s: Node):
        if isinstance(s, VarDecl):
            # declare and optionally init
            if s.init:
                expr = self.gen_expr(s.init)
                self.emit(f"{s.name} = {expr}")
            else:
                self.emit(f"{s.name} = None")
            self.ctx.types[s.name] = s.dtype
            return

        if isinstance(s, Assign):
            expr = self.gen_expr(s.expr)
            self.emit(f"{s.name} = {expr}")
            return

        if isinstance(s, If):
            cond = self.gen_expr(s.cond)
            self.emit(f"if {cond}:")
            self.indent += 1
            self.gen_stmt(s.then)
            self.indent -= 1
            if s.else_branch:
                self.emit("else:")
                self.indent += 1
                self.gen_stmt(s.else_branch)
                self.indent -= 1
            return

        if isinstance(s, While):
            cond = self.gen_expr(s.cond)
            self.emit(f"while {cond}:")
            self.indent += 1
            self.gen_stmt(s.body)
            self.indent -= 1
            return

        if isinstance(s, For):
            # transform for(init; cond; post) body
            if s.init:
                self.gen_stmt(s.init)
            cond = self.gen_expr(s.cond) if s.cond else "True"
            self.emit(f"while {cond}:")
            self.indent += 1
            if isinstance(s.body, Block):
                self.gen_block(s.body)
            else:
                self.gen_stmt(s.body)
            if s.post:
                self.gen_stmt(s.post)

            self.indent -= 1
            return

        if isinstance(s, Switch):
            tmp = self.fresh("_switch_")
            expr = self.gen_expr(s.expr)
            self.emit(f"{tmp} = {expr}")
            first = True
            for case_val, block in s.cases:
                if case_val is None:
                    self.emit("else:")
                else:
                    cond = f"{tmp} == {self.gen_expr(case_val)}"
                    self.emit(("if " if first else "elif ") + cond + ":")
                self.indent += 1
                # emulate 'break' by raising and catching a sentinel?
                # Simpler: stop at Break by wrapping into a function with return. We'll inline: check for Break and use a flag.
                flag = self.fresh("_brk_")
                self.emit(f"{flag} = False")
                for st in block.stmts:
                    if isinstance(st, Break):
                        self.emit(f"{flag} = True")
                        self.emit("pass")
                        # stop emitting subsequent case statements
                        break
                    else:
                        self.gen_stmt(st)
                self.emit(f"if {flag}:")
                self.indent += 1
                self.emit("pass")
                self.indent -= 1
                self.indent -= 1
                first = False
            return

        if isinstance(s, Break):
            # handled inside switch codegen
            self.emit("# break")
            return

        if isinstance(s, Block):
            self.emit("")  # cosmetic
            self.indent += 1
            self.gen_block(s)
            self.indent -= 1
            return

        if isinstance(s, Cout):
            # collect parts; write without newline unless Endl encountered
            buffer = []
            newline = False
            for p in s.parts:
                if isinstance(p, Endl):
                    newline = True
                else:
                    buffer.append(self.gen_expr(p))
            if newline:
                if buffer:
                    self.emit(f"sys.stdout.write(str(" + ") + str(".join(buffer) + ") + '\\n')")
                else:
                    self.emit("sys.stdout.write('\\n')")
            else:
                if buffer:
                    self.emit(f"sys.stdout.write(str(" + ") + str(".join(buffer) + "))")
            return

        if isinstance(s, Cin):
            # read inputs for each target and cast by declared type
            for name in s.targets:
                dtype = self.ctx.types.get(name, None)
                cast = "str"
                if dtype == "int":
                    cast = "int"
                elif dtype == "float":
                    cast = "float"
                elif dtype == "bool":
                    # read '0/1/true/false'
                    tmp = self.fresh("_inp_")
                    self.emit(f"{tmp} = input().strip()")
                    self.emit(f"{name} = ({tmp}.lower() in ['1','true','t','yes'])")
                    continue
                self.emit(f"{name} = {cast}(input())")
            return

        if isinstance(s, ExprStmt):
            self.emit(self.gen_expr(s.expr))
            return

        raise RuntimeError(f"Unhandled stmt: {type(s)}")

    def gen_expr(self, e: Node) -> str:
        if isinstance(e, Literal):
            if e.typ == "string":
                return repr(e.value)
            if e.typ == "bool":
                return "True" if e.value else "False"
            return str(e.value)
        if isinstance(e, Var):
            return e.name
        if isinstance(e, UnaryOp):
            if e.op == "!":
                return f"(not {self.gen_expr(e.expr)})"
            if e.op == "+":
                return f"(+{self.gen_expr(e.expr)})"
            if e.op == "-":
                return f"(-{self.gen_expr(e.expr)})"
        if isinstance(e, BinOp):
            opmap = {
                "&&": "and",
                "||": "or",
                "==": "==",
                "!=": "!=",
                "<": "<",
                "<=": "<=",
                ">": ">",
                ">=": ">=",
                "+": "+",
                "-": "-",
                "*": "*",
                "/": "/",
                "%": "%",
            }
            op = opmap.get(e.op, e.op)
            return f"({self.gen_expr(e.left)} {op} {self.gen_expr(e.right)})"
        raise RuntimeError(f"Unhandled expr: {type(e)}")

# -------------------------------
# Driver
# -------------------------------

def compile_source(src: str) -> str:
    tokens = tokenize(src)
    parser = Parser(tokens)
    ast = parser.parse()
    ctx = Context()
    gen = CodeGen(ctx)
    py = gen.compile(ast)
    return py

def main():
    if len(sys.argv) < 2:
        print("Usage: python minicpp_compiler.py <source.cpp> [--run]")
        sys.exit(1)
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    pycode = compile_source(src)
    if "--run" in sys.argv[2:]:
        # Execute compiled Python code in a fresh globals
        g = {}
        exec(pycode, g, g)
    else:
        print(pycode)

if __name__ == "__main__":
    main()
