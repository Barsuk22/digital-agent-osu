from __future__ import annotations

from src.skills.minecraft.config import MinecraftRuntimeConfig
from src.skills.minecraft.env.connector import MinecraftConnector, NullMinecraftConnector
from src.skills.minecraft.env.tcp_connector import TcpMinecraftConnector


def make_minecraft_connector(config: MinecraftRuntimeConfig) -> MinecraftConnector:
    if config.connector == "null":
        return NullMinecraftConnector()
    if config.connector == "tcp":
        return TcpMinecraftConnector(config.bridge)
    raise ValueError(f"Unknown Minecraft connector: {config.connector}")
