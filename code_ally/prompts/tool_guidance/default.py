"""Default guidance for when no specific tool is identified."""

DEFAULT_GUIDANCE = """
GENERAL TOOL USAGE GUIDANCE:

When solving problems where no specific tool approach is obvious, follow these guidelines:

1. TASK ANALYSIS:
   - Break down the request into discrete, actionable steps
   - Identify what information you need to gather first
   - Determine which tools are most appropriate for each step
   - Plan a complete solution before starting execution
   - Be prepared to adapt as you discover more information

2. EXPLORATION STRATEGY:
   - Begin with environment discovery: bash commands to understand the context
   - Use grep and glob to find relevant files and code
   - Examine key files to understand the project structure
   - Formulate a hypothesis about how the system works
   - Test your hypothesis with targeted tool usage

3. IMPLEMENTATION APPROACH:
   - Start with minimal, focused changes
   - Create new files rather than modifying existing ones when appropriate
   - Test each change immediately after making it
   - Document your changes with clear comments
   - Verify the complete solution functions as expected

4. PROBLEM-SOLVING SEQUENCE:
   - Environment understanding → Information gathering → Solution design → Implementation → Testing → Refinement
   - For bugs: Reproduction → Identification → Root cause analysis → Fixing → Verification → Prevention
   - For features: Requirements clarification → Design → Implementation → Testing → Documentation

5. TOOL SELECTION PRINCIPLES:
   - For file operations: glob → read → edit/write → verify
   - For code exploration: grep for patterns, read for context
   - For running code: bash for execution, capturing output for analysis
   - For complex searches: combine grep patterns with glob for file types
   - For unknown problems: start with broad searches, then narrow focus

6. VALIDATION AND VERIFICATION:
   - Test each component of your solution individually
   - Verify the complete solution works end-to-end
   - Check for edge cases and potential failure modes
   - Run appropriate tests after making changes
   - Validate against the original requirements

DETAILED EXAMPLES:

Example 1: Implementing a Bug Fix
```
# Step 1: Understand the error and reproduce it
bash command="python -m app.main"  # Run the app to observe the error

# Step 2: Search for relevant code
grep pattern="IndexError" include="*.py"  # Find where this error might be handled
grep pattern="get_user_by_id" include="*.py"  # Find the function mentioned in the error

# Step 3: Examine the problematic code
file_read file_path="/app/models/user.py"  # Read the file containing the issue

# Step 4: Fix the issue
file_edit file_path="/app/models/user.py" old_string="def get_user_by_id(user_id):\n    return users[user_id]" new_string="def get_user_by_id(user_id):\n    if user_id < 0 or user_id >= len(users):\n        return None\n    return users[user_id]"

# Step 5: Test the fix
bash command="python -m app.tests.test_user"  # Run unit tests
bash command="python -m app.main"  # Test the full application
```

Example 2: Adding a New Feature
```
# Step 1: Understand the codebase structure
glob pattern="**/*.py"  # Find all Python files
ls path="/app"  # See main application directories

# Step 2: Find similar features to use as templates
grep pattern="class\\s+\\w+Controller" include="*.py"  # Find controller classes
file_read file_path="/app/controllers/product_controller.py"  # Read a similar controller

# Step 3: Create the new feature files
file_write file_path="/app/controllers/order_controller.py" content="from app.models.order import Order\n\nclass OrderController:\n    def __init__(self):\n        self.orders = []\n    \n    def create_order(self, product_id, quantity, user_id):\n        order = Order(product_id, quantity, user_id)\n        self.orders.append(order)\n        return order\n    \n    def get_orders_by_user(self, user_id):\n        return [order for order in self.orders if order.user_id == user_id]"

file_write file_path="/app/models/order.py" content="class Order:\n    def __init__(self, product_id, quantity, user_id):\n        self.product_id = product_id\n        self.quantity = quantity\n        self.user_id = user_id\n        self.status = 'pending'\n    \n    def complete(self):\n        self.status = 'completed'\n        return True"

# Step 4: Update the main app to register the new feature
file_read file_path="/app/main.py"  # Read the main app file to see how controllers are registered
file_edit file_path="/app/main.py" old_string="from app.controllers.product_controller import ProductController\n\napp = Flask(__name__)\nproduct_controller = ProductController()" new_string="from app.controllers.product_controller import ProductController\nfrom app.controllers.order_controller import OrderController\n\napp = Flask(__name__)\nproduct_controller = ProductController()\norder_controller = OrderController()"

# Step 5: Create tests for the new feature
file_write file_path="/app/tests/test_order.py" content="import unittest\nfrom app.models.order import Order\nfrom app.controllers.order_controller import OrderController\n\nclass TestOrder(unittest.TestCase):\n    def test_create_order(self):\n        controller = OrderController()\n        order = controller.create_order(1, 5, 101)\n        self.assertEqual(order.product_id, 1)\n        self.assertEqual(order.quantity, 5)\n        self.assertEqual(order.status, 'pending')\n\n    def test_complete_order(self):\n        order = Order(1, 5, 101)\n        self.assertEqual(order.status, 'pending')\n        order.complete()\n        self.assertEqual(order.status, 'completed')\n\nif __name__ == '__main__':\n    unittest.main()"

# Step 6: Run tests to verify the new feature
bash command="python -m app.tests.test_order"
```

Example 3: Performance Optimization
```
# Step 1: Identify the slow component
bash command="python -m cProfile -o profile.out app.main"  # Profile the application
bash command="python -m pstats profile.out"  # Analyze the profile data

# Step 2: Examine the problematic code
grep pattern="process_large_dataset" include="*.py"  # Find the slow function
file_read file_path="/app/services/data_processor.py"  # Read the implementation

# Step 3: Optimize the code
file_edit file_path="/app/services/data_processor.py" old_string="def process_large_dataset(data):\n    result = []\n    for item in data:\n        for element in item:\n            if element > 0:\n                result.append(transform(element))\n    return result" new_string="def process_large_dataset(data):\n    # Use list comprehension and avoid nested loops\n    return [transform(element) for item in data for element in item if element > 0]"

# Step 4: Benchmark the optimized solution
file_write file_path="/app/benchmarks/benchmark_processor.py" content="import time\nfrom app.services.data_processor import process_large_dataset\n\ndata = [[i*j for j in range(1000)] for i in range(100)]\n\nstart = time.time()\nresult = process_large_dataset(data)\nend = time.time()\n\nprint(f\"Processed {len(result)} items in {end - start:.4f} seconds\")"

bash command="python -m app.benchmarks.benchmark_processor"  # Run the benchmark
```

When no clear tool path exists, use bash commands to explore the environment and develop a custom approach using the available tools.
"""
