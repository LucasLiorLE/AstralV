import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle, File
from discord.ui import View, Button, button
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
    process_factorial,
    create_graph,
    symbolic_derivative,
    definite_integral
)
import numpy as np
class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.current_page = "basic"
        
    def create_basic_embed(self):
        embed = discord.Embed(title="Calculator Help - Basic Operations")
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
            name="Trigonometric Functions",
            value=(
                "Degree Mode (90°):\n"
                "`dsin(90)` → 1\n"
                "`dcos(90)` → 0\n"
                "`dtan(45)` → 1\n\n"
                "Radian Mode (π):\n"
                "`rsin(pi/2)` → 1\n"
                "`rcos(pi)` → -1\n"
                "`rtan(pi/4)` → 1"
            ),
            inline=False
        )
        return embed
        
    def create_advanced_embed(self):
        embed = discord.Embed(title="Calculator Help - Advanced Operations")
        embed.add_field(
            name="Advanced math symbols:",
            value=(
                "Variable Assignment `#`\n"
                "Variable Calling `@`\n"
                "Productation `?`\n"
                "Summation `$`\n"
                "New Line `;`"
            )
        )
        embed.add_field(
            name="Trigonometric Functions",
            value=(
                "**Degree Mode:**\n"
                "`dsin, dcos, dtan`\n"
                "**Radian Mode:**\n"
                "`rsin, rcos, rtan`\n"
                "**Inverse Functions:**\n"
                "`arcsin/asin, arccos/acos, arctan/atan`"
            )
        )
        embed.add_field(
            name="Examples",
            value=(
                "```• (dsin(90))#x\n"
                "• (1+1+1+1)#x; $@x,4,#k,(@k*2)\n"
                "• rsin(pi/2)^2 + rcos(pi/2)^2\n"
                "• arcsin(0.5)#angle```"
            ),
            inline=False
        )
        return embed
        
    def create_graph_embed(self):
        embed = discord.Embed(title="Calculator Help - Graphing")
        embed.add_field(
            name="Graphing Functions",
            value=(
                "Plot mathematical functions using:\n"
                "`/calculator graph equation:x^2 mode:y xmin:-10 xmax:10 ymin:-5 ymax:5`\n\n"
                "**Modes:**\n"
                "• y - Regular cartesian (y = f(x))\n"
                "• r - Polar coordinates (r = f(x))\n\n"
                "**Supported functions:**\n"
                "• Basic operations (+, -, *, /, ^)\n"
                "• Trig - Degrees (dsin, dcos, dtan)\n"
                "• Trig - Radians (rsin, rcos, rtan)\n"
                "• Inverse trig (arcsin, arccos, arctan)\n"
                "• Others (sqrt, abs, log, e^)\n"
                "• Advanced operations (summation, etc)"
            )
        )
        embed.add_field(
            name="Examples",
            value=(
                "```• Regular: equation:2*x^2+3 mode:y\n"
                "• Polar: equation:2*cos(3*x) mode:r\n"
                "• With bounds: equation:sin(x) ymin:-2 ymax:2```"
            ),
            inline=False
        )
        return embed

    def create_calculus_embed(self):
        embed = discord.Embed(title="Calculator Help - Calculus")
        embed.add_field(
            name="Derivative",
            value=(
                "Calculate derivatives:\n"
                "`/calculator derivative equation:x^2 order:1`\n"
                "• Supports all math functions\n"
                "• Order specifies nth derivative"
            )
        )
        embed.add_field(
            name="Integral",
            value=(
                "Calculate definite integrals:\n"
                "`/calculator integral equation:x^2 lower:0 upper:1`\n"
                "• Supports all math functions\n"
                "• Evaluates between lower and upper bounds"
            )
        )
        embed.add_field(
            name="Examples",
            value=(
                "```• derivative: sin(x)\n"
                "• derivative: x^3 order:2\n"
                "• integral: x^2 lower:0 upper:1\n"
                "• integral: sin(x) lower:0 upper:pi```"
            ),
            inline=False
        )
        return embed

    @button(label="Basic", style=ButtonStyle.secondary)
    async def basic_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = "basic"
        await interaction.response.edit_message(embed=self.create_basic_embed(), view=self)
        
    @button(label="Advanced", style=ButtonStyle.secondary)
    async def advanced_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = "advanced"
        await interaction.response.edit_message(embed=self.create_advanced_embed(), view=self)
        
    @button(label="Graphing", style=ButtonStyle.secondary)
    async def graph_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = "graph"
        await interaction.response.edit_message(embed=self.create_graph_embed(), view=self)

    @button(label="Calculus", style=ButtonStyle.secondary)
    async def calculus_button(self, interaction: discord.Interaction, button: Button):
        self.current_page = "calculus"
        await interaction.response.edit_message(embed=self.create_calculus_embed(), view=self)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class CalculatorCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="calculator", description="Calculations...", guild_only=False)

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
            view = HelpView()
            embed = view.create_basic_embed()
            await interaction.response.send_message(embed=embed, view=view)
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

    @app_commands.command(name="graph")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Polar", value="r"),
            app_commands.Choice(name="Cartesian", value="y")
        ]
    )
    async def graph(
        self, 
        interaction: discord.Interaction, 
        equation: str, 
        mode: str = 'y',
        xmin: float = -10.0, 
        xmax: float = 10.0,
        ymin: float = None,
        ymax: float = None
    ):
        await interaction.response.defer()
        try:
            if mode not in ['y', 'r']:
                await interaction.followup.send("Mode must be either 'y' for regular graphs or 'r' for polar graphs.")
                return
            
            if not is_safe_expression(equation):
                await interaction.followup.send("Expression contains unsafe operations.")
                return
            
            if any(char in equation for char in ['#', '@', '$', '?', ';']):
                functions = split_equation(equation)
                result, _ = self.calculate(functions)
                if isinstance(result, str) and result.startswith("Error"):
                    await interaction.followup.send(result)
                    return
                equation = str(list(result.values())[-1])
            
            y_range = (ymin, ymax) if ymin is not None and ymax is not None else None
            graph_data = create_graph(equation, (xmin, xmax), y_range, mode)
            
            file = File(fp=graph_data, filename='graph.png')
            embed = discord.Embed(
                title="Function Graph",
                description=f"{'y' if mode == 'y' else 'r'} = {equation}"
            )
            embed.set_image(url="attachment://graph.png")
            await interaction.followup.send(file=file, embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")

    @app_commands.command(name="derivative")
    async def derivative(self, interaction: discord.Interaction, equation: str, order: int = 1):
        await interaction.response.defer()
        try:
            if not is_safe_expression(equation):
                return await interaction.followup.send("Expression contains unsafe operations.")
            
            deriv = symbolic_derivative(equation, order=order)
            x_vals = np.linspace(-2, 2, 5)
            results = [f"x={x:.2f}: {deriv(x):.4f}" for x in x_vals]
            
            embed = discord.Embed(
                title=f"Derivative of order {order}",
                description=f"Expression: `{equation}`\n\nSample values:\n" + "\n".join(results)
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")

    @app_commands.command(name="integral")
    async def integral(self, interaction: discord.Interaction, equation: str, lower: float, upper: float):
        await interaction.response.defer()
        try:
            if not is_safe_expression(equation):
                return await interaction.followup.send("Expression contains unsafe operations.")
            
            result = definite_integral(equation, lower, upper)
            embed = discord.Embed(
                title="Definite Integral",
                description=f"Expression: `{equation}`\nBounds: [{lower}, {upper}]\nResult: {result:.6f}"
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")

class CalculatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(CalculatorCommandGroup())

async def setup(bot):
    await bot.add_cog(CalculatorCog(bot))