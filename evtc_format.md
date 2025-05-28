### **EVTC File Format Overview**

The EVTC file format is a binary format that stores structured data about combat encounters in Guild Wars 2. It is designed to be compact and efficient, enabling tools like **arcdps** (a combat logging plugin) to generate logs that can be parsed for performance analysis, such as by tools like **Elite Insights**. The file is divided into several sections:

1. **Header**: Contains metadata about the file, such as the file identifier, version, and revision.
2. **Agents**: Lists entities (players, NPCs, gadgets, etc.) involved in the encounter, including their attributes like profession, name, and team.
3. **Skills**: Records skills used during the encounter, identified by a skill ID and name.
4. **Events**: A sequence of combat events (e.g., damage, healing, buff applications) with detailed attributes like source, destination, and timestamps.

Each section uses fixed-size binary structures defined using Python's `struct` module, ensuring precise parsing of the binary data.

#### **Header Structure**
- **Format**: `<4s8sBHB` (4-byte string, 8-byte string, unsigned byte, unsigned short, unsigned byte)
- **Fields**:
  - `magic` (4 bytes): Must be `b'EVTC'` to identify a valid EVTC file.
  - `version` (8 bytes): Version string (e.g., `b'EVTC20250525'`), null-terminated.
  - `instruction_set_id` (1 byte): Likely indicates the architecture or instruction set.
  - `revision` (2 bytes): File format revision number.
  - `padding` (1 byte): Unused, aligns the header to 16 bytes.
- **Purpose**: Validates the file and provides versioning information for compatibility.

#### **Agent Structure**
- **Format**: `<QIIHHHHHH64s4x` (unsigned long long, unsigned int, unsigned int, 4 unsigned shorts, unsigned short, unsigned short, 64-byte string, 4-byte padding)
- **Size**: 96 bytes (calculated by `struct.calcsize(AGENT_STRUCT)`).
- **Fields**:
  - `address` (8 bytes): Unique identifier for the agent (e.g., memory address or instance ID).
  - `profession` (4 bytes): Profession ID (maps to `PROFESSION_NAMES` like Guardian, Warrior, etc.).
  - `is_elite` (4 bytes): Indicates elite specialization (0 for core profession, specific values for elite specs, or `4294967295` for non-player entities).
  - `toughness`, `healing`, `condition`, `concentration` (2 bytes each): Combat attributes (e.g., toughness, healing power).
  - `hitbox_width`, `hitbox_height` (2 bytes each): Physical dimensions of the agent (likely for collision detection).
  - `name` (64 bytes): Null-terminated string containing the agent’s name, account, or subgroup (e.g., `CharacterName\x00AccountName\x00Subgroup` for players).
  - `padding` (4 bytes): Aligns the structure.
- **Purpose**: Describes all entities in the encounter, including players, NPCs, and objects.

#### **Skill Structure**
- **Format**: `<i64s` (signed int, 64-byte string).
- **Size**: 68 bytes.
- **Fields**:
  - `skill_id` (4 bytes): Unique identifier for a skill.
  - `name` (64 bytes): Null-terminated string of the skill’s name.
- **Purpose**: Catalogues skills used in the encounter for reference in event data.

#### **Event Structure**
- **Format**: `<qQQiiIIHHHHBBBBBBBBBBBBI` (signed long long, 2 unsigned long longs, 2 signed ints, 2 unsigned ints, 4 unsigned shorts, 12 unsigned bytes, unsigned int).
- **Size**: 48 bytes.
- **Fields**:
  - `time` (8 bytes): Timestamp of the event (in milliseconds since encounter start).
  - `src_agent`, `dst_agent` (8 bytes each): Source and destination agent addresses.
  - `value`, `buff_dmg` (4 bytes each): Primary and buff-related damage/healing values.
  - `overstack_value` (4 bytes): Additional value for buff stacking mechanics.
  - `skill_id` (4 bytes): ID of the skill associated with the event.
  - `src_instid`, `dst_instid` (2 bytes each): Instance IDs for source and destination agents.
  - `src_master_instid`, `dst_master_instid` (2 bytes each): Master instance IDs (e.g., for pets or minions).
  - `iff` (1 byte): Indicates if the event involves friend (1), foe (2), or unknown (0).
  - `buff` (1 byte): Indicates if the event is a buff-related action (0 or 1).
  - `result` (1 byte): Outcome of the event (e.g., hit, miss, block).
  - `is_activation`, `is_buffremove`, `is_ninety`, `is_fifty`, `is_moving`, `is_statechange`, `is_flanking`, `is_shields`, `is_offcycle` (1 byte each): Flags for specific event conditions (e.g., activation, movement, flanking).
  - `pad` (4 bytes): Padding for alignment.
- **Purpose**: Records individual actions (damage, healing, buff applications, state changes) with detailed context.

---
