import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    handle_logs
)
from .utils import (
    process_assignment,
    process_summation,
    process_productation,
    split_equation,
    check_for_abs,
    is_safe_expression,
    process_radicals,
    process_factorial
)

class CalculatorCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="calculator", description="Calculations...")

    def format_steps(self, equation, vars_history):
        steps = []
        for i, (expr, vars_state) in enumerate(vars_history):
            if '#' in expr and not expr.startswith(('$', '?')):
                var_name = expr.split('#')[1].strip()
                steps.append(f"Step {i+1}: Assignment\n`{expr}` → {var_name} = {vars_state[var_name]}")
            elif expr.startswith('$'):
                var_name = expr.split('#')[1].split(',')[0].strip()
                steps.append(f"Step {i+1}: Summation\n`{expr}` → {var_name} = {vars_state[var_name]}")
            elif expr.startswith('?'):
                var_name = expr.split('#')[1].split(',')[0].strip()
                steps.append(f"Step {i+1}: Productation\n`{expr}` → {var_name} = {vars_state[var_name]}")
        return steps

    def calculate(self, equation):
        variables = {}
        vars_history = []
        try:
            for expr in equation:
                expr = expr.replace('^', '**')
                expr = check_for_abs(expr)
                expr = process_radicals(expr)
                expr = process_factorial(expr)
                
                if '#' in expr and not expr.startswith('$') and not expr.startswith('?'):
                    result = process_assignment(expr, variables)
                elif expr.startswith('$'):
                    result = process_summation(expr, variables)
                elif expr.startswith('?'):
                    result = process_productation(expr, variables)
                    
                vars_history.append((expr, variables.copy()))
                
            return variables, vars_history
        except Exception as e:
            return f"Error: {str(e)}", None

    @app_commands.command(name="help")
    async def help(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="Calculator Help"
            )
            embed.add_field(
                name="Basic math symbols:",
                value=(
                    "Addition `+` (1 + 1)\n"
                    "Subtraction `-` (1 - 1)\n"
                    "Multiplication `*` (2 \* 2)\n"
                    "Division `/` (4 / 2)"
                )
            )
            embed.add_field(
                name="Other math symbols:",
                value=(
                    "Power `**` or ^ (2^2)\n"
                    "Radicals `&` (3&2, 3rd root of 2)\n"
                    "Modulo `%` (10 % 2)\n"
                    "Abs `|| ||` (\||-1\||)\n"
                    "Factorial `!` (4!)"
                )
            )
            embed.add_field(
                name="Advanced math symbols:",
                value=(
                "Variable Assignment `#`\n"
                "Variable Calling `@`\n"
                "Productation `?`\n"
                "Summation `$`\n"
                "New Line `;`\n\n"

                "Examples:\n"
                "```#5 assigns 5 to x\n"
                "@x calls value of x\n"
                "?1,@x products numbers 1 through 5\n"
                "$1,@x sums numbers 1 through 5\n\n"
                "(1+1+1+1)#x; $@x,4,#k,(@k*2)\n"
                "x = 1 + 1 + 1 + 1, which is 4, so x is 4\n"
                "Summation lower bound = @x, which is 4\n"
                "Summation upper bound is 4\n"
                "The output variable is k\n"
                "Iterate k in the loop, in this summation, it's just k*2\n"
                "So basically in here UB and LB are the same\n"
                "4*2 = 8 = k. The output is k, which is 8```"
                )
            )
            embed.add_field(
                name="Notes:",
                value=(
                    "Python expressions also work\n"
                    "round(5.2) returns 5\n"
                    "Can also use abs(), and a lot more!\n"
                    "Basic math symbols only work in /calculator basic\n"
                    "Advanced math symbols only work in /calculator advanced"
                )
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="basic")
    async def basic(self, interaction: discord.Interaction, equation: str):
        try:
            if not is_safe_expression(equation):
                await interaction.response.send_message("Expression contains unsafe operations.")
                return
                
            if any(char in equation for char in ['#', '@', '$', '?', ';']):
                await interaction.response.send_message("Basic mode only supports simple arithmetic operations.")
                return
                
            equation = equation.replace(" ", "")
            equation = equation.replace('^', '**')
            
            if not all(c in '0123456789+-*/.()^&%!|' for c in equation):
                await interaction.response.send_message("Only basic arithmetic and mathematical operations are allowed (+, -, *, /, ^, &, %, !, ||).")
                return
            
            try:
                equation = check_for_abs(equation)
                equation = process_radicals(equation)
                equation = process_factorial(equation)
                result = eval(equation)
                if isinstance(result, float):
                    result = f"{result:.10g}"
                await interaction.response.send_message(f"Result: {result}")
            except Exception as e:
                await interaction.response.send_message(f"Invalid expression: {str(e)}")
                
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="advanced")
    async def advanced(self, interaction: discord.Interaction, *, equation: str):
        try:
            if not is_safe_expression(equation):
                await interaction.response.send_message("Expression contains unsafe operations.")
                return
                
            functions = split_equation(equation)
            if not functions:
                await interaction.response.send_message("Invalid equation!")
                return
            
            result, history = self.calculate(functions)
            if isinstance(result, str) and result.startswith("Error"):
                await interaction.response.send_message(result)
                return
            
            embed = discord.Embed(title="Advanced Calculator", description=f"Original expression:\n`{equation}`")
            
            steps = self.format_steps(functions, history)
            step_text = "\n\n".join(steps)
            if len(step_text) > 1024:
                step_text = step_text[:1021] + "..."
            embed.add_field(name="Calculation Steps", value=step_text, inline=False)
            
            final_vars = "\n".join([f"`{k}` = {v}" for k, v in result.items()])
            embed.add_field(name="Final Values", value=final_vars, inline=False)
            
            await interaction.response.send_message(embed=embed)
                
        except Exception as e:
            await handle_logs(interaction, e)

class CalculatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(CalculatorCommandGroup())

async def setup(bot):
    await bot.add_cog(CalculatorCog(bot))