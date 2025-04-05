"""Math tool for performing calculations."""

import ast
import math
import operator
from typing import Any, Dict, Union

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool

# Define allowed operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,  # Unary negation
}

# Define allowed functions
FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    # Math module functions
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "degrees": math.degrees,
    "radians": math.radians,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "floor": math.floor,
    "ceil": math.ceil,
}

# Define allowed constants
CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "nan": math.nan,
    "tau": math.tau,
}


class MathEvaluator(ast.NodeVisitor):
    """Evaluates mathematical expressions safely."""

    def __init__(self):
        self.allowed_operators = OPERATORS
        self.allowed_functions = FUNCTIONS
        self.allowed_constants = CONSTANTS

    def visit_BinOp(self, node):
        """Handle binary operations."""
        left = self.visit(node.left)
        right = self.visit(node.right)

        operator_type = type(node.op)
        if operator_type not in self.allowed_operators:
            raise ValueError(f"Unsupported operator: {operator_type.__name__}")

        return self.allowed_operators[operator_type](left, right)

    def visit_UnaryOp(self, node):
        """Handle unary operations (like -x)."""
        operand = self.visit(node.operand)

        operator_type = type(node.op)
        if operator_type not in self.allowed_operators:
            raise ValueError(f"Unsupported unary operator: {operator_type.__name__}")

        return self.allowed_operators[operator_type](operand)

    def visit_Name(self, node):
        """Handle variable names (constants)."""
        if node.id in self.allowed_constants:
            return self.allowed_constants[node.id]
        raise ValueError(f"Unsupported variable name: {node.id}")

    def visit_Call(self, node):
        """Handle function calls."""
        if not isinstance(node.func, ast.Name):
            raise ValueError("Indirect function calls are not supported")

        func_name = node.func.id
        if func_name not in self.allowed_functions:
            raise ValueError(f"Unsupported function: {func_name}")

        args = [self.visit(arg) for arg in node.args]
        return self.allowed_functions[func_name](*args)

    def visit_Num(self, node):
        """Handle numeric literals."""
        return node.n

    def visit_Constant(self, node):
        """Handle constants (Python 3.8+)."""
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    def visit_List(self, node):
        """Handle list literals."""
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node):
        """Handle tuple literals."""
        return tuple(self.visit(elt) for elt in node.elts)

    def generic_visit(self, node):
        """Handle unsupported nodes."""
        raise ValueError(f"Unsupported operation: {type(node).__name__}")

    @classmethod
    def evaluate(cls, expression: str) -> Union[int, float, list, tuple]:
        """Safely evaluate a mathematical expression.

        Args:
            expression: A string containing a mathematical expression

        Returns:
            The result of the evaluation

        Raises:
            ValueError: If the expression contains unsupported operations
            SyntaxError: If the expression is syntactically invalid
        """
        try:
            node = ast.parse(expression, mode="eval")
            evaluator = cls()
            return evaluator.visit(node.body)
        except SyntaxError:
            raise ValueError(f"Invalid expression syntax: {expression}")


@register_tool
class MathTool(BaseTool):
    """Tool for evaluating mathematical expressions."""

    name = "math"
    description = "Evaluate mathematical expressions and perform calculations"
    requires_confirmation = False

    def execute(
        self, expression: str, expressions: str = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Evaluate one or more mathematical expressions.

        Args:
            expression: The primary mathematical expression to evaluate
            expressions: Optional additional expressions separated by semicolons (e.g., "5+5; 10*2; sqrt(16)")
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the evaluation was successful
                result: The result of the primary expression
                results: List of results if multiple expressions were provided
                expressions_evaluated: List of expressions that were evaluated
                error: Error message if any
        """
        try:
            # Evaluate the primary expression
            result = MathEvaluator.evaluate(expression)

            # Initialize results for multiple expressions
            all_results = [result]
            all_expressions = [expression]

            # Check if additional expressions were provided
            if expressions:
                # Split by semicolons and evaluate each expression
                extra_expressions = [expr.strip() for expr in expressions.split(";")]

                for expr in extra_expressions:
                    if expr:  # Skip empty expressions
                        try:
                            expr_result = MathEvaluator.evaluate(expr)
                            all_results.append(expr_result)
                            all_expressions.append(expr)
                        except Exception as e:
                            # If one expression fails, include error but continue with others
                            all_results.append(f"Error: {str(e)}")
                            all_expressions.append(expr)

            return {
                "success": True,
                "result": result,  # Primary result for backward compatibility
                "results": all_results,  # All results including the primary
                "expressions_evaluated": all_expressions,
                "error": "",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "results": [],
                "expressions_evaluated": [],
                "error": f"Error evaluating expression: {str(e)}",
            }
