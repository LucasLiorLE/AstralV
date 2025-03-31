from pathlib import Path
import json 

MEMBER_INFO_PATH = Path(__file__).parents[2] / "storage" / "member_info.json"

def load_member_info():
    with open(MEMBER_INFO_PATH, 'r') as f:
        return json.load(f)

def save_member_info(data):
    with open(MEMBER_INFO_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def is_valid_value(value: int, min_val: int, max_val: int) -> bool:
    if value is None:
        return True
    try:
        return min_val <= value <= max_val
    except TypeError:
        return False

import re, math, io
import matplotlib.pyplot as plt
import numpy as np

from math import gamma
from scipy.integrate import quad

def symbolic_derivative(expr: str, order: int = 1) -> callable:
	"""Calculate the derivative of an expression numerically using central difference"""
	def func(x):
		context = {
			'x': x, 
			'np': np,
			'sin': np.sin,
			'cos': np.cos,
			'tan': np.tan,
			'dsin': lambda x: np.sin(x * np.pi/180),
			'dcos': lambda x: np.cos(x * np.pi/180),
			'dtan': lambda x: np.tan(x * np.pi/180),
			'rsin': np.sin,
			'rcos': np.cos,
			'rtan': np.tan,
			'asin': np.arcsin,
			'acos': np.arccos,
			'atan': np.arctan,
			'arcsin': np.arcsin,
			'arccos': np.arccos,
			'arctan': np.arctan,
			'sqrt': np.sqrt,
			'abs': np.abs,
			'log': np.log,
			'e': np.e,
			'pi': np.pi
		}
		expr_np = expr.replace('^', '**')
		return eval(expr_np, {"__builtins__": {}}, context)
	
	def derivative(x, h=1e-7):
		if order == 1:
			return (func(x + h) - func(x - h)) / (2 * h)
		elif order == 2:
			return (func(x + h) - 2 * func(x) + func(x - h)) / (h * h)
		else:
			if order < 1:
				raise ValueError("Order must be positive")
			def deriv(n, x):
				if n == 0:
					return func(x)
				elif n == 1:
					return (func(x + h) - func(x - h)) / (2 * h)
				else:
					prev = deriv(n-1, x)
					return (deriv(n-1, x + h) - prev) / h
			return deriv(order, x)
	
	return derivative

def definite_integral(expr: str, lower: float, upper: float) -> float:
	"""Calculate the definite integral of an expression"""
	def func(x):
		context = {'x': x, 'np': np}
		expr_np = expr.replace('^', '**')
		return eval(expr_np, context)
	
	result, error = quad(func, lower, upper)
	return result

def is_safe_expression(expr: str) -> bool:
	"""
	Check if expression is safe to evaluate.
	Returns False if expression contains dangerous keywords or patterns.
	"""
	dangerous_patterns = [
		'import',
		'__',
		'eval',
		'exec',
		'open',
		'os.',
		'sys.',
		'subprocess',
		'lambda',
		'getattr',
		'globals',
		'locals'
	]
	expr = expr.lower()
	return not any(pattern in expr for pattern in dangerous_patterns)

def check_for_abs(expr: str) -> str:
	"""
	Check for absolute value notation (|x|) and replace with abs(x)
	"""
	pattern = r'\|(.*?)\|'
	while '|' in expr:
		match = re.search(pattern, expr) 
		if not match:
			break
		content = match.group(1)
		expr = expr.replace(f"|{content}|", f"abs({content})")
	return expr

def factorial(n: float) -> float:
	"""
	Calculate factorial of n, supports decimal numbers using gamma function.
	For integers, uses regular factorial.
	For decimals, uses gamma(n + 1).
	"""
	if isinstance(n, int) or n.is_integer():
		if n < 0:
			raise ValueError("Factorial undefined for negative numbers")
		n = int(n)
		if n == 0:
			return 1
		return n * factorial(n - 1)
	else:
		if n < 0:
			raise ValueError("Factorial undefined for negative numbers")
		return gamma(n + 1)

def process_factorial(expr: str) -> str:
	"""Process factorial expressions like 5! or 5.5! or 5!! or 5!!!"""
	def calc_multi_factorial(match):
		num_expr = match.group(1)
		bangs = len(match.group(2))
		try:
			result = float(eval(num_expr))
			for _ in range(bangs):
				result = factorial(result)
			return str(result)
		except Exception as e:
			raise ValueError(f"Error evaluating factorial expression: {e}")
	
	pattern = r'([^!]+?)(!+)'
	return re.sub(pattern, calc_multi_factorial, expr)

def process_radicals(expr: str) -> str:
    """
    Process radical expressions of the form n&x (nth root of x)
    or &x (square root of x).
    
    Examples:
        "3&27" -> "pow(27, 1/3)"      # cube root of 27
        "&9" -> "pow(9, 1/2)"         # square root of 9
        "2*&9" -> "2*pow(9, 1/2)"     # 2 times square root of 9
        "&abs(x)" -> "pow(abs(x), 1/2)" # square root of absolute value
    """
    while '&' in expr:
        match = re.search(r'((\d+)?&)([a-zA-Z0-9_()\[\]]+)', expr)
        if not match:
            break
            
        full_match = match.group(0)
        root_degree = match.group(2) or '2'
        operand = match.group(3)
        
        if operand.startswith('('):
            paren_count = 1
            for i, c in enumerate(operand[1:], 1):
                if c == '(': paren_count += 1
                elif c == ')': paren_count -= 1
                if paren_count == 0:
                    operand = operand[1:i]
                    break
        
        replacement = f"pow({operand}, 1/{root_degree})"
        expr = expr.replace(full_match, replacement)
    
    return expr

def resolve_vars(expr: str, variables: dict) -> str:
	"""
	Replace variable references in an expression with their actual values.
	
	Args:
		expr (str): Expression containing variable references in the form @<var>
		variables (dict): Dictionary mapping variable names to their values
	
	Example:
		expr = "2 * @x + @y"
		variables = {"x": 5, "y": 3}
		Result: "2 * 5 + 3"
		
	Raises:
		ValueError: If a referenced variable is not found in the variables dict
	"""
	if not is_safe_expression(expr):
		raise ValueError("Expression contains unsafe operations")
	expr = check_for_abs(expr)
	expr = process_factorial(expr)
	expr = process_radicals(expr)
	
	def repl(match):
		var_name = match.group(1)
		if var_name in variables:
			return str(variables[var_name])
		else:
			raise ValueError(f"Variable '{var_name}' not defined")
	
	return re.sub(r'@([A-Za-z0-9_]+)', repl, expr)

def deg_to_rad(x):
	return x * math.pi / 180

def dsin(x): return math.sin(deg_to_rad(x))
def dcos(x): return math.cos(deg_to_rad(x))
def dtan(x):
	if abs(x % 180) == 90:
		raise ValueError("tan() is undefined at 90°, 270°, etc.")
	return math.tan(deg_to_rad(x))

def rsin(x): return math.sin(x)
def rcos(x): return math.cos(x)
def rtan(x):
	if abs(x % (math.pi/2)) == math.pi/2:
		raise ValueError("tan() is undefined at π/2, 3π/2, etc.")
	return math.tan(x)

def process_assignment(assign_expr: str, variables: dict) -> int:
	"""
	Process a variable assignment expression and store the result.
	
	Format: (expression)#variable_name
	The expression is evaluated first (resolving any variable references),
	then the result is stored in the specified variable.
	
	Args:
		assign_expr (str): The full assignment expression (e.g. "(1+2)#x")
		variables (dict): Dictionary to store variable assignments
		
	Example:
		"(1+@x)#y" with variables={"x": 5} will store 6 in variables["y"]
	
	Returns:
		int: The evaluated value that was assigned
		
	Raises:
		ValueError: If expression format is invalid or evaluation fails
	"""
	if not is_safe_expression(assign_expr):
		raise ValueError("Expression contains unsafe operations")
	if '#' not in assign_expr:
		raise ValueError("Assignment expression must contain '#'")
	
	expr_part, var_part = assign_expr.split('#', 1)
	var_name = var_part.strip()
	
	expr_part = expr_part.strip()
	if expr_part.startswith('(') and expr_part.endswith(')'):
		expr_part = expr_part[1:-1]
	
	resolved_expr = resolve_vars(expr_part, variables)
	
	math_context = {
		'sin': rsin,
		'cos': rcos,
		'tan': rtan,
		'dsin': dsin,
		'dcos': dcos,
		'dtan': dtan,
		'rsin': rsin,
		'rcos': rcos,
		'rtan': rtan,
		'asin': math.asin,
		'acos': math.acos,
		'atan': math.atan,
		'arcsin': math.asin,
		'arccos': math.acos,
		'arctan': math.atan,
		'sqrt': math.sqrt,
		'log': math.log,
		'pi': math.pi,
		'e': math.e,
		'abs': abs,
		'pow': pow
	}
	
	try:
		value = eval(resolved_expr, {"__builtins__": {}}, math_context)
	except Exception as e:
		raise ValueError(f"Error evaluating expression '{resolved_expr}': {e}")
	
	variables[var_name] = value
	return value

def process_summation(sum_expr: str, variables: dict) -> int:
	"""
	Process a summation expression starting with '$' of the form:
	   $lower_bound,upper_bound,#target_variable,(expression)
	   
	The lower and upper bounds are evaluated (they may call variables).
	The target variable (after '#') is used in the expression:
	every occurrence of @<target_variable> is replaced by the current loop value.
	
	The summation iterates from the lower bound to the upper bound (inclusive),
	evaluates the expression for each iteration, sums the results,
	then stores the final sum in the target variable.
	"""
	if not sum_expr.startswith('$'):
		raise ValueError("Summation expression must start with '$'")
	
	parts = sum_expr[1:].split(',')
	if len(parts) != 4:
		raise ValueError("Summation expression must have 4 parts separated by commas")
	
	lower_str, upper_str, target_str, expr_str = [p.strip() for p in parts]
	
	if not target_str.startswith('#'):
		raise ValueError("Target variable part must start with '#'")
	target_var = target_str[1:]
	
	lower_resolved = resolve_vars(lower_str, variables)
	upper_resolved = resolve_vars(upper_str, variables)
	
	try:
		lower_bound = int(eval(lower_resolved))
		upper_bound = int(eval(upper_resolved))
	except Exception as e:
		raise ValueError(f"Error evaluating bounds: {e}")
	
	expr_str = expr_str.strip()
	if expr_str.startswith('(') and expr_str.endswith(')'):
		expr_str = expr_str[1:-1]
	
	total = 0
	for i in range(lower_bound, upper_bound + 1):
		iteration_expr = expr_str.replace(f"@{target_var}", str(i))
		iteration_expr = resolve_vars(iteration_expr, variables)
		try:
			step_value = eval(iteration_expr)
		except Exception as e:
			raise ValueError(f"Error evaluating iteration expression '{iteration_expr}': {e}")
		total += step_value
	
	variables[target_var] = total
	return total

def process_productation(prod_expr: str, variables: dict) -> int:
	"""
	Process a productation expression starting with '?' of the form:
	   ?lower_bound,upper_bound,#target_variable,(expression)
	   
	Similar to summation but multiplies the results instead of adding them.
	The lower and upper bounds are evaluated (they may call variables).
	The target variable (after '#') is used in the expression:
	every occurrence of @<target_variable> is replaced by the current loop value.
	"""
	if not prod_expr.startswith('?'):
		raise ValueError("Productation expression must start with '?'")
	
	parts = prod_expr[1:].split(',')
	if len(parts) != 4:
		raise ValueError("Productation expression must have 4 parts separated by commas")
	
	lower_str, upper_str, target_str, expr_str = [p.strip() for p in parts]
	
	if not target_str.startswith('#'):
		raise ValueError("Target variable part must start with '#'")
	target_var = target_str[1:]
	
	lower_resolved = resolve_vars(lower_str, variables)
	upper_resolved = resolve_vars(upper_str, variables)
	
	try:
		lower_bound = int(eval(lower_resolved))
		upper_bound = int(eval(upper_resolved))
	except Exception as e:
		raise ValueError(f"Error evaluating bounds: {e}")
	
	expr_str = expr_str.strip()
	if expr_str.startswith('(') and expr_str.endswith(')'):
		expr_str = expr_str[1:-1]
	
	total = 1
	for i in range(lower_bound, upper_bound + 1):
		iteration_expr = expr_str.replace(f"@{target_var}", str(i))
		iteration_expr = resolve_vars(iteration_expr, variables)
		try:
			step_value = eval(iteration_expr)
		except Exception as e:
			raise ValueError(f"Error evaluating iteration expression '{iteration_expr}': {e}")
		total *= step_value
	
	variables[target_var] = total
	return total

def split_equation(equation: str) -> list:
	"""
	Splits an equation string into a list of function expressions.
	The semicolon (;) is used as the separator.
	
	Example:
		Input: "(1+1+1+1)#x; $@x,4,#k,(@k*2)"
		Output: ["(1+1+1+1)#x", "$@x,4,#k,(@k*2)"]
	"""
	stripped = equation.replace(" ", "")
	functions = [expr for expr in stripped.split(";") if expr]
	return functions

if __name__ == "__main__":
	variables = {}
	
	equation = "(1+1+1+1)#x; ?@x,8,#k,(2)"

	expressions = split_equation(equation)
	
	for expr in expressions:
		if '#' in expr and not expr.startswith('$') and not expr.startswith('?'):
			result = process_assignment(expr, variables)
		elif expr.startswith('$'):
			result = process_summation(expr, variables)
		elif expr.startswith('?'):
			result = process_productation(expr, variables)

def clean_expression(expr: str) -> str:
    """Clean up expression and ensure balanced parentheses"""
    expr = expr.replace(' ', '')
    while '(()' in expr or '())' in expr:
        expr = expr.replace('()', '')
    open_count = expr.count('(')
    close_count = expr.count(')')
    if open_count > close_count:
        expr += ')' * (open_count - close_count)
    return expr

def create_graph(expr: str, x_range=(-10, 10), y_range=None, mode='y') -> io.BytesIO:
    """Create a graph from the given expression"""
    plt.clf()
    
    try:
        expr = clean_expression(expr)
        expr = expr.replace('^', '**')
        
        if mode == 'r':
            theta = np.linspace(0, 2*np.pi, 1000)
            expr_polar = expr.replace('x', 'theta')
            expr_polar = check_for_abs(expr_polar)
            expr_polar = process_radicals(expr_polar)
            
            context = {
                'theta': theta, 
                'np': np,
                'sin': np.sin,
                'cos': np.cos,
                'tan': np.tan,
                'sqrt': np.sqrt,
                'abs': np.abs,
                'log': np.log,
                'pi': np.pi,
                'e': np.e,
                'pow': pow
            }
            
            r = eval(expr_polar, {"__builtins__": {}}, context)
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            plt.plot(x, y, 'b-', label=f'r = {expr}')
            plt.axis('equal')
        else:
            x = np.linspace(x_range[0], x_range[1], 1000)
            expr = re.sub(r'(\d+)([a-zA-Z])', r'\1*\2', expr)
            
            context = {
                'x': x,
                'np': np,
                'sin': np.sin,
                'cos': np.cos,
                'tan': np.tan,
                'sqrt': np.sqrt,
                'abs': np.abs,
                'log': np.log,
                'pi': np.pi,
                'e': np.e,
                'arcsin': np.arcsin,
                'arccos': np.arccos,
                'arctan': np.arctan,
                'asin': np.arcsin,
                'acos': np.arccos,
                'atan': np.arctan
            }
            
            y = eval(expr, context)
            plt.plot(x, y, 'b-', label=f'y = {expr}')

        plt.grid(True)
        plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        plt.axvline(x=0, color='k', linestyle='-', alpha=0.3)
        plt.legend()

        if y_range:
            plt.ylim(y_range)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf
        
    except Exception as e:
        raise ValueError(str(e))