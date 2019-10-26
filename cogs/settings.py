#!/usr/bin/env python3
# Copyright (c) 2016-2017, henry232323
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import csv

from discord.ext import commands
import discord
import asyncio

from random import randint

from io import BytesIO, StringIO

from .utils.data import ServerItem, NumberConverter, create_pages
from .utils import checks
from .utils.translation import _


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        def predicate(ctx):
            if ctx.guild is None:
                raise commands.NoPrivateMessage()
            return True

        return commands.check(predicate(ctx))

    @commands.group(aliases=["s", "configuration", "conf"], invoke_without_command=True)
    async def settings(self, ctx):
        """Get the current server settings"""
        settings = await self.bot.db.get_guild_data(ctx.guild)
        embed = discord.Embed(color=randint(0, 0xFFFFFF),)
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.add_field(name=await _(ctx, "Starting Money"),
                        value=f"{settings['start']} {settings.get('currency', 'dollars')}")
        embed.add_field(name=await _(ctx, "Items"), value="{} {}".format(len(settings['items']), await _(ctx, "items")))
        embed.add_field(name=await _(ctx, "Characters"),
                        value="{} {}".format(len(settings['characters']), await _(ctx, "characters")))
        embed.add_field(name=await _(ctx, "Maps"),
                        value=await _(ctx, "None") if not settings.get("maps") else "\n".join(
                            (x if x != settings.get("default_map") else f"**{x}**") for x in settings["maps"]))
        embed.add_field(name=await _(ctx, "Currency"), value=f"{settings.get('currency', 'dollars')}")
        embed.add_field(name=await _(ctx, "Language"), value=f"{settings.get('language', 'en')}")
        embed.add_field(name=await _(ctx, "Experience Enabled"), value=f"{settings.get('exp', True)}")
        embed.add_field(name=await _(ctx, "Prefix"), value=f"{settings.get('prefix', 'rp!')}")
        embed.add_field(name=await _(ctx, "Hide Inventories"), value=f"{settings.get('hideinv', False)}")
        embed.add_field(name=await _(ctx, "Wipe Userdata on Leave"), value=f"{settings.get('wipeonleave', False)}")
        time = settings.get('msgdel', 0)
        embed.add_field(name=await _(ctx, "Message Auto Delete Time"), value=f"{time if time is not 0 else 'Never'}")
        await ctx.send(embed=embed)

    @settings.command()
    async def iteminfo(self, ctx, *, item: str):
        """Get info on a server item"""
        items = await self.bot.di.get_guild_items(ctx.guild)
        item = items.get(item)
        if not item:
            await ctx.send(await _(ctx, "Item doesnt exist!"))
            return
        if hasattr(item, "description"):
            embed = discord.Embed(title=item.name, description=item.description, color=randint(0, 0xFFFFFF),)
        else:
            embed = discord.Embed(title=item.name, color=randint(0, 0xFFFFFF),)

        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.add_field(name=await _(ctx, "Name"), value=item.name)
        img = item.meta.get("image")
        embed.set_thumbnail(url=str(img)) if img else None
        for key, value in item.meta.items():
            if key == "image":
                continue
            embed.add_field(name=key, value=value)

        await ctx.send(embed=embed)

    @settings.command()
    async def items(self, ctx, letter: str = None):
        """See all items for a server"""
        items = await self.bot.di.get_guild_items(ctx.guild)

        if not items:
            await ctx.send(await _(ctx, "No items to display"))
            return

        words = dict()
        for x in sorted(items.keys()):
            if x[0].casefold() in words:
                words[x[0].casefold()].append(x)
            else:
                words[x[0].casefold()] = [x]

        desc = await _(ctx, "\u27A1 to see the next page"
                            "\n\u2B05 to go back"
                            "\n\u274C to exit")

        if letter is not None:
            if letter in words:
                words = {letter: words[letter]}
            else:
                await ctx.send(await _(ctx, "No entries found for that letter"))

        def lfmt(v):
            return "\n".join(v)

        await create_pages(ctx, list(words.items()), lfmt, description=desc, title=await _(ctx, "Server Items"),
                           author=ctx.guild.name, author_url=ctx.guild.icon_url,
                           thumbnail="https://mir-s3-cdn-cf.behance.net/project_modules/disp/196b9d18843737.562d0472d523f.png",
                           footer=str(ctx.message.created_at), chunk=4)

    @checks.mod_or_permissions()
    @settings.command()
    async def additem(self, ctx, *, name: str):
        """Add a custom item.
         Custom keys that can be used for special additions:
            `image` Setting this to a URL will give that item a special thumbnail when info is viewed for it
            `used` A message for when the item is used

        Henry: rp!settings additem Example
        RPGBot: Describe the item (a description for the item)
        Henry: This is an example item
        RPGBot: Additional information? (Attributes formatted in a list i.e color: 400, value: 200 Set an image for this item with the image key i.e. image: http://example.com/image.png Set this item as usable by adding used key i.e. used: You open the jar and the bird flies away
        Henry: used: You used this item!, image: http://www.sourcecertain.com/img/Example.png
        RPGBot:  Item successfully created

        Requires Bot Moderator or Bot Admin
            """
        try:
            item = dict()
            item["name"] = name
            check = lambda x: x.channel == ctx.channel and x.author == ctx.author
            await ctx.send(await _(ctx, "Describe the item (a description for the item)"))
            response = await self.bot.wait_for("message", timeout=120, check=check)
            if response.content.lower() == "cancel":
                await ctx.send(await _(ctx, "Cancelling!"))
                return

            item["description"] = response.content
            item["meta"] = dict()

            await ctx.send(
                await _(ctx, "Additional information? (Attributes formatted in a list i.e `color: 400, value: 200` "
                             "Set an image for this item with the `image` key i.e. `image: http://example.com/image.png` "
                             "Set this item as usable by adding `used` key i.e. `used: You open the jar and the bird flies away`"))
            while True:
                response = await self.bot.wait_for("message", timeout=60, check=check)
                if response.content.lower() == "cancel":
                    await ctx.send(await _(ctx, "Cancelling!"))
                    return
                elif response.content.lower() == "skip":
                    await ctx.send(await _(ctx, "Skipping!"))
                    break
                else:
                    try:
                        if "\n" in response.content:
                            res = response.content.split("\n")
                        else:
                            res = response.content.split(",")
                        for val in res:
                            key, value = val.split(": ")
                            key = key.strip().casefold()
                            value = value.strip()
                            item["meta"][key] = value
                        else:
                            break
                    except:
                        await ctx.send(await _(ctx, "Invalid syntax, try again."))
            await self.bot.di.new_item(ctx.guild, ServerItem(**item))
            await ctx.send(await _(ctx, "Item successfully created"))

        except asyncio.TimeoutError:
            await ctx.send(await _(ctx, "Timed out! Try again"))

    @checks.mod_or_permissions()
    @settings.command(aliases=["deleteitem"])
    async def removeitem(self, ctx, *, name: str):
        """Remove a custom item
        Requires Bot Moderator or Bot Admin"""
        try:
            await self.bot.di.remove_item(ctx.guild, name)
            await ctx.send((await _(ctx, "Successfully removed {}")).format(name))
        except KeyError:
            await ctx.send(await _(ctx, "That item doesn't exist"))

    @checks.mod_or_permissions()
    @commands.command()
    async def setstart(self, ctx, amount: NumberConverter):
        """Set the money start amount for a guild
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.set_start(ctx.guild, amount)
        await ctx.send((await _(ctx, "Starting amount changed to {} dollars")).format(amount))

    @commands.command()
    @checks.admin_or_permissions()
    async def language(self, ctx, language: str = None):
        """Set the guild language or check the language
        Requires Bot Moderator or Bot Admin"""
        if language is None:
            lang = await self.bot.di.get_language(ctx.guild)
            await ctx.send((await _(ctx, "The guild language is set to {}")).format(lang))
        else:
            if language not in self.bot.languages:
                await ctx.send(await _(ctx, "That is not a valid language!"))
                return
            await self.bot.di.set_language(ctx.guild, language)
            await ctx.send(await _(ctx, "Language successfully set!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def currency(self, ctx, currency: str):
        """Set the guild currency
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.set_currency(ctx.guild, currency)
        await ctx.send(await _(ctx, "Currency successfully set!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loaddnd(self, ctx):
        """This command will pre-load all D&D items and make them available to give
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.new_items(ctx.guild, (ServerItem(**item) for item in self.bot.dnditems.values()))
        await ctx.send(await _(ctx, "Successfully added all D&D items!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loadstarwars(self, ctx):
        """This command will pre-load all D&D items and make them available to give
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.new_items(ctx.guild, (ServerItem(**item) for item in self.bot.switems.values()))
        await ctx.send(await _(ctx, "Successfully added all Star Wars items!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loadstarwarsshop(self, ctx):
        """This command will pre-load all Star Wars items and make them available in shop
        Requires Bot Moderator or Bot Admin"""
        items = {}
        for item, value in self.bot.switems.items():
            try:
                items[item] = dict(buy=int("".join(filter(str.isdigit, value["meta"]["Cost"].split(" ")[0]))), sell=0, level=0)
            except:
                continue

        await self.bot.di.add_shop_items(ctx.guild, items)
        await ctx.send(await _(ctx, "Successfully added all Star Wars items to shop!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loaddndshop(self, ctx):
        """This command will pre-load all D&D items and make them available in shop
        Requires Bot Moderator or Bot Admin"""
        items = {}
        for item, value in self.bot.dnditems.items():
            try:
                items[item] = dict(buy=int("".join(filter(str.isdigit, value["meta"]["Cost"]))), sell=0, level=0)
            except:
                continue

        await self.bot.di.add_shop_items(ctx.guild, items)
        await ctx.send(await _(ctx, "Successfully added all D&D items to shop!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loadmagicshop(self, ctx):
        """This command will pre-load all D&D Magic items and make them available in shop
        Requires Bot Moderator or Bot Admin"""
        items = {}
        for item, value in self.bot.dndmagic.items():
            try:
                items[item] = dict(buy=int("".join(filter(str.isdigit, value["meta"]["Cost"]))), sell=0, level=0)
            except:
                continue

        await self.bot.di.add_shop_items(ctx.guild, items)
        await ctx.send(await _(ctx, "Successfully added all D&D magic items to shop!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loaddndmagic(self, ctx):
        """This command will pre-load all D&D Magic items and make them available to give
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.new_items(ctx.guild, (ServerItem(**item) for item in self.bot.dndmagic.values()))
        await ctx.send(await _(ctx, "Successfully added all D&D items!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loadpokemon(self, ctx):
        """This command will pre-load all Pokemon items and make them available to give
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.new_items(ctx.guild, (ServerItem(**item) for item in self.bot.pokemonitems.values()))
        await ctx.send(await _(ctx, "Successfully added all Pokemon items!"))

    @commands.command()
    @checks.admin_or_permissions()
    async def loaditems(self, ctx):
        """This command load all the items in the attached file.
        See an example file here: https://github.com/henry232323/RPGBot/blob/master/tutorial.md
        Requires Bot Moderator or Bot Admin"""
        items = []
        if not ctx.message.attachments:
            await ctx.send(await _(ctx, "This command needs to have a file attached!"))
            return

        attachment = ctx.message.attachments.pop()
        size = attachment.size
        if size > 2 ** 20:
            await ctx.send(await _(ctx, "This file is too large!"))
            return

        file = BytesIO()
        await attachment.save(file)
        file.seek(0)

        nfile = StringIO(file.getvalue().decode())
        nfile.seek(0)

        csv_reader = csv.DictReader(nfile)
        shop_items = {}

        for row in csv_reader:
            items.append(dict(
                name=row["name"],
                description=row.get("description", "No description."),
                meta={}
            ))
            if not row["name"]:
                await ctx.send(await _(ctx, "Error: There is an item with a missing name!"))
                return
            for k, v in row.items():
                if k not in ["name", "description", "buyprice", "sellprice"]:
                    if v:
                        items[-1]["meta"][k] = v

            if float(row.get("buyprice", 0)) or float(row.get("sellprice", 0)):
                shop_items[row["name"]] = dict(buy=float(row.get("buyprice", 0)), sell=float(row.get("sellprice", 0)), level=0)

        await self.bot.di.add_shop_items(ctx.guild, shop_items)
        await self.bot.di.new_items(ctx.guild, (ServerItem(**item) for item in items))
        await ctx.send(await _(ctx, "Successfully loaded all items!"))

    @commands.command()
    @checks.mod_or_permissions()
    async def deleteafter(self, ctx, time: int):
        """Set a time for messages to be automatically deleted after running in seconds. `rp!deleteafter 0` to make messages never be deleted
        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.set_delete_time(ctx.guild, time)
        await ctx.send(await _(ctx, "Updated settings"))

    @commands.command()
    @checks.mod_or_permissions()
    async def unload(self, ctx, name: str):
        """Unload Pokemon, D&D, D&D Magic, or Star Wars items. `rp!unload {name}` where name is either dnd, dndmagic, pokemon or starwars
        Requires Bot Moderator or Bot Admin"""
        if name == "dnd":
            items = self.bot.dnditems
        elif name == "dndmagic":
            items = self.bot.dndmagic
        elif name == "pokemon":
            items = self.bot.pokemonitems
        elif name == "starwars":
            items = self.bot.switems
        else:
            await ctx.send(await _(ctx, "That is not a valid input, look at `rp!help unload`"))
            return

        await self.bot.di.remove_items(ctx.guild, *items)
        await self.bot.di.remove_shop_items(ctx.guild, *items)
        await ctx.send((await _(ctx, "Successfully removed all {} items!")).format(name))

    @commands.command()
    @checks.admin_or_permissions()
    async def setdefaultmap(self, ctx, value: str):
        """Set the server's custom prefix. The default prefix will continue to work.
        Example:
            rp!setprefix ! --> !setprefix rp!

        Requires Bot Moderator or Bot Admin"""
        self.bot.di.set_default_map(ctx.guild, value)
        await ctx.send(await _(ctx, "Updated default map"))

    @commands.command()
    @checks.admin_or_permissions()
    async def setprefix(self, ctx, value: str):
        """Set the server's custom prefix. The default prefix will continue to work.
        Example:
            rp!setprefix ! --> !setprefix rp!

        Requires Bot Moderator or Bot Admin"""
        self.bot.prefixes[str(ctx.guild.id)] = value
        await ctx.send(await _(ctx, "Updated server prefix"))

    @commands.command()
    async def prefix(self, ctx):
        """View the current custom prefix for the server

        Requires Bot Moderator or Bot Admin"""
        prefix = self.bot.prefixes.get(str(ctx.guild.id))
        await ctx.send(prefix)

    @commands.command(disabled=True)
    @checks.admin_or_permissions()
    async def setcmdprefix(self, ctx, cmdpath: str, *, value: str):
        """Set a custom prefix for a command. The default prefix will continue to work.
        Example:
            Henry: rp!setcmdprefix rtd /
            Henry: /1d20
            RPGBot: Henry rolled Roll 9 ([9])

        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.set_cmd_prefixes(ctx.guild, cmdpath, value)
        await ctx.send(await _(ctx, "Updated command prefix"))

    @commands.command(disabled=True)
    async def prefixes(self, ctx):
        """View the current custom command prefixes for the server

        Requires Bot Moderator or Bot Admin"""
        prefixes = await self.bot.di.get_cmd_prefixes(ctx.guild)
        await ctx.send("\n".join(f"{k}: {v}" for k, v in prefixes.items()))

    @commands.command()
    @checks.admin_or_permissions()
    async def wipeonleave(self, ctx, value: str):
        """Set the server's setting for what to do when a player leaves. Set to true to wipe player data.
        Example:
            rp!setprefix ! --> !setprefix rp!

        Requires Bot Moderator or Bot Admin"""
        await self.bot.di.set_leave_setting(ctx.guild, value)
        await ctx.send(await _(ctx, "Updated server setting"))

    @commands.command()
    @checks.admin_or_permissions()
    async def hideinv(self, ctx, value: bool):
        """Set whether or not user inventories are hidden. If enabled, inventories will be sent via DMs.
        Requires Bot Moderator or Bot Admin"""
        gd = await self.bot.db.get_guild_data(ctx.guild)
        gd["hideinv"] = value
        await self.bot.db.update_guild_data(ctx.guild, gd)
        await ctx.send(await _(ctx, "Updated inventory setting"))

