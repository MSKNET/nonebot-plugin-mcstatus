import socket
import re
import requests
from typing import List, cast

from mcstatus import JavaServer, BedrockServer
from mcstatus.pinger import PingResponse

from .data import Data, Server
from .parser import Namespace


def query_players(server: Server, status: PingResponse) -> str:
    if server.server_type == "JE":
        if status.players.online > 0:
            try:
                players = JavaServer.lookup(server.address).query().players.names
            except:
                players = []
            if players:
                return f"\nPlayers list: {', '.join(players)}"
    return ""


def put_status(server: Server, status: PingResponse) -> str:
    def put_be(status):
        return (re.sub(r"(§.)", "", (
                f"Title: {status.motd}-{status.map}\n"
                + f"Version: {status.version.brand}{status.version.version}\n"
                + f"Players: {status.players_online}/{status.players_max}\n"
                + f"Gamemode: {status.gamemode}"
                )))

    def put_je(status):
        if '\n' in status.description:
            cut_title = (re.split(r'[\n]', status.description)[0]).strip()
            cut_dc = (''.join((re.split(r'[\n]', status.description))[1:])).strip()
            return (re.sub(r"(§.)", "", (
                f"Title: {cut_title}\n"
                + f"Description: {cut_dc}\n"
                + f"Version: {status.version.name}\n"
                + f"Players: {status.players.online}/{status.players.max}"
                + query_players(server, status)
            )))
        else:
            return (re.sub(r"(§.)", "", (
                f'Title: {status.description}\n'
                + f"Version: {status.version.name}\n"
                + f"Players: {status.players.online}/{status.players.max}"
                + query_players(server, status)
            )))

    return (
        put_je(status)
        if server.server_type == 'JE' else
        put_be(status)
    )


class Handle:
    @classmethod
    async def add(cls, args: Namespace) -> str:
        try:
            players = BedrockServer.lookup(args.address).status().players_online
            server_type = 'BE'
        except socket.gaierror:
            return "域名解析失败"
        except socket.timeout:
            try:
                players = JavaServer.lookup(args.address).status().players.online
                server_type = 'JE'
            except socket.timeout:
                return "未找到处于开放状态的BE/JE服务器"
            except Exception as e:
                return f"未知错误：{e}"
        except Exception as e:
            return f"未知错误：{e}"

        Data().add_server(
            Server(name=args.name,
                   address=args.address,
                   server_type=server_type,
                   online=True,
                   players=players,
                   retry=0),
            args.user_id,
            args.group_id,
        )

        return f"添加{server_type}服务器成功！"

    @classmethod
    async def remove(cls, args: Namespace) -> str:
        Data().remove_server(args.name, args.user_id, args.group_id)

        return "移除服务器成功！"

    @classmethod
    async def list(cls, args: Namespace) -> str:
        server_list = Data().get_server_list(args.user_id, args.group_id)

        if server_list:
            return "本群关注服务器列表如下：\n" + "\n".join(
                f"[{'o' if server.online else 'x'}]{server.server_type} {server.name} ({server.address})"
                for server in cast(List[Server], server_list)
            )
        else:
            return "本群关注服务器列表为空！"

    @classmethod
    async def check(cls, args: Namespace) -> str:
        try:
            server_list = Data().get_server_list(args.user_id, args.group_id)

            if args.name not in (s.name for s in server_list):
                return "没有找到对应该名称的已记录服务器"

            server = next(s for s in server_list if s.name == args.name)
            try:
                status = (
                    JavaServer.lookup(server.address).status()
                    if server.server_type == 'JE' else
                    BedrockServer.lookup(server.address).status()
                )
            except socket.timeout:
                return "获取服务器状态超时"

            return put_status(server, status)

        except Exception as e:
            return f"未知错误：{e}"

    @classmethod
    async def checkapi(cls, args: Namespace) -> str:
        try:
            server_list = Data().get_server_list(args.user_id, args.group_id)

            if args.name not in (s.name for s in server_list):
                return "没有找到对应该名称的已记录服务器"

            server = next(s for s in server_list if s.name == args.name)
            api_url = "https://api.mcsrvstat.us/2/" if server.server_type == 'JE' else "https://api.mcsrvstat.us/bedrock/2/"
            resp = requests.get(api_url + server.address)
            if resp.status_code != 200:
                return f"{server.address} ({server.description}) 获取信息失败（{resp.status_code}）。"
            json_data = resp.json()
            if not json_data["online"]:
                return f"{server.address} ({server.description}) 当前不在线。"
            elif json_data['players']['online'] == 0:
                return f"{server.address} ({server.description}) 当前没有玩家在线。"
            else:
                return f"{server.address} ({server.description}) 在线玩家： {', '.join(json_data['players']['list'])}。"

        except Exception as e:
            return f"未知错误：{e}"
