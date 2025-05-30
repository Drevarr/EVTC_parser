import struct
import sys
import traceback
from typing import List, Dict, NamedTuple, Tuple
from collections import defaultdict
from dataclasses import dataclass

AGENT_STRUCT = '<QIIHHHHHH64s4x'  # Q: uint64, I: uint32, H: uint16, 64s: char[64]
AGENT_SIZE = struct.calcsize(AGENT_STRUCT)

EVENT_STRUCT = '<qQQiiIIHHHHBBBBBBBBBBBBI'
EVENT_SIZE = struct.calcsize(EVENT_STRUCT)

@dataclass
class EvtcHeader:
    magic: str
    version: str
    instruction_set_id: int
    revision: int

@dataclass
class EvtcAgent:
    address: int
    profession: int
    is_elite: int
    toughness: int
    healing: int
    condition: int
    concentration: int
    name: str
    party: int
    team: str
    instid: int

@dataclass
class EvtcSkill:
    skill_id: int
    name: str

@dataclass
class EvtcEvent:
    time: int
    src_agent: int
    dst_agent: int
    value: int
    buff_dmg: int
    overstack_value: int
    skill_id: int
    src_instid: int
    dst_instid: int
    src_master_instid: int
    dst_master_instid: int
    iff: int
    buff: int
    result: int
    is_activation: int
    is_buffremove: int
    is_ninety: int
    is_fifty: int
    is_moving: int
    is_statechange: int
    is_flanking: int
    is_shields: int
    is_offcycle: int
    pad: int

def parse_evtc(file_path: str) -> Tuple[EvtcHeader, List[EvtcAgent], List[EvtcSkill], List[EvtcEvent]]:
    """
    Parse an EVTC binary log file and return its components.
    (Same as previous implementation, included for completeness)
    """
    try:
        with open(file_path, 'rb') as f:
            header_data = f.read(16)
            if len(header_data) < 16:
                raise EOFError("File too short to contain a valid header")
            
            magic, version, instruction_set_id, revision, padding = struct.unpack('<4s8sBHB', header_data)
            if magic[:4] != b'EVTC':
                raise ValueError(f"Invalid EVTC file: magic number is {magic!r}, expected 'EVTC'")
            header = EvtcHeader(
                magic=magic.decode('utf8'),
                version=version.decode('utf8').rstrip('\x00'),
                instruction_set_id=instruction_set_id,
                revision=revision
            )
            #print(f"Header parsed: version={version}, revision={revision}, instruction_set_id={instruction_set_id}")
            agent_count_data = f.read(4)
            if len(agent_count_data) < 4:
                raise EOFError("Unexpected EOF while reading agent count")
            agent_count = struct.unpack('<I', agent_count_data)[0]
            
            agents = []
            for _ in range(agent_count):
                agent_data = f.read(AGENT_SIZE)
                if len(agent_data) < AGENT_SIZE:
                    raise EOFError("Unexpected EOF while reading agent data")
                
                addr, prof, is_elite, toughness, concentration, healing, hitbox_width, condition, hitbox_height, name = struct.unpack(AGENT_STRUCT, agent_data)
                name = name.decode('utf-8').rstrip('\x00')
                if "." in name:
                    party = name[-1]
                else:
                    party = 0
                agents.append(EvtcAgent(
                    address=addr,
                    profession=prof,
                    is_elite=is_elite,
                    toughness=toughness,
                    healing=healing,
                    condition=condition,
                    concentration=concentration,
                    name=name,
                    party=party,
                    team="",
                    instid = 0

                ))

            skill_count_data = f.read(4)
            if len(skill_count_data) < 4:
                raise EOFError("Unexpected EOF while reading skill count")
            skill_count = struct.unpack('<I', skill_count_data)[0]
            
            skills = []
            for _ in range(skill_count):
                skill_data = f.read(68)
                if len(skill_data) < 68:
                    raise EOFError("Unexpected EOF while reading skill data")
                
                skill_id, name = struct.unpack('<i64s', skill_data)
                name = name.decode('utf-8').rstrip('\x00')
                skills.append(EvtcSkill(skill_id=skill_id, name=name))

            events = []
            while True:
                event_data = f.read(EVENT_SIZE)
                if not event_data:
                    break
                if len(event_data) < EVENT_SIZE:
                    raise EOFError("Unexpected EOF while reading event data")
                
                time, src_agent, dst_agent, value, buff_dmg, overstack_value, skill_id, \
                src_instid, dst_instid, src_master_instid, dst_master_instid, \
                iff, buff, result, is_activation, is_buffremove, is_ninety, is_fifty, \
                is_moving, is_statechange, is_flanking, is_shields, is_offcycle, \
                padding = struct.unpack(EVENT_STRUCT, event_data)
                
                events.append(EvtcEvent(
                    time=time,
                    src_agent=src_agent,
                    dst_agent=dst_agent,
                    value=value,
                    buff_dmg=buff_dmg,
                    overstack_value=overstack_value,
                    skill_id=skill_id,
                    src_instid=src_instid,
                    dst_instid=dst_instid,
                    src_master_instid=src_master_instid,
                    dst_master_instid=dst_master_instid,
                    iff=iff,
                    buff=buff,
                    result=result,
                    is_activation=is_activation,
                    is_buffremove=is_buffremove,
                    is_ninety=is_ninety,
                    is_fifty=is_fifty,
                    is_moving=is_moving,
                    is_statechange=is_statechange,
                    is_flanking=is_flanking,
                    is_shields=is_shields,
                    is_offcycle=is_offcycle,
                    pad =padding
                ))

            return header, agents, skills, events

    except FileNotFoundError:
        raise FileNotFoundError(f"EVTC file not found: {file_path}")
    except struct.error as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        line_number = traceback.extract_tb(exc_traceback)[-1][1]
        print(f"Struct error at line {line_number}: {e}")
        raise ValueError(f"Error parsing EVTC file: {str(e)}")