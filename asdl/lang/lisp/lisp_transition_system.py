# coding=utf-8
from asdl.transition_system import TransitionSystem, GenTokenAction

try:
    from cStringIO import StringIO
except:
    from io import StringIO

from collections import Iterable
from asdl.asdl import *
from asdl.asdl_ast import RealizedField, AbstractSyntaxTree
import ast

from common.registerable import Registrable


def lisp_node_to_ast(grammar, lisp_tokens, start_idx):
    node_name = lisp_tokens[start_idx]
    i = start_idx
    if node_name in ['_eq','select','filter','_parts','_time','_inspect','between','_and','_or','renew','cancel']:
        # it's a predicate
        prod = grammar.get_prod_by_ctr_name('apply')
        pred_field = RealizedField(prod['predicate'], value=node_name)

        arg_ast_nodes = []
        while True:
            i += 1
            lisp_token = lisp_tokens[i]
            if lisp_token == "(":
                arg_ast_node, end_idx = lisp_expr_to_ast_helper(grammar, lisp_tokens,i)
            elif lisp_token == ")":
                i +=1
                break
            else:
                prod1 = grammar.get_prod_by_ctr_name('Literal')
                arg_ast_node ,end_idx= AbstractSyntaxTree(prod1,
                                              [RealizedField(prod1['literal'], value=lisp_tokens[i])]),i


            arg_ast_nodes.append(arg_ast_node)

            i = end_idx
            if i >= len(lisp_tokens): break
            if lisp_tokens[i] == ')':
                i += 1
                break


        arg_field = RealizedField(prod['arguments'], arg_ast_nodes)
        ast_node = AbstractSyntaxTree(prod, [pred_field, arg_field])
    elif node_name.endswith('id0') or node_name.endswith('id1') or node_name.endswith('id2') \
            or node_name in ['periodid0', 'periodid1']:
        # it's a literal
        prod = grammar.get_prod_by_ctr_name('Literal')

        ast_node = AbstractSyntaxTree(prod,
                                      [RealizedField(prod['literal'], value=node_name)])


        i += 1
    else:
        raise NotImplementedError

    return ast_node, i


def lisp_expr_to_ast_helper(grammar, lisp_tokens, start_idx=0):
    i = start_idx
    if lisp_tokens[i] == '(':
        i += 1

    parsed_nodes = []
    while True:
        if lisp_tokens[i] == '(':
            ast_node, end_idx = lisp_expr_to_ast_helper(grammar, lisp_tokens, i)
            parsed_nodes.append(ast_node)
            i = end_idx
        else:
            ast_node, end_idx = lisp_node_to_ast(grammar, lisp_tokens, i)
            parsed_nodes.append(ast_node)
            i = end_idx

        if i >= len(lisp_tokens): break
        if lisp_tokens[i] == ')':
            # i += 1
            break

        if lisp_tokens[i] == ' ':
            # and
            i += 1

    assert parsed_nodes
    if len(parsed_nodes) > 1:
        prod = grammar.get_prod_by_ctr_name('And')
        return_node = AbstractSyntaxTree(prod, [RealizedField(prod['arguments'], parsed_nodes)])
    else:
        return_node = parsed_nodes[0]
    return return_node, i


def lisp_expr_to_ast(grammar, lisp_expr):
    lisp_tokens = lisp_expr.strip().split(' ')
    return lisp_expr_to_ast_helper(grammar, lisp_tokens, start_idx=0)[0]

def ast_to_lisp_expr(asdl_ast):
    value = ast_to_lisp_expr_helper(asdl_ast)
    value = " ".join(value.split())
    return value

def ast_to_lisp_expr_helper(asdl_ast):
    sb = StringIO()
    constructor_name = asdl_ast.production.constructor.name
    if constructor_name == 'apply':
        predicate = asdl_ast['predicate'].value
        sb.write(' ( ')
        sb.write(predicate)
        sb.write(' ')
        for i, arg in enumerate(asdl_ast['arguments'].value):
            arg_val = arg.fields[0].value
            sb.write(' ')
            if isinstance(arg_val,str):
                sb.write(arg_val)
            else:
                for ast in arg_val:
                    sb.write(ast_to_lisp_expr_helper(ast))

        sb.write(' ) ')
    return sb.getvalue()


def is_equal_ast(this_ast, other_ast):
    if not isinstance(other_ast, this_ast.__class__):
        return False

    if this_ast == other_ast:
        return True

    if isinstance(this_ast, AbstractSyntaxTree):
        if this_ast.production != other_ast.production:
            return False

        if len(this_ast.fields) != len(other_ast.fields):
            return False

        for i in range(len(this_ast.fields)):
            if this_ast.production.constructor.name in ('And', 'Or') and this_ast.fields[i].name == 'arguments':
                this_field_val = sorted(this_ast.fields[i].value, key=lambda x: x.to_string())
                other_field_val = sorted(other_ast.fields[i].value, key=lambda x: x.to_string())
            else:
                this_field_val = this_ast.fields[i].value
                other_field_val = other_ast.fields[i].value

            if not is_equal_ast(this_field_val, other_field_val): return False
    elif isinstance(this_ast, list):
        if len(this_ast) != len(other_ast): return False

        for i in range(len(this_ast)):
            if not is_equal_ast(this_ast[i], other_ast[i]): return False
    else:
        return this_ast == other_ast

    return True


@Registrable.register('lisp')
class LispTransitionSystem(TransitionSystem):
    def compare_ast(self, hyp_ast, ref_ast):
        return is_equal_ast(hyp_ast, ref_ast)

    def ast_to_surface_code(self, asdl_ast):
        return ast_to_lisp_expr(asdl_ast)

    def surface_code_to_ast(self, code):
        return lisp_expr_to_ast(self.grammar, code)

    def hyp_correct(self, hyp, example):
        return is_equal_ast(hyp.tree, example.tgt_ast)

    def tokenize_code(self, code, mode):
        return code.split(' ')

    def get_primitive_field_actions(self, realized_field):
        assert realized_field.cardinality == 'single'
        if realized_field.value is not None:
            return [GenTokenAction(realized_field.value)]
        else:
            return []

    def is_valid_hypothesis(self, hyp, **kwargs):
        return True


if __name__ == '__main__':
    pass
