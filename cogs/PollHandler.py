#!/usr/bin/env python
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
import cogs.colourEmbed as functions
import traceback
import sqlite3
import datetime
import discord

conn = sqlite3.connect('bot.db', timeout=5.0)
c = conn.cursor()
conn.row_factory = sqlite3.Row

c.execute(
    '''CREATE TABLE IF NOT EXISTS pollProperties (
    `pollID` INT PRIMARY KEY, 
    `pollTopic` TEXT,
    `pollRole` INT,
    `roleName` TEXT,
    `serverID` INT,
    `pollChannelID` INT,
    `resultChannelID` INT,
    `resultMessageID` INT,
    `pollStartTime` INT,
    `pollEndTime` INT,
    `pollStarted` INT,
    UNIQUE(pollTopic)
    ) ''')

c.execute(
    '''CREATE TABLE IF NOT EXISTS winnerList (
    `pollID` INT, 
    `pollWinnerID` INT,
    `winnerName` INT,
    `winDate` TEXT
    ) ''')

c.execute(
    '''CREATE TABLE IF NOT EXISTS pollMessages (
    `pollID` INT, 
    `pollMessageID` INT,
    `userID` INT,
    `reactNumber` INT
    ) ''')


class Poll:
    def __init__(self, name):
        self.Info = [r for r in c.execute('SELECT * FROM pollProperties WHERE pollTopic = ? ', (name,))][0] \
            if [r for r in c.execute('SELECT * FROM pollProperties WHERE pollTopic = ? ', (name,))] else None
        self.ID = self.Info[0] if self.Info else None
        self.Topic = self.Info[1] if self.Info else None
        self.Role = self.Info[2] if self.Info else None
        self.Reward = self.Info[3] if self.Info else None
        self.ServerID = self.Info[4] if self.Info else None
        self.PollChannel = self.Info[5] if self.Info else None
        self.ResultChannel = self.Info[6] if self.Info else None
        self.MessageID = self.Info[7] if self.Info else None
        self.StartTimestamp = self.Info[8] if self.Info else None
        self.EndTimestamp = self.Info[9] if self.Info else None
        self.PollStarted = self.Info[10] if self.Info else None
        self.Count = [r[0] for r in c.execute('SELECT COUNT(*) FROM pollProperties WHERE pollTopic = ? ', (name,))][0]

    def List(self, ID):
        ListCount = [r for r in c.execute('SELECT COUNT(*) FROM winnerList WHERE pollID = ? ', (ID,))]

        if not ListCount:
            return False

        return [r for r in
                c.execute('SELECT pollWinnerID, winnerName, winDate FROM winnerList WHERE pollID = ? ', (ID,))]

    def Messages(self, ID):
        ListCount = [r for r in c.execute('SELECT COUNT(*) FROM pollMessages WHERE pollID = ? ', (ID,))]

        if not ListCount:
            return False

        return [r for r in
                c.execute('SELECT pollMessageID, userID, reactNumber FROM pollMessages WHERE pollID = ? ', (ID,))]


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


class Polling(commands.Cog, name="📩  Poll"):
    def __init__(self, bot):
        self.bot = bot
        self.pollHandler.start()
        self.resultHandler.start()

    @tasks.loop(seconds=20.0)
    async def pollHandler(self):

        startInterval = datetime.datetime.now().replace(day=20, hour=0, minute=0, second=0, microsecond=0)
        endInterval = datetime.datetime.now().replace(day=21, hour=0, minute=0, second=0, microsecond=0)
        now = datetime.datetime.now()
        pollList = [i for i in c.execute('SELECT * FROM pollProperties')]

        if not endInterval > now > startInterval:
            return

        for id, topic, role, name, serverID, channelID, resultID, messageID, startTime, endTime, pollStarted in pollList:
            if pollStarted:
                continue

            c.execute('UPDATE pollProperties SET pollStarted = ? WHERE pollID = ? ', (1, id))
            conn.commit()

            channelObject = self.bot.get_channel(channelID)
            guildObject = self.bot.get_guild(serverID)

            memberList = [member for member in guildObject.members if not member.bot]

            chunkedMemberList = list(chunks([i for i in memberList], 10))
            emoteList = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯']

            for page in chunkedMemberList:
                description = "Please vote for the members below. You can only vote for one person per topic.\n\n"

                for idx, m in enumerate(page):
                    description += f"{emoteList[idx]} {m}\n"

                embed = discord.Embed(title=topic, description=description)
                msg = await channelObject.send(embed=embed)

                for idx, m in enumerate(page):
                    await msg.add_reaction(emoteList[idx])
                    c.execute('INSERT INTO pollMessages VALUES (?, ?, ?, ?) ',
                              (id, msg.id, page[idx].id, emoteList[idx]))
                    conn.commit()

    @tasks.loop(seconds=20.0)
    async def resultHandler(self):

        startInterval = datetime.datetime.now().replace(day=2, hour=0, minute=0, second=0, microsecond=0)
        endInterval = datetime.datetime.now().replace(day=3, hour=0, minute=0, second=0, microsecond=0)
        now = datetime.datetime.now()
        pollList = [i for i in c.execute('SELECT * FROM pollProperties')]

        if not endInterval > now > startInterval:
            return

        for id, topic, role, name, serverID, channelID, resultID, messageID, startTime, endTime, pollStarted in pollList:
            if not pollStarted:
                continue

            channelObject = self.bot.get_channel(channelID)
            resultObject = self.bot.get_channel(resultID)
            guildObject = self.bot.get_guild(serverID)
            resultMsgObject = await resultObject.fetch_message(messageID)
            roleObject = guildObject.get_role(role_id=role)

            c.execute('UPDATE pollProperties SET pollStarted = ? WHERE pollID = ? ', (0, id))
            conn.commit()

            pageList = [i for i in c.execute('SELECT * FROM pollMessages WHERE pollID = ? ', (id,))]
            resultList = []

            for pollID, msgID, userID, react in pageList:
                messageObject = await channelObject.fetch_message(msgID)
                for reaction in messageObject.reactions:
                    if str(reaction.emoji) == str(react):
                        users = await reaction.users().flatten()
                        votes = len(users)
                        resultList.append([userID, votes])

            c.execute('DELETE FROM pollMessages WHERE pollID = ? ', (id,))
            conn.commit()
            winner = max(resultList, key=lambda x: x[1])[0]
            memberObject = guildObject.get_member(winner)

            year = now.year
            month = now.month
            await roleObject.edit(name=f"{name} ({month}/{year})")

            for member in guildObject.members:
                if roleObject in member.roles:
                    await member.remove_roles(roleObject)
            await memberObject.add_roles(roleObject)

            winnerList = [i for i in c.execute('SELECT * FROM winnerList WHERE pollID = ? ', (id,))]

            description = ""

            for pollID, winnerID, winnerName, winDate in winnerList:
                member = guildObject.get_member(winnerID)

                if member:
                    description += f"{winDate}: {member.mention}\n"
                else:
                    description += f"{winDate}: {winnerName}\n"

            embed = discord.Embed(title=f"{topic} Winners", description=description)
            await resultMsgObject.edit(embed=embed)

            c.execute('INSERT INTO winnerList VALUES (?, ?, ?, ?) ',
                      (id, memberObject.id, f"{memberObject}", f"{month}/{year}"))
            conn.commit()

            embed = discord.Embed(title=f'Monthly Winner Of {topic}',
                                  description=f"Congratulations! {memberObject.mention} has won this month's {roleObject.mention}")
            await resultObject.send(embed=embed)

    @resultHandler.before_loop
    async def before_result(self):
        print('Waiting to update results...')
        await self.bot.wait_until_ready()

    @pollHandler.before_loop
    async def before_poll(self):
        print('Waiting to update polls...')
        await self.bot.wait_until_ready()

    @commands.command(description=f"winnerlist [Poll Topic]**\n\nShows the winner list of a topic. Administrator Only.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @has_permissions(administrator=True)
    async def winnerlist(self, ctx, *, pollTopic):

        PollObject = Poll(pollTopic)

        if not PollObject.Count:
            return await functions.errorEmbedTemplate(ctx, f"The topic does not exist.", ctx.author)

        winnerList = [i for i in c.execute('SELECT * FROM winnerList WHERE pollID = ? ', (PollObject.ID,))]
        description = ""

        for pollID, winnerID, winnerName, winDate in winnerList:
            member = ctx.guild.get_member(winnerID)

            if member:
                description += f"{winDate}: {member.mention}\n"
            else:
                description += f"{winDate}: {winnerName}\n"

        embed = discord.Embed(title=f"{PollObject.Topic} Winners", description=description)
        await ctx.send(embed=embed)

    @commands.command(description=f"editpolltopic**\n\nEdits an existing poll. Administrator Only.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @has_permissions(administrator=True)
    async def editpolltopic(self, ctx):

        def check(m):
            return m.channel == ctx.message.channel and m.author == ctx.message.author

        await ctx.send("Please enter the topic name of the poll you would like to edit.")

        nameMessage = await self.bot.wait_for('message', check=check, timeout=60)
        PollObject = Poll(nameMessage.content)

        if not PollObject.Count:
            return await functions.errorEmbedTemplate(ctx, f"The topic does not exist.",
                                                      ctx.author)

        await ctx.send(f"Your selected topic is **{nameMessage.content}**.")
        await ctx.send("Please enter the topic name of the poll you would like to change to.")

        newNameMessage = await self.bot.wait_for('message', check=check, timeout=60)
        PollObject = Poll(newNameMessage.content)

        if PollObject.Count:
            return await functions.errorEmbedTemplate(ctx, f"The topic you're trying to change to already exists. "
                                                           f"Please restart the command.",
                                                      ctx.author)

        await ctx.send(f"Your new topic name is **{newNameMessage.content}**.")
        await ctx.send("Please enter the new name of the role reward you would like awarded to the winner.")
        roleMessage = await self.bot.wait_for('message', check=check, timeout=60)

        await ctx.send(f"Your role reward name is **{roleMessage.content}**.")
        await ctx.send("Please mention the channel you want the poll to be held in.")
        channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
        channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')

        while True:
            try:
                channelObject = self.bot.get_channel(int(channelID))

                if not channelObject:
                    await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                    channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
                    channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')
                    continue
                break
            except ValueError:
                await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
                channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')
                continue

        await ctx.send("Please mention the channel you want the result message to be in.")
        resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
        resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')

        while True:
            try:
                resultObject = self.bot.get_channel(int(resultID))

                if not resultObject:
                    await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                    resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
                    resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')
                    continue
                break
            except ValueError:
                await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
                resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')
                continue

        startDate = (datetime.datetime.now().replace(day=1) + datetime.timedelta(days=32)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        endDate = startDate + datetime.timedelta(days=1)
        year = startDate.year
        month = startDate.month

        embed = discord.Embed(title="Updating Poll..", description="Please react below to confirm.")
        embed.add_field(name="Poll Topic", value=newNameMessage.content)
        embed.add_field(name="Role Reward", value=roleMessage.content)
        embed.add_field(name="Poll Channel", value=channelMessage.content)
        embed.add_field(name="Result Channel", value=resultMessage.content)
        embed.add_field(name="Poll Start Time", value=startDate.strftime('%d %b %Y %H:%M:%S'))
        embed.add_field(name="Poll End Time", value=endDate.strftime('%d %b %Y %H:%M:%S'))
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("☑")
        await msg.add_reaction("❌")

        def confirmationCheck(reaction, user):
            return str(reaction.emoji) in ['☑',
                                           '❌'] and user == ctx.message.author and reaction.message.id == msg.id

        reaction, user = await self.bot.wait_for('reaction_add',
                                                 check=confirmationCheck,
                                                 timeout=120)

        if str(reaction.emoji) == "❌":
            await functions.requestEmbedTemplate(ctx, "Poll update cancelled.", ctx.message.author)

        elif str(reaction.emoji) == "☑":

            PollObject = Poll(nameMessage.content)
            roleObject = ctx.guild.get_role(role_id=PollObject.Role)
            await roleObject.edit(name=f"{roleMessage.content} ({month}/{year})")

            embed = discord.Embed(title=nameMessage.content)
            msg = await resultObject.send(embed=embed)

            c.execute(
                'UPDATE pollProperties SET pollTopic = ?, roleName = ?, pollChannelID = ?, resultChannelID = ?, resultMessageID = ?'
                'WHERE pollID = ? ',
                (newNameMessage.content, roleMessage.content, int(channelID), int(resultID), msg.id, PollObject.ID))
            conn.commit()

            await functions.successEmbedTemplate(ctx, "Poll update successful!", ctx.message.author)

    @commands.command(description=f"createpolltopic**\n\nCreates a poll. Administrator Only.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @has_permissions(administrator=True)
    async def createpolltopic(self, ctx):

        await ctx.send(
            "Please enter the topic name of the poll you would like to create. Duplicate names are not allowed.")

        def check(m):
            return m.channel == ctx.message.channel and m.author == ctx.message.author

        nameMessage = await self.bot.wait_for('message', check=check, timeout=60)
        PollObject = Poll(nameMessage.content)

        print(PollObject.Count)
        if PollObject.Count:
            return await functions.errorEmbedTemplate(ctx, f"The topic already exists.",
                                                      ctx.author)

        await ctx.send(f"Your topic is **{nameMessage.content}**.")
        await ctx.send("Please enter the name of the role reward you would like awarded to the winner.")

        roleMessage = await self.bot.wait_for('message', check=check, timeout=60)

        await ctx.send(f"Your role reward name is **{roleMessage.content}**.")
        await ctx.send("Please mention the channel you want the poll to be held in.")
        channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
        channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')

        while True:
            try:
                channelObject = self.bot.get_channel(int(channelID))

                if not channelObject:
                    await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                    channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
                    channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')
                    continue
                break
            except ValueError:
                await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                channelMessage = await self.bot.wait_for('message', check=check, timeout=60)
                channelID = channelMessage.content.replace('<', '').replace('>', '').replace('#', '')
                continue

        await ctx.send("Please mention the channel you want the result message to be in.")
        resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
        resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')

        while True:
            try:
                resultObject = self.bot.get_channel(int(resultID))

                if not resultObject:
                    await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                    resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
                    resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')
                    continue
                break
            except ValueError:
                await ctx.send("Invalid input. Please make sure you're mentioning a text channel that exists!")
                resultMessage = await self.bot.wait_for('message', check=check, timeout=60)
                resultID = resultMessage.content.replace('<', '').replace('>', '').replace('#', '')
                continue

        startDate = (datetime.datetime.now().replace(day=1) + datetime.timedelta(days=32)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        endDate = startDate + datetime.timedelta(days=1)
        year = startDate.year
        month = startDate.month

        embed = discord.Embed(title="Creating Poll..", description="Please react below to confirm.")
        embed.add_field(name="Poll Topic", value=nameMessage.content)
        embed.add_field(name="Role Reward", value=roleMessage.content)
        embed.add_field(name="Poll Channel", value=channelMessage.content)
        embed.add_field(name="Result Channel", value=resultMessage.content)
        embed.add_field(name="Poll Start Time", value=startDate.strftime('%d %b %Y %H:%M:%S'))
        embed.add_field(name="Poll End Time", value=endDate.strftime('%d %b %Y %H:%M:%S'))
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("☑")
        await msg.add_reaction("❌")

        def confirmationCheck(reaction, user):
            return str(reaction.emoji) in ['☑',
                                           '❌'] and user == ctx.message.author and reaction.message.id == msg.id

        reaction, user = await self.bot.wait_for('reaction_add',
                                                 check=confirmationCheck,
                                                 timeout=120)

        if str(reaction.emoji) == "❌":
            await functions.requestEmbedTemplate(ctx, "Poll creation cancelled.", ctx.message.author)

        elif str(reaction.emoji) == "☑":
            roleObject = await ctx.guild.create_role(name=f"{roleMessage.content} ({month}/{year})")
            embed = discord.Embed(title=f"{nameMessage.content} Winners")
            msg = await resultObject.send(embed=embed)
            i = 1

            while True:
                try:
                    c.execute('INSERT INTO pollProperties VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ',
                              (i, nameMessage.content, roleObject.id, roleMessage.content,
                               ctx.guild.id, int(channelID), int(resultID), msg.id,
                               startDate.timestamp(), endDate.timestamp(), 0))
                    conn.commit()

                except sqlite3.IntegrityError:
                    i += 1
                    continue

            await functions.successEmbedTemplate(ctx, "Poll creation successful!", ctx.message.author)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        if payload.member.bot:
            return

        pollList = [i[0] for i in c.execute('SELECT pollMessageID FROM pollMessages')]

        if payload.message_id in pollList:
            pollID = [i[0] for i in c.execute('SELECT pollID FROM pollMessages WHERE pollMessageID = ? ', (payload.message_id, ))][0]
            messageList = list(set([i[0] for i in c.execute('SELECT pollMessageID FROM pollMessages WHERE pollID = ? ', (pollID, ))]))

            userVote = []
            for messageID in messageList:
                channel = self.bot.get_channel(payload.channel_id)
                payloadMessage = await channel.fetch_message(payload.message_id)
                messageObject = await channel.fetch_message(messageID)

                for reaction in messageObject.reactions:
                    users = await reaction.users().flatten()
                    for user in users:
                        if user.id == payload.member.id:
                            userVote.append([payloadMessage, payload.emoji, user])

            if len(userVote) > 1:
                userVote.pop(0)
                for payloadMessage, payloadEmoji, user in userVote:
                    await payloadMessage.remove_reaction(payloadEmoji, user)

                    try:
                        await payload.member.send("You can only vote for one person!")
                    except:
                        pass





def setup(bot):
    bot.add_cog(Polling(bot))
