import re

from _ast import *
from ast import parse as ast_parse, walk as ast_walk


class AstAnalyser:
    root = None
    
    def __init__(self, file):
        self.file = file
        with open(file, mode='r', encoding='utf-8-sig') as f:
            text = f.read()
        self.root = ast_parse(text)
    
    def get_lino_indent_dict(self):
        """
        refer: {lkdemo}/ast_demo.py
        
        NOTICE: 使用 regex 计算行缩进, 不要用 node.col_offset.
            为什么: 假设存在以下代码:
                1 | def func():
                2 |     if a == 1:
                3 |         pass
            对第 2 行 `if a == 1:`, 使用正则计算结果是 indent = 4, 而 node.col_offset
            的值是 7. 原因在于, node.col_offset 计算的是变量 `a` 的列位置, 而非该行的缩进
            位置.
        
        IN: self.file
            self.root
        OT: {lino: indent}
                lino: int. count from 1 but not consecutive. the linos are
                    already sorted by ascending order.
                indent: int. the column offset, assert all of them would be
                    integral multiple of 4, e.g. 0, 4, 8, 12, ...
        """
        from lk_utils.read_and_write_basic import read_file_by_line
        lino_indent = {}
        
        code_lines = read_file_by_line(self.file)
        reg = re.compile(r'^ *')
        
        for node in ast_walk(self.root):
            if not (hasattr(node, 'lineno') and hasattr(node, 'col_offset')):
                continue
            if node.lineno in lino_indent:
                continue
            if node.col_offset == -1:
                # 说明这个节点是 docstring
                continue
            lino_indent[node.lineno] = len(
                reg.findall(
                    code_lines[node.lineno - 1]
                )[0]
            )
        
        # sort linos
        sorted_lino_indent = {
            k: lino_indent[k]
            for k in sorted(lino_indent.keys())
        }
        
        return sorted_lino_indent
    
    def main(self):
        """
        IN: self.root
        OT: dict. {
                lino: [(node_type, node_value), (...), ...], ...
            }
                lino: int. count from 1 but not consecutive. the linos are
                    already sorted by ascending order.
                node_type: str. refer to _ast class types, e.g. "<class '_ast
                    .Import'>", "<class '_ast.FunctionDef'>", ...
                node_value: str/dict. e.g. 'os.path.abspath', {'os': 'os'}, ...
        """
        out = {}
        
        for node in ast_walk(self.root):
            if not hasattr(node, 'lineno'):
                continue
            if node.col_offset == -1:
                # 说明这个节点是 docstring
                continue
            x = out.setdefault(node.lineno, [])
            x.append((str(type(node)), self.eval_node(node)))
        
        # sort linos
        sorted_out = {
            k: out[k]
            for k in sorted(out.keys())
        }
        
        return sorted_out
    
    def eval_node(self, node):
        result = None
        
        while result is None:
            # lk.loga(type(node))
            # ------------------------------------------------ output result
            if isinstance(node, arg):
                """
                _fields = ('arg', 'annotation')
                    arg        -> str
                    annotation -> None / _ast.Name

                e.g. 1:
                    source_code = `def main(x, y):`
                    -> node.arg = 'x', node.annotation = None
                       node.arg = 'y', node.annotation = None

                e.g. 2:
                    source_code = `def main(self, x: dict):`
                    -> node.arg = 'self', node.annotation = None
                       node.arg = 'x', node.annotation = eval(node.annotation)
                       = 'dict'
                """
                # print('[arg fields]', node.arg, node.annotation)
                result = node.arg
                # | k, v = node.arg, node.annotation
                # | if v is not None:
                # |     v = self.eval_node(v)
                # | result = {k: v}
            elif isinstance(node, ClassDef):
                result = node.name
            elif isinstance(node, FunctionDef):
                result = node.name
            elif isinstance(node, Name):
                result = node.id
            elif isinstance(node, Str):
                result = node.s
            # ------------------------------------------------ compound obj
            elif isinstance(node, Assign):
                result = {}
                a, b = node.targets, node.value
                k = self.eval_node(b)
                for i in a:
                    v = self.eval_node(i)
                    result[v] = k
            elif isinstance(node, Attribute):
                """
                _fields = ('value', 'attr', 'ctx')
                    value -> _ast.Name / _ast.Attribute
                    attr  -> str
                    ctx   -> _ast.Load
                """
                # print('[Attribute fields]', node.value, node.attr, node.ctx)
                v = node.attr
                k = self.eval_node(node.value)
                result = k + '.' + v
                # | result = node.attr
            elif isinstance(node, Import):
                result = {}  # {module: import_name_or_asname}
                for imp in node.names:
                    if imp.asname is None:
                        result[imp.name] = imp.name
                    else:
                        result[imp.name] = imp.asname
            elif isinstance(node, ImportFrom):
                result = {}  # {module: import_name_or_asname}
                module = node.module
                for imp in node.names:
                    if imp.asname is None:
                        result[module + '.' + imp.name] = imp.name
                    else:
                        result[module + '.' + imp.name] = imp.asname
            # ------------------------------------------------ take reloop
            elif isinstance(node, Call):
                """
                _fields = ('func', 'args', 'keywords')
                    func     -> _ast.Attribute / _ast.Name
                    args     -> [] (empty list) / [_ast.Call]
                    keywords -> [] (empty list)
                """
                # print('[Call fields]', node.func, node.args, node.keywords)
                node = node.func
            elif isinstance(node, Expr):
                node = node.value
            elif isinstance(node, Subscript):
                node = node.value
            else:
                # noinspection PyProtectedMember
                result = str(node._fields)
        
        return result


# ------------------------------------------------

def dump_asthelper_result():
    """
    将 AstHelper 解析结果输出到 json 文件.
    
    IN: temp/in.py
            suggest copied from testflight/test_app_launcher.py
    OT: temp/out.json
            backup this file to res/sample/ast_helper_result/{module}.json
    """
    from lk_utils.read_and_write_basic import write_json
    helper = AstAnalyser('../temp/in.py')
    res = helper.main()
    write_json(res, '../temp/out.json')


def dump_lino_indent_result():
    """
    将 AstHelper#get_lino_indent_dict() 的结果输出到 json 文件.
    IN: temp/in.py
    OT: temp/out.json
    """
    from lk_utils.read_and_write_basic import write_json
    helper = AstAnalyser('../temp/in.py')
    res = helper.get_lino_indent_dict()
    write_json(res, '../temp/out.json')


def dump_by_filter_schema(file, schema=1):
    """
    将 AstHelper 解析结果根据对象类型 (库, 变量, 方法和类对象) 分类后, 输出或打印出来.

    IN: file: str. 要解析的 py 文件, 传入绝对路径或相对路径. e.g. './dump_asthelper
            _result.py'
    OT: schema 1:
            print out to the console
        schema 2:
            dump collector to './ast_helper_result.json'
    """
    helper = AstAnalyser(file)
    res = helper.main()
    
    lib_dict = {}
    var_dict = {}
    fun_dict = {}
    cls_dict = {}
    
    dict_filter = {
        "<class '_ast.Import'>"     : lib_dict,
        "<class '_ast.ImportFrom'>" : lib_dict,
        "<class '_ast.Assign'>"     : var_dict,
        "<class '_ast.FunctionDef'>": fun_dict,
        "<class '_ast.ClassDef'>"   : cls_dict,
    }
    
    for lino, data in res.items():
        for i in data:
            type_, value = i
            if type_ in dict_filter:
                d = dict_filter.get(type_)
                if isinstance(value, str):
                    # schema 1: use list to store vars
                    node = d.setdefault(value, [])
                    node.append(lino)
                    # schema 2: override if the old key-value exists
                    # d[value] = lino
                else:
                    for k in value.keys():
                        # schema 1: use list to store vars
                        node = d.setdefault(k, [])
                        node.append(lino)
                        # schema 2: override if the old key-value exists
                        # d[k] = lino
    
    if schema == 1:
        # schema 1: print out to the console
        print('库', lib_dict)
        print('类', cls_dict)
        print('函数', fun_dict)
        print('变量', var_dict)
    else:
        # schema 2: dump to local file
        from json import dumps
        
        out = {
            "lib_dict": lib_dict,
            "var_dict": var_dict,
            "fun_dict": fun_dict,
            "cls_dict": cls_dict,
        }
        
        with open('ast_helper_result.json', encoding='utf-8', mode='w') as f:
            f.write(dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    dump_asthelper_result()
    # dump_lino_indent_result()
    
    # 在这里传入要解析的 py 文件的路径.
    # dump_by_filter_schema('dump_asthelper_result.py')
