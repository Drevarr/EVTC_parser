from enum import Enum

class CbtStateChange(Enum):
    """State change events ported from arcdps enum cbtstatechange"""

    NONE = 0
    """Not used - not this kind of event"""

    ENTERCOMBAT = 1
    """Agent entered combat."""

    EXITCOMBAT = 2
    """Agent left combat."""

    CHANGEUP = 3
    """Agent is alive at time of event."""

    CHANGEDEAD = 4
    """Agent is dead at time of event."""

    CHANGEDOWN = 5
    """Agent is down at time of event."""

    SPAWN = 6
    """Agent entered tracking."""

    DESPAWN = 7
    """Agent left tracking."""

    HEALTHPCTUPDATE = 8
    """Agent health percentage changed."""

    SQCOMBATSTART = 9
    """Squad combat start, first player enters combat."""

    SQCOMBATEND = 10
    """Squad combat stop, last player left combat."""

    WEAPSWAP = 11
    """Agent weapon set changed."""

    MAXHEALTHUPDATE = 12
    """Agent maximum health changed."""

    POINTOFVIEW = 13
    """'Recording' player."""

    LANGUAGE = 14
    """Text language id."""

    GWBUILD = 15
    """Game build."""

    SHARDID = 16
    """Server shard id."""

    REWARD = 17
    """Wiggly box reward."""

    BUFFINITIAL = 18
    """Buff already existing at event time."""

    POSITION = 19
    """Agent position changed."""

    VELOCITY = 20
    """Agent velocity changed."""

    FACING = 21
    """Agent facing direction changed."""

    TEAMCHANGE = 22
    """Agent team id changed."""

    ATTACKTARGET = 23
    """Attacktarget to gadget association."""

    TARGETABLE = 24
    """Agent targetable state changed."""

    MAPID = 25
    """Map id."""

    REPLINFO = 26
    """Internal use only."""

    STACKACTIVE = 27
    """Buff instance is now active."""

    STACKRESET = 28
    """Buff instance duration changed / reset."""

    GUILD = 29
    """Agent is a member of a guild."""

    BUFFINFO = 30
    """Buff information."""

    BUFFFORMULA = 31
    """Buff formula information."""

    SKILLINFO = 32
    """Skill information."""

    SKILLTIMING = 33
    """Skill timing information."""

    BREAKBARSTATE = 34
    """Agent breakbar state changed."""

    BREAKBARPERCENT = 35
    """Agent breakbar percentage changed."""

    INTEGRITY = 36
    """Error/integrity message."""

    MARKER = 37
    """Marker on agent."""

    BARRIERPCTUPDATE = 38
    """Agent barrier percentage changed."""

    STATRESET = 39
    """arcdps stats reset."""

    EXTENSION = 40
    """Extension use only."""

    APIDELAYED = 41
    """Non-realtime-safe cbtevent posted later."""

    INSTANCESTART = 42
    """Map instance start."""

    RATEHEALTH = 43
    """Tick health / tickrate."""

    LAST90BEFOREDOWN = 44
    """Retired, not used since 240529+."""

    EFFECT = 45
    """Retired, not used since 230716+."""

    IDTOGUID = 46
    """Content id to guid association."""

    LOGNPCUPDATE = 47
    """Log boss agent changed."""

    IDLEEVENT = 48
    """Internal use only."""

    EXTENSIONCOMBAT = 49
    """Extension use, cbtevent struct interpreted."""

    FRACTALSCALE = 50
    """Fractal scale (for fractals)."""

    EFFECT2_DEFUNC = 51
    """Retired, not used since 250526+."""

    RULESET = 52
    """Ruleset flags (pve, wvw, pvp)."""

    SQUADMARKER = 53
    """Squad ground markers."""

    ARCBUILD = 54
    """Arc build info."""

    GLIDER = 55
    """Glider status change."""

    STUNBREAK = 56
    """Disable stopped early."""

    MISSILECREATE = 57
    """Missile created."""

    MISSILELAUNCH = 58
    """Missile launched."""

    MISSILEREMOVE = 59
    """Missile removed."""

    EFFECTGROUNDCREATE = 60
    """Effect played on ground."""

    EFFECTGROUNDREMOVE = 61
    """Effect stopped on ground."""

    EFFECTAGENTCREATE = 62
    """Effect played around agent."""

    EFFECTAGENTREMOVE = 63
    """Effect stopped around agent."""

    IIDCHANGE = 64
    """IID changed (players only, after spawn)."""

    MAPCHANGE = 65
    """Map changed."""

    UNKNOWN = 66
    """Unknown/unsupported type (newer than this list)."""
