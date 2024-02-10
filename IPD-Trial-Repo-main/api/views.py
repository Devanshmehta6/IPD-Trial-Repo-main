import os
from django.http import HttpResponse
from django.shortcuts import redirect, render
import requests,json
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
import tokenize
import ast
import svgwrite

@csrf_exempt
def index(request):
    return render(request,'index.html')

@csrf_exempt
def format_code(request):
    if request.method == 'POST':
        code = request.POST.get('code', '')
        # print(code)
        formatted_output = code.replace('\n','\\n').replace('"', "'")
        # print('hello',formatted_output)
        request.session['code'] = code
        request.session['my_variable'] = formatted_output
        return createASTfromAPI(request)

@csrf_exempt
def createASTfromAPI(request):
    my_variable = request.session.get('my_variable')
    # print(f"import ast \ncode = '{my_variable}' \nparsed_ast = ast.parse(code) \nast.dump(parsed_ast)")
    r = requests.post('https://online-code-compiler.p.rapidapi.com/v1/' , 
            headers = {
                'X-RapidAPI-Key' : 'bf3d23b953msh22d99c684dcfdebp1ad975jsn742acbd71271',
                'X-RapidAPI-Host' : 'online-code-compiler.p.rapidapi.com',
                'Content-Type' : 'application/json'
            },
            json = {
                    "language": "python3",
                    "version": "latest",
                    "code": f"import ast \ncode = '''{my_variable}''' \nparsed_ast = ast.parse(code) \nprint(ast.dump(parsed_ast))",
                    "input": None
            },
            )
    parsed_output = json.loads(r.text)
    actual_output = parsed_output["output"]
    request.session['output'] = actual_output

    code_to_parse = request.session.get('code')
    ast_tree = ast.parse(code_to_parse)
    ast_dict = ast_to_dict(ast_tree)

    keys_to_extract = ['node_type','arg', 'name', 'id', 'value']

    result = process_ast(code_to_parse)
    json_result = json.dumps(result)
    print("Json ---------- ",json_result)

    return HttpResponse(json_result)

@csrf_exempt
def ast_to_dict(node):
    if isinstance(node, ast.AST):
        return {
            'node_type': type(node).__name__,
            'fields': {field: ast_to_dict(value) for field, value in ast.iter_fields(node)}
        }
    elif isinstance(node, list):
        return [ast_to_dict(item) for item in node]
    else:
        return node

@csrf_exempt
def traverse_dict(node, result_list, current_path=None):
    if current_path is None:
        current_path = []

    if isinstance(node, dict):
        for key, value in node.items():
            new_path = current_path + [key]
            traverse_dict(value, result_list, new_path)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            new_path = current_path + [index]
            traverse_dict(item, result_list, new_path)
    else:
        result_list.append((current_path, node))

    print('RESULT ----------- ',result_list)

# @csrf_exempt
# def extract_only_necessary_values(data, keys_to_extract, result_list, prev_key=None):
#     if isinstance(data, dict):
#         for key, value in data.items():
#             if key in keys_to_extract and not isinstance(value, dict):
#                 result_list.append({key: value})
#                 prev_key = key
#             extract_only_necessary_values(value, keys_to_extract, result_list, prev_key=key)
#     elif isinstance(data, list):
#         for item in data:
#             extract_only_necessary_values(item, keys_to_extract, result_list, prev_key)

@csrf_exempt
# lower level things like bin operations, or simple code like variables
def extract_value(node):
    if isinstance(node, ast.AST):
        return {key: extract_value(value) for key, value in ast.iter_fields(node)}
    elif isinstance(node, list):
        return [extract_value(item) for item in node]
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Expr):
        return extract_value(node.value)
    elif isinstance(node, ast.BinOp):
        left = extract_value(node.left)
        right = extract_value(node.right)
        return {"left": left, "right": right}
    else:
        return str(node)

@csrf_exempt
#higher level concepts like loops, functions, class
def extract_info(node):
    info = {}
    if isinstance(node, ast.FunctionDef):
        info["function"] = node.name
        info["args"] = [arg.arg for arg in node.args.args]
        info["body"] = [extract_info(stmt) for stmt in node.body]

    elif isinstance(node, ast.For):
        info["for_loop"] = {
            "variable": node.target.id,
            "iterable": extract_value(node.iter),
            "body": [extract_info(stmt) for stmt in node.body]
        }
    
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                info["variable"] = target.id
                info["value"] = extract_value(node.value)
    return info

def process_ast(source_code):
    tree = ast.parse(source_code)
    return [extract_info(node) for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.FunctionDef, ast.For, ast.If))]


