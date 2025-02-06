from bot_utils import (
    mc_fetchUUID,
    hypixelAPI,

    load_commands,
    handle_logs,
)

import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands, ButtonStyle

import re
from aiohttp import ClientSession
from datetime import datetime, timezone

class HypixelView(View):
    def __init__(self, player_data, message, current_page="main"):
        super().__init__(timeout=None)
        self.message = message
        self.player_data = player_data
        self.player = self.player_data.get("player", {})
        self.current_page = current_page

        self.main_button = Button(label="Main", style=ButtonStyle.secondary)
        self.main_button.callback = self.show_main_page
        self.add_item(self.main_button)

        self.skyblock_button = Button(label="Skyblock", style=ButtonStyle.secondary)
        self.skyblock_button.callback = self.show_skyblock_page
        self.add_item(self.skyblock_button)

        self.arcade_button = Button(label="Arcade", style=ButtonStyle.secondary)
        self.arcade_button.callback = self.show_arcade_page
        self.add_item(self.arcade_button)

        self.bedwars_button = Button(label="Bedwars", style=ButtonStyle.secondary)
        self.bedwars_button.callback = self.show_bedwars_page
        self.add_item(self.bedwars_button)

        self.skywars_button = Button(label="Skywars", style=ButtonStyle.secondary)
        self.skywars_button.callback = self.show_skywars_page
        self.add_item(self.skywars_button)

        self.update_buttons()
    
    def update_buttons(self):
        self.main_button.disabled = self.current_page == "main"
        self.skyblock_button.disabled = self.current_page == "skyblock"
        self.arcade_button.disabled = self.current_page == "arcade"
        self.bedwars_button.disabled = self.current_page == "bedwars"
        self.skywars_button.disabled = self.current_page == "skywars"

    async def show_skywars_page(self, interaction: discord.Interaction):
        self.current_page = "skywars"
        self.update_buttons()

        embed = self.create_skywars_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_skywars_embed(self):
        profile_data = self.player.get("stats", {}).get("SkyWars", {})

        souls = profile_data.get("souls", 0)
        coins = profile_data.get("coins", 0)
        skywars_level = profile_data.get("levelFormatted", "Unknown")
        kills = profile_data.get("kills", 0)
        deaths = profile_data.get("deaths", 0)
        wins = profile_data.get("wins", 0)
        games_played = profile_data.get("games_played_skywars", 0)
        win_streak = profile_data.get("win_streak", 0)
        time_played = profile_data.get("time_played", 0)
        longest_bow_kill = profile_data.get("longest_bow_kill", 0)

        embed = discord.Embed(
            title="SkyWars Stats",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="SkyWars Level", value=f"{skywars_level.replace('§', '')}")
        embed.add_field(name="Souls", value=f"{souls:,}")
        embed.add_field(name="Coins", value=f"{coins:,}")
        embed.add_field(name="Kills", value=f"{kills:,}")
        embed.add_field(name="Deaths", value=f"{deaths:,}")
        embed.add_field(name="K/D Ratio", value=f"{kills / deaths if deaths > 0 else kills:.2f}")
        embed.add_field(name="Wins", value=f"{wins:,}")
        embed.add_field(name="Games Played", value=f"{games_played:,}")
        embed.add_field(name="Win Streak", value=f"{win_streak:,}")
        embed.add_field(name="Time Played", value=f"{time_played} seconds") # TODO: Format this?
        embed.add_field(name="Longest Bow Kill", value=f"{longest_bow_kill} blocks")

        return embed

    async def show_bedwars_page(self, interaction: discord.Interaction):
        self.current_page = "bedwars"
        self.update_buttons()

        embed = self.create_bedwars_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_bedwars_embed(self):
        profile_data = self.player.get("stats", {}).get("Bedwars", {})
        
        games_played = profile_data.get("games_played_bedwars", 0)
        wins = profile_data.get("wins_bedwars", 0)
        losses = profile_data.get("losses_bedwars", 0)
        kills = profile_data.get("kills_bedwars", 0)
        deaths = profile_data.get("deaths_bedwars", 0)
        beds_broken = profile_data.get("beds_broken_bedwars", 0)
        beds_lost = profile_data.get("beds_lost_bedwars", 0)
        
        embed = discord.Embed(
            title="Bedwars Stats",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Games Played", value=f"{games_played}", inline=False)
        embed.add_field(
            name="Wins/Losses", 
            value=f"{wins}/{losses} ({(wins/losses * 100):.2f}%)" if losses > 0 else f"{wins}/{losses} (N/A)", 
            inline=False
        )
        embed.add_field(
            name="Kills/Deaths", 
            value=f"{kills}/{deaths} ({(kills/deaths * 100):.2f}%)" if deaths > 0 else f"{kills}/{deaths} (N/A)", 
            inline=False
        )
        embed.add_field(
            name="Beds Broken/Lost", 
            value=f"{beds_broken}/{beds_lost} ({(beds_broken/beds_lost) * 100:.2f}%)" if beds_lost > 0 else f"{beds_broken}/{beds_lost} (N/A)", 
            inline=False
        )

        return embed
        
    async def show_arcade_page(self, interaction: discord.Interaction):
        self.current_page = "arcade"
        self.update_buttons()

        embed =  self.create_arcade_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_arcade_embed(self):
        profile_data = self.player.get("stats", {}).get("Arcade", {})
        coins = profile_data.get("coins", 0)
        
        embed = discord.Embed(
            title="Arcade Stats",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Coins", value=f"{coins:,}", inline=False)

        pixel_party = profile_data.get("pixel_party", {})
        embed.add_field(
            name="Pixel Party",
            value=f"Games Played: {pixel_party.get('games_played', 0)}\n"
                f"Games Played (Normal): {pixel_party.get('games_played_normal', 0)}",
            inline=False
        )

        dropper = profile_data.get("dropper", {})
        map_stats = dropper.get("map_stats", {})
        dropper_maps = "\n".join(
            f"{map_name.title()}: Best Time: {stats.get('best_time', 'N/A')} ms, Completions: {stats.get('completions', 0)}"
            for map_name, stats in map_stats.items()
        )
        embed.add_field(
            name="Dropper",
            value=f"Fails: {dropper.get('fails', 0)}\n"
                f"Games Played: {dropper.get('games_played', 0)}\n"
                f"Maps Completed: {dropper.get('maps_completed', 0)}\n\n"
                f"**Map Stats:**\n{dropper_maps}",
            inline=False
        )

        # print(profile_data)
        # TODO: This doesn't work on large profiles (too much lines)
        # Probably just use multiple embeds via returning multiple if too much.
        # Work on in later verions

        stats_party_games = {
            (
                re.sub(
                    r"(.*) (Deaths|Kills|Final Kills|Wins|Score|Time)$",
                    r"(\2) \1",
                    key.title().replace("_", " ").replace("Party", "").strip()
                )
            ): value
            for key, value in profile_data.items() if isinstance(value, int) and key != "coins"
        }

        party_games_stats = "\n".join(f"{k}: {v}" for k, v in stats_party_games.items())
        if stats_party_games is not None:
            embed.add_field(name="Party Games Stats", value=party_games_stats, inline=False)

        return embed

    async def show_skyblock_page(self, interaction: discord.Interaction):
        self.current_page = "skyblock"
        self.update_buttons()

        embed = self.create_skyblock_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_skyblock_embed(self):
        cookie_claim_time = self.player.get("skyblock_free_cookie", None)
        cookie_string = f"<t:{int(int(cookie_claim_time) / 1000)}:F>" if cookie_claim_time is not None else "Never claimed."

        profile_data = self.player.get("stats", None).get("SkyBlock", None).get("profiles", None)

        cute_names = [profile_data[i]["cute_name"] for i in profile_data]
        profile_ids = [profile_data[i]["profile_id"] for i in profile_data]

        embed = discord.Embed(
            title="Skyblock data", 
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Free booster cookie claim time", value=f"{cookie_string}", inline=False)
        for profiles in range(len(cute_names)):
            embed.add_field(name=cute_names[profiles], value=profile_ids[profiles], inline=False)
        return embed
    
    async def show_main_page(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons()

        embed = self.create_main_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_main_embed(self):
        id = self.player.get("_id", "Unknown")
        rank = self.player.get("newPackageRank", "Regular")
        username = self.player.get("displayname", "Unknown")

        firstLogin = self.player.get("firstLogin", 0)
        lastLogin = self.player.get("lastLogin", 0)
        lastLogout = self.player.get("lastLogout", 0)
        recentGame = self.player.get("mostRecentGameType", "Unknown")

        embed = discord.Embed(
            title=f"Hypixel profile for [{rank.replace("_", "").replace("PLUS", "+")}] {username} ({id})",
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Login and dates", 
            value=f"Join Date: <t:{int(int(firstLogin) / 1000)}:F>\n"
            f"Last Login: <t:{int(int(lastLogin) / 1000)}:F>\n"
            f"Last Logout: <t:{int(int(lastLogout) / 1000)}:F>\n"
            f"Most recent game: {recentGame.replace("_", " ").title()}",
            inline=False
        )

        # Ignore why I stop using camel case it's how im feeling and I do these like 2 days apart
        exp = self.player.get("networkExp", 0)
        level_rewards = self.player.get("leveling", {}).get("claimedRewards", {})
        achievement_points = self.player.get("achievementPoints", 0)
        karma = self.player.get("karma", 0)
        achievements = self.player.get("achievements", 0)

        embed.add_field(
            name="Levels and Experience",
            value = f"Total EXP: {exp:,}\n"
            f"Claimed level rewards: {len(level_rewards):,}\n"
            f"Achievement Points: {achievement_points:,}\n"
            f"Total achievements: {len(achievements):,}\n"
            f"Karma: {karma:,}",
            inline=False
            )

        last_claimed_reward = self.player.get("lastClaimedReward", 0)
        reward_high_score = self.player.get("rewardHighScore", 0)
        reward_score = self.player.get("rewardScore", 0)
        reward_streak = self.player.get("rewardStreak", 0)
        total_daily_rewards = self.player.get("totalDailyRewards", 0)
        total_rewards = self.player.get("totalRewards", 0)

        embed.add_field(
            name="Daily Rewards",
            value = f"Last claim time: <t:{int(last_claimed_reward / 1000)}:F>\n" if isinstance(last_claimed_reward, int) else "Last claim time: Never claimed\n"
            f"Reward score/streak: {reward_score:,}/{reward_streak:,}\n"
            f"Reward highscore: {reward_high_score:,}\n"
            f"Total daily rewards: {total_daily_rewards:,}\n"
            f"Total rewards: {total_rewards:,}",
            inline=False
        )

        # This is "None" and not None because NoneType has no attribute for replace, while a string does
        current_click_effect = self.player.get("currentClickEffect", "None")
        particle_pack = self.player.get("particlePack", "None")
        current_gadget = self.player.get("currentGadget", "None")
        current_pet = self.player.get("currentPet", "None")

        embed.add_field(
            name="Cosmetics",
            value=f"Current click effect: {current_click_effect.replace("_", " ").title()}\n"
            f"Particle pack: {particle_pack.replace("_", " ").title()}\n"
            f"Current gadget: {current_gadget.replace("_", " ").title()}\n"
            f"Current pet: {current_pet.replace("_", " ").title()}"
        )

        return embed

class HypixelCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="hypixel", description="Base Hypixel commands")
        load_commands(self.commands, "hypixel")

    @app_commands.command(name="profile", description="Get a player's Hypixel stats.")
    @app_commands.describe(username="Their Minecraft username.")
    async def hyProfile(self, interaction: discord.Interaction, username: str):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            uuid = await mc_fetchUUID(interaction, username)
            async with ClientSession() as session:
                async with session.get(f"https://api.hypixel.net/player?key={hypixelAPI}&uuid={uuid}") as response:
                    if response.status == 200:
                        message = await interaction.followup.send("Fetching profile...")
                        data = await response.json()
                        view = HypixelView(data, message)
                        embed = view.create_main_embed()
                        await message.edit(embed=embed, view=view, content=None)
                    else:
                        await interaction.followup.send(f"Failed to retrieve data. Status code: {response.status}")
        except Exception as e:
            await handle_logs(interaction, e)

class SkyblockView(View):
    def __init__(self, player_data, message, uuid, find_profile, current_page="main"):
        super().__init__(timeout=None)
        self.uuid = uuid
        self.message = message
        self.player_data = player_data
        self.find_profile = find_profile
        self.profiles = self.player_data.get("profiles", {})
        self.current_page = current_page

        self.profile_data = (
            self.profiles[find_profile]
            if len(self.profiles) > find_profile
            else None
        )

        self.main_button = Button(label="Main (Base stats)", style=ButtonStyle.secondary)
        self.main_button.callback = self.show_main_page
        self.add_item(self.main_button)

        self.mine_button = Button(label="Mining", style=ButtonStyle.secondary)
        self.mine_button.callback = self.show_mine_page
        self.add_item(self.mine_button)

        self.farm_button = Button(label="Farming", style=ButtonStyle.secondary)
        self.farm_button.callback = self.show_farm_page
        self.add_item(self.farm_button)

        self.collections_button = Button(label="Collections", style=ButtonStyle.secondary)
        self.collections_button.callback = self.show_collections_page
        self.add_item(self.collections_button)

        self.misc_button = Button(label="Miscellaneous", style=ButtonStyle.secondary)
        self.misc_button.callback = self.show_misc_page
        self.add_item(self.misc_button)
        '''
        TODO: Add these buttons for later versions?
        $.members.found_profile.events.easter (For chocolate factory)
        $.members.found_profile.dungeons (For dungeons data)
        $.members.found_profile.nether_island_player_data (That place i forgot what it was called)
        $.members.found_profile.auctions

        '''

        self.update_buttons()

    def get_level(self, total_xp, type=None):
        exp_dict = {
            "uni_xp": [
                0, 50, 175, 375, 675, 1175, 1925, 2925, 4425, 6425, 9925, 14925, 22425, 32425, 47425, 67425,
                97425, 147425, 222425, 322425, 522425, 822425, 1222425, 1722425, 2322425, 3022425, 3822425, 4722425, 5722425,
                6822425, 8022425, 9322425, 10722425, 12222425, 13822425, 15522425, 17322425, 19222425, 21222425, 23322425,
                25522425, 27822425, 30222425, 32722425, 35322425, 38072425, 40972425, 44072425, 47472425, 51172425, 55172425,
                59472425, 64072425, 68972425, 74172425, 79672425, 85472425, 91572425, 97972425, 104672425, 111672425
            ],
            "runecrafting": [
                0, 50, 150, 275, 435, 635, 885, 1200, 1600, 2100, 2725, 3510, 4510, 5760, 7325, 9325, 11825, 14950, 18950,
                23950, 30200, 38050, 47850, 60100, 75400, 94450
            ],
            "social": [
                0, 50, 150, 300, 550, 1050, 1800, 2800, 4050, 5550, 7550, 10050, 13050, 16800, 21300, 27300, 35300, 45300, 57800, 
                72800, 92800, 117800, 147800, 182800, 222800, 272800
            ],
            "dungeoneering": [
                0, 50, 125, 235, 395, 625, 955, 1425, 2095, 3045, 4385, 6275, 8940, 12700, 17960, 25340, 35640, 50040, 
                70040, 97640, 135640, 188140, 259640, 356640, 488640, 668640, 911640, 1239640, 1684640, 2284640, 3084640, 
                4149640, 5559640, 7459640, 9959640, 13259640, 17759640, 23559640, 31359640, 41559640, 55559640, 74559640, 
                99559640, 132559640, 177559640, 235559640, 315559640, 423559640, 569809640
            ]
        }

        return next((level for level in range(len(exp_dict[type]) - 1, -1, -1) if total_xp >= exp_dict[type][level]), 0)

    def update_buttons(self):
        self.main_button.disabled = self.current_page == "main"
        self.mine_button.disabled = self.current_page == "mine"
        self.farm_button.disabled = self.current_page == "farm"
        self.collections_button.disabled = self.current_page == "collections"
        self.misc_button.disabled = self.current_page == "misc"

    async def show_mine_page(self, interaction: discord.Interaction):
        self.current_page = "mine"
        self.update_buttons()
        
        embed = self.create_mine_embed()
        await self.message.edit(embed=embed, view=self)

        await interaction.response.defer()

    def create_mine_embed(self):
        embed = discord.Embed(
            title="Mining Stats",
            color=discord.Color.light_grey(),
            timestamp=datetime.now(timezone.utc)
        )

        found_profile = self.profile_data.get("members", {}).get(self.uuid, {})
        mining = found_profile.get("mining_core", {})

        last_hotm_reset = mining.get("last_reset", None)

        tokens = mining.get("token", 0)
        tokens_spent = mining.get("tokens_spent", 0)

        mithril = mining.get("powder_mithril_total", 0) # TODO: Check if it is this or just powder_mithril
        gemstone = mining.get("powder_gemstone_total", 0)
        glacite = mining.get("powder_glacite_total", 0)

        embed.add_field(
            name="Powder",
            value=f"Mithril: {mithril}\n"
            f"Gemstone: {gemstone}\n"
            f"Glacite: {glacite}",
            inline=False
        )

        hotm_string = f"<t:{int(last_hotm_reset / 1000)}:F>" if last_hotm_reset is not None else "Never"

        embed.add_field(
            name="Heart Of The Mountain",
            value=f"Tokens: {tokens}\n"
            f"Spent: {tokens_spent}\n"
            f"Last HOTM Reset Time: {hotm_string}",
            inline=False
        )

        return embed

    async def show_farm_page(self, interaction: discord.Interaction):
        self.current_page = "farm"
        self.update_buttons()
        
        embed = self.create_farm_embed()
        await self.message.edit(embed=embed, view=self)

        await interaction.response.defer()

    def create_farm_embed(self):
        embed = discord.Embed(
            title="Farming Stats",
            color=discord.Color.from_rgb(165, 42, 42), # 0xA52A2A, thinking of getting a darker color
            timestamp=datetime.now(timezone.utc)
        )

        found_profile = self.profile_data.get("members", {}).get(self.uuid, {})
        contests = found_profile.get("jacobs_contest", {})
        medals = contests.get("medals_inv", {})
        perks = contests.get("perks", {})
        personal_bests = contests.get("personal_bests", {})

        m_string = "\n".join(
            f"{medal.replace('_', ' ').title()}: {amount}"
            for medal, amount in medals.items()
        )
        embed.add_field(name="Current Medals", value=m_string or "No medals", inline=False)

        p_string = "\n".join(
            f"{perk.replace('_', ' ').title()}: {value}"
            for perk, value in perks.items()
        )
        embed.add_field(name="Perks", value=p_string or "No perks", inline=False)

        pe_string = "\n".join(
            f"{crop.replace('_', ' ').title()}: {score}"
            for crop, score in personal_bests.items()
        )
        embed.add_field(name="Personal Bests", value=pe_string or "No personal bests", inline=False)

        return embed

    async def show_main_page(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons()

        embed = self.create_main_embed()
        if embed:
            await self.message.edit(embed=embed, view=self)
        else:
            await self.message.edit(content="That is not an account.", embed=None, view=None)
        await interaction.response.defer()

    def create_main_embed(self):
        if self.profile_data is not None:
            profile_id = self.profile_data.get("profile_id", "Unknown")
            cute_name = self.profile_data.get("cute_name", "Unknown")
            creation_date = self.profile_data.get("created_at", 0)
            game_mode = self.profile_data.get("game_mode", "Regular")
            members = self.profile_data.get("members", {})

            creation_thing = f"<t:{int(int(creation_date) / 1000)}:F>" if creation_date > 0 else "Most likely old account."

            embed = discord.Embed(
                title=f"Profile data for: {profile_id}", 
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="Profile Data",
                value=(
                    f"Game Mode: {str(game_mode).title()}\n"
                    f"Cute Name: {cute_name}\n"
                    f"Creation Date: {creation_thing}\n"
                    f"Members: {len(members)}"
                ),
                inline=False
            )

            found_profile = members.get(self.uuid, {})
            exp = found_profile.get("leveling", {}).get("experience", 0)

            experience = found_profile.get("player_data", {}).get("experience", {})
            skills = experience.items()

            objectives = found_profile.get("objectives", {})
            completed_count = sum(1 for objective in objectives.values() if isinstance(objective, dict) and objective.get("status") == "COMPLETE")

            embed.add_field(
                name="Leveling and Advancements",
                value=(
                    f"Level: {int(exp) // 100} ({exp} total EXP)\n"
                    f"Objectives: {completed_count}/{len(objectives)}\n"),
                inline=False
            )

            skill_details = ""
            for skill_name, xp in skills:
                xp_type = skill_name.lower() if skill_name.lower() in skills else "uni_xp"
                level = self.get_level(xp, xp_type)
                skill_details += f"{skill_name.replace('SKILL_', '').title()} Skill: {level} (EXP: {int(xp)})\n"

            if skill_details:
                embed.add_field(name="Skills", value=skill_details, inline=False)

            copper = found_profile.get("garden_player_data", {}).get("copper", 0)
            currencies = found_profile.get("currencies", {})
            essences = currencies.get("essence", {})
            purse = currencies.get("coin_purse", 0)
            bank = found_profile.get("profile", {}).get("bank_account", -1)
            motes = currencies.get("motes_purse", 0)

            embed.add_field(
                name="Economy", 
                value=f"Purse: {purse:.2f}\n"
                f"Bank: {'{:.2f}'.format(bank) if bank > 0 else 'None'}\n"
                f"Copper: {copper}\n"
                f"Motes: {motes}", 
                inline=False
                )
            
            if essences:
                essence_details = ""
                for essence, data in essences.items():
                    current_essence = data.get("current", 0) if data else 0
                    essence_details += f"{essence.title()} Essence: {current_essence}\n"

                embed.add_field(name="Essences", value=essence_details, inline=False)

            gifts = found_profile.get("player_stats", {}).get("gifts", {})
            gift_given = gifts.get("total_recieved", 0)
            gift_recieved = gifts.get("total_given", 0)

            if gift_given or gift_recieved > 0:
                embed.add_field(name="Gifts", value=f"Given: {gift_given}\nRecieved: {gift_recieved}")


            return embed
        else:
            return None

    async def show_misc_page(self, interaction: discord.Interaction):
        self.current_page = "misc"
        self.update_buttons()

        embed = self.create_misc_embed()
        await self.message.edit(embed=embed, view=self)

        await interaction.response.defer()

    def create_misc_embed(self):
        found_profile = self.profile_data.get("members", {}).get(self.uuid, {})
        highest_crit = found_profile.get("player_stats", {}).get("highest_critical_damage", 0)
        highest_damage = found_profile.get("player_stats", {}).get("highest_damage", 0)


        kills = found_profile.get("player_stats", {}).get("kills", {})
        # deaths = found_profile.get("player_stats", {}).get("deaths", {})
        deaths = found_profile.get("player_data", {}).get("death_count", 0)
        # No clue what format this is
        # last_death = found_profile.get("player_data", {}).get("last_death", None)

        def format_mob_data(data):
            # formatted_data = []
            total = 0
            for _, count in data.items():
                total += count
                '''
                mob_name = mob.replace("_", " ").title()
                formatted_data.append(f"{mob_name}: {int(count)}")
                '''
            return total # formatted_data

        embed = discord.Embed(
            title="Misc Data",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Highest Damage", value=f"Normal: {highest_damage:,.2f}\nCritical: {highest_crit:,.2f}", inline=False)

        
        # Kills and deaths have too much items sometimes. Makes it so it's too large to put onto 1 embed
        # TODO: Multiple embeds per message?
        if kills:
            # kills_formatted = "\n".join(format_mob_data(kills))
            kills = format_mob_data(kills)
            embed.add_field(name="Kills", value=f"Total: {kills}", inline=False)

        if deaths:
            # deaths_formatted = "\n".join(format_mob_data(deaths))
            # deaths = format_mob_data(deaths)
            # death_string = f"<t:{int(int(last_death) / 1000)}:F>" if last_death is not None else "Never died."
            embed.add_field(name="Deaths", value=f"Deaths: {deaths}")
            # \nLast Death: {death_string}", inline=False)
            
            
        fairy_souls = found_profile.get("fairy_soul", {})
        total = fairy_souls.get("total_collected", 0)
        exchanged = fairy_souls.get("fairy_exchanges", 0)
        unspent = fairy_souls.get("unspent_souls", 0)

        if fairy_souls is not None:
            embed.add_field(
                name="Fairy Souls", 
                value=f"Total: {total}\nExchanged: {exchanged * 5} ({exchanged} times exchanged)\nUnspent: {unspent}",
                inline=False
            )


        glow_mushrooms = found_profile.get("player_stats", {}).get("glowing_mushrooms_broken", 0)
        sea_kills = found_profile.get("player_stats", {}).get("sea_creature_kills", 0)


        embed.add_field(
            name="Other",
            value=f"Glowing Mushrooms Broken: {glow_mushrooms}\n"
            f"Sea Creature Kills: {sea_kills}",
            inline=False
        )
        
        return embed

    async def show_collections_page(self, interaction: discord.Interaction):
        self.current_page = "collections"
        self.update_buttons()

        embed = self.create_collections_embed()
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    def create_collections_embed(self):

        # TODO: Coming v1.1.25
        embed = discord.Embed(
            title="Coming next version!", 
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )

        return embed    

class SkyblockCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="sb", description="Hypixel skyblock commands")
        
        load_commands(self.commands, "sb")


    @app_commands.command(name="profile", description="Get a Hypixel Skyblock account's data")
    @app_commands.describe(
        profile_id="The profile ID",
        username="A Minecraft username"
    )
    @app_commands.choices(
        profile_id=[
            app_commands.Choice(name="1", value=0),
            app_commands.Choice(name="2", value=1),
            app_commands.Choice(name="3", value=2),
            app_commands.Choice(name="4", value=3),
            app_commands.Choice(name="5", value=4)
        ]
    )
    async def sbprofile(self, interaction: discord.Interaction, username: str, profile_id: int = None):
        await interaction.response.defer()
        try:
            uuid = await mc_fetchUUID(interaction, username)
            async with ClientSession() as session:
                async with session.get(f"https://api.hypixel.net/v2/skyblock/profiles?key={hypixelAPI}&uuid={uuid}") as response:
                    if response.status == 200:
                        message = await interaction.followup.send("Fetching profiles...")
                        data = await response.json()

                        if profile_id is None:
                            profiles = data.get("profiles", [])
                            selected_profile_index = next(
                                (i for i, profile in enumerate(profiles) if profile.get("selected")), 0
                            )
                            profile_id = selected_profile_index

                        view = SkyblockView(data, message, uuid, profile_id)
                        embed = view.create_main_embed()
                        await message.edit(content=None, view=view, embed=embed)
                    else:
                        await interaction.followup.send(f"Failed to retrieve data. Status code: {response.status}")

        except Exception as e:
            await handle_logs(interaction, e)

class HypixelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.bot.tree.add_command(HypixelCommandsGroup())
        self.bot.tree.add_command(SkyblockCommandsGroup())

async def setup(bot):
    await bot.add_cog(HypixelCog(bot))