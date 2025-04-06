import discord
from discord.ext import commands
from discord import app_commands
import random

from matplotlib.legend_handler import HandlerErrorbar

from bot_utils import (
    handle_logs
)

def random_event(player, all_players=None):
    solo_events = [
        ("accidentally fell into a trap and died.", True),
        ("was struck by a falling tree.", True),
        ("fell ill and couldn't survive.", True),
        ("was caught in an explosion.", True),
        ("got caught in a fire.", True),
        ("was struck by lightning.", True),
        ("starved to death.", True),
        ("died from infected wounds.", True),
        ("fell from a cliff.", True),
        ("ate poisonous berries.", True),
        ("found a shelter and stayed safe.", False),
        ("gathered some berries and survived another day.", False),
        ("found clean water to drink.", False),
        ("built a small fire to stay warm.", False),
        ("crafted a makeshift weapon.", False),
        ("found some medical supplies.", False),
        ("caught some fish from a nearby stream.", False),
        ("set up clever traps around their camp.", False),
        ("climbed a tree to scout the area.", False),
        ("found a cave to hide in.", False),
        ("treated their wounds with medicinal herbs.", False),
        ("successfully hunted some small game.", False),
        ("camouflaged their shelter.", False),
        ("found a backpack with supplies.", False),
        ("practiced their survival skills.", False),
        ("built a rainwater collection system.", False),
        ("created a comfortable sleeping spot.", False),
        ("found some edible mushrooms.", False),
        ("spotted a tribute but remained hidden.", False),
        ("sharpened their weapons.", False),
        ("set up an early warning system.", False),
        ("found night vision goggles.", False),
        ("discovered a source of fresh water.", False),
        ("made new arrows for their bow.", False),
        ("found warm clothing.", False),
        ("created a successful snare.", False),
        ("found some energy bars.", False),
        ("got some much-needed rest.", False),
        ("improved their shelter.", False),
        ("found a first aid kit.", False)
    ]

    if not all_players or len(all_players) < 2:
        return random.choice(solo_events)

    if random.random() < 0.3 and len(all_players) >= 2:
        return generate_multi_player_event(player, all_players)
    
    return random.choice(solo_events)

def generate_multi_player_event(player, all_players):
    other_players = [p for p in all_players if p != player]
    
    if not other_players:
        return random_event(player)

    hostile_events = [
        ("tried to ambush **{target}** but failed.", False),
        ("died by **{target}** in combat.", True),
        ("got into a fight with **{target}** but both survived.", False),
        ("threw a spear at **{target}** but missed.", False),
        ("fought **{target}** and died.", True),
        ("poisoned **{target}**'s water supply, killing them.", True),
        ("shot an arrow at **{target}** but they escaped.", False),
        ("snuck up on **{target}** but they got away.", False),
        ("engaged **{target}** in combat but was defeated and died.", "self"),
        ("and **{target}** fought, but neither survived.", "both")
    ]

    cooperative_events = [
        ("formed an alliance with {target}.", False),
        ("shared resources with {target}.", False),
        ("helped {target} treat their wounds.", False),
        ("and {target} set up camp together.", False),
        ("and {target} went hunting together.", False),
        ("worked with {target} to build a shelter.", False),
        ("and {target} shared information about other tributes.", False),
        ("and {target} found a good hiding spot.", False),
        ("and {target} cuddle together for warmth", False)
    ]

    if random.random() < 0.4:
        event_template, is_fatal = random.choice(hostile_events)
        target = random.choice(other_players)
        if is_fatal == "self":
            return (event_template.format(target=target.name), True)
        elif is_fatal == "both":
            return (event_template.format(target=target.name), "both")
        else:
            return (event_template.format(target=target.name), is_fatal)
    else:
        event_template, is_fatal = random.choice(cooperative_events)
        target = random.choice(other_players)
        return (event_template.format(target=target.name), is_fatal)

class HungerGamesView(discord.ui.View):
    def __init__(self, group: 'HungerGamesCommandGroup', interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.group = group
        self.interaction = interaction

    @discord.ui.button(label="Next Event", style=discord.ButtonStyle.blurple)
    async def next_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("Only the person who started the game can trigger events.", ephemeral=True)
            return
        
        await self.group.next_event(interaction)
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Show Districts Status", style=discord.ButtonStyle.gray)
    async def show_districts(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_state = self.group.game_state[self.interaction.user.id]
        alive_players = current_state["players"]
        districts = current_state["districts"]

        embed = discord.Embed(title="Districts Status", 
                            description="**Bold** names indicate deceased tributes.", 
                            color=discord.Color.blue())

        for i, district in enumerate(districts, 1):
            district_members = []
            for player in district:
                if player in alive_players:
                    district_members.append(player.name)
                else:
                    district_members.append(f"**{player.name}**")
            names = ', '.join(district_members)
            embed.add_field(name=f"District {i}", value=names, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class HungerGamesCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="hg", description="Hunger game commands")
        self.player_data = {}
        self.game_state = {}

    def get_player_state(self, game_id, player):
        if 'player_states' not in self.game_state[game_id]:
            self.game_state[game_id]['player_states'] = {}
        
        if player.id not in self.game_state[game_id]['player_states']:
            self.game_state[game_id]['player_states'][player.id] = {
                'items': [],
                'allies': [],
                'health': 100,
                'shelter': False,
                'weapon': None
            }
        
        return self.game_state[game_id]['player_states'][player.id]

    def update_player_state(self, game_id, player, event_text):
        state = self.get_player_state(game_id, player)
        
        if "found a first aid kit" in event_text:
            state['items'].append('first aid kit')
        elif "found some medical supplies" in event_text:
            state['items'].append('bandages')
        elif "crafted a makeshift weapon" in event_text:
            state['weapon'] = 'makeshift weapon'
        elif "found night vision goggles" in event_text:
            state['items'].append('night vision goggles')
        elif "built a shelter" in event_text or "found a cave" in event_text:
            state['shelter'] = True
        
        return state

    def modify_event_based_on_state(self, game_id, player, event_text, is_fatal, target=None):
        state = self.get_player_state(game_id, player)
        
        if target and "attacked" in event_text and is_fatal:
            target_state = self.get_player_state(game_id, target)
            
            if 'first aid kit' in target_state['items'] or 'bandages' in target_state['items']:
                if 'first aid kit' in target_state['items']:
                    target_state['items'].remove('first aid kit')
                elif 'bandages' in target_state['items']:
                    target_state['items'].remove('bandages')
                return (f"tried to kill {target.name}, but they survived thanks to their medical supplies.", False)
            
            if target_state['shelter']:
                return (f"tried to attack {target.name}, but they were safe in their shelter.", False)
        
        return (event_text, is_fatal)

    async def next_event(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)

        current_state = self.game_state[interaction.user.id]
        players = current_state["players"].copy()
        deaths = []
        events = []
        dead_players = set()

        max_deaths = max(1, len(players) // 3)
        
        player_order = players.copy()
        random.shuffle(player_order)
        
        i = 0
        while i < len(player_order):
            player = player_order[i]
            
            if player in dead_players:
                i += 1
                continue
            
            if len(deaths) >= max_deaths:
                event, is_fatal = random_event(player, [p for p in players if p not in dead_players])
                while is_fatal:
                    event, is_fatal = random_event(player, [p for p in players if p not in dead_players])
            else:
                event, is_fatal = random_event(player, [p for p in players if p not in dead_players])
            
            if "{target}" in event:
                available_targets = [p for p in players if p != player and p not in dead_players]
                if not available_targets:
                    event, is_fatal = random_event(player, [player])
                else:
                    target = random.choice(available_targets)
                    event = event.format(target=target.name)
                    event, is_fatal = self.modify_event_based_on_state(interaction.user.id, player, event, is_fatal, target)
                    
                    if is_fatal == "both" and target in players:
                        if len(deaths) + 2 <= max_deaths:
                            deaths.append((player, event))
                            deaths.append((target, f"died in combat with **{player.name}**"))
                            dead_players.add(player)
                            dead_players.add(target)
                            players.remove(player)
                            players.remove(target)
                            events.append((player, event))
                            i += 1
                            continue
                        else:
                            event, is_fatal = random_event(player, [player])
                    elif is_fatal and target in players:
                        if len(deaths) < max_deaths:
                            deaths.append((target, f"was killed by **{player.name}**"))
                            dead_players.add(target)
                            players.remove(target)
                            events.append((player, event))
                            i += 1
                            continue
            
            self.update_player_state(interaction.user.id, player, event)
            events.append((player, event))
            
            if is_fatal is True and len(deaths) < max_deaths:
                deaths.append((player, event))
                dead_players.add(player)
                players.remove(player)
            
            i += 1

        current_state["players"] = players

        embed = discord.Embed(title=f"Day {current_state['day']} Events", 
                            color=discord.Color.gold())
        
        event_texts = []
        for player, event in events:
            if (player, event) not in deaths:
                event_texts.append(f"**{player.name}** {event}")
        
        if event_texts:
            embed.add_field(name="📝 Events", 
                          value="\n".join(event_texts), 
                          inline=False)

        if deaths:
            death_texts = []
            for player, event in deaths:
                death_texts.append(f"**{player.name}** {event}")
            
            embed.add_field(name="☠️ Deaths ☠️", 
                          value="\n".join(death_texts), 
                          inline=False)

        embed.set_thumbnail(url="https://i.imgur.com/gpflnsf.png")

        if len(players) == 1:
            winner = players[0]
            embed.add_field(name="🏆 Game Over 🏆", 
                          value=f"**{winner.name}** is the winner of the Hunger Games!", 
                          inline=False)
            embed.set_thumbnail(url=winner.display_avatar.url)
            self.game_state[interaction.user.id]["game_over"] = True
            await interaction.followup.send(embed=embed)
            return

        embed.add_field(name="Next Event", value="Click the button to continue to the next event!", inline=False)

        current_state['day'] += 1
        self.game_state[interaction.user.id] = current_state

        view = HungerGamesView(self, interaction)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="start")
    async def start(self, interaction: discord.Interaction, players: str, amount: int):
        try:
            try:
                user_ids = [int(p.strip('<@!>')) if p.startswith('<@') else int(p) for p in players.split()]
            except ValueError:
                await interaction.response.send_message("Invalid player list format.", ephemeral=True)
                return

            users = []
            for uid in user_ids:
                try:
                    user = await interaction.client.fetch_user(uid)
                    users.append(user)
                    self.player_data[user.id] = user
                except discord.NotFound:
                    continue

            if amount <= 0:
                await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
                return

            if len(users) < amount:
                await interaction.response.send_message("Not enough players for even one district.", ephemeral=True)
                return

            random.shuffle(users)
            districts = [users[i:i + amount] for i in range(0, len(users), amount)]

            self.game_state[interaction.user.id] = {
                "players": users,
                "districts": districts,
                "day": 1,
                "deaths": []
            }

            embed = discord.Embed(title="Hunger Games Districts", color=discord.Color.gold())
            for i, district in enumerate(districts, 1):
                names = ', '.join(user.name for user in district)
                embed.add_field(name=f"District {i}", value=names, inline=False)

            embed.set_thumbnail(url="https://i.imgur.com/gpflnsf.png")

            view = HungerGamesView(self, interaction)
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            await handle_logs(interaction, e)

    def create_all_deaths_button(self):
        return discord.ui.View().add_item(
            discord.ui.Button(
                label="Show All Deaths", 
                style=discord.ButtonStyle.secondary, 
                custom_id="show_all_deaths"
            )
        )

    @app_commands.command(name="kill")
    async def kill(self, interaction: discord.Interaction, player: discord.User):
        try:
            if interaction.user.id not in self.game_state:
                await interaction.response.send_message("No active game found.", ephemeral=True)
                return

            current_state = self.game_state[interaction.user.id]
            if player not in current_state["players"]:
                await interaction.response.send_message("That player is not in the game.", ephemeral=True)
                return

            current_state["players"].remove(player)
            embed = discord.Embed(title="Player Killed", 
                                description=f"**{player.name}** was forcefully eliminated from the game.", 
                                color=discord.Color.red())
            
            if len(current_state["players"]) == 1:
                winner = current_state["players"][0]
                embed.add_field(name="🏆 Game Over 🏆", 
                            value=f"**{winner.name}** is the winner of the Hunger Games!", 
                            inline=False)
                embed.set_thumbnail(url=winner.display_avatar.url)
                self.game_state[interaction.user.id]["game_over"] = True
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="revive")
    async def revive(self, interaction: discord.Interaction, player: discord.User):
        try:
            if interaction.user.id not in self.game_state:
                await interaction.response.send_message("No active game found.", ephemeral=True)
                return

            current_state = self.game_state[interaction.user.id]
            if player in current_state["players"]:
                await interaction.response.send_message("That player is already alive.", ephemeral=True)
                return

            in_game = False
            for district in current_state["districts"]:
                if player in district:
                    in_game = True
                    break

            if not in_game:
                await interaction.response.send_message("That player was never in this game.", ephemeral=True)
                return

            current_state["players"].append(player)
            embed = discord.Embed(title="Player Revived", 
                                description=f"**{player.name}** has been brought back to life!", 
                                color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

class HungerGamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hg_group = HungerGamesCommandGroup()
        self.bot.tree.add_command(self.hg_group)

async def setup(bot):
    await bot.add_cog(HungerGamesCog(bot))
