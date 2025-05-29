import parser
import datetime
import os
import requests
import sys
import tempfile
import time
import zipfile
from typing import List, Dict, NamedTuple, Tuple
from urllib.parse import urlparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

ARCDPS_LOG_DIR = "d:\\test\\"
LOG_DELAY = 2
WEBHOOK_URL = ""  # Update with a valid Discord webhook URL

prof_abbrv = {
    "Guardian":"Gn", "Dragonhunter":"Dh", "Firebrand":"Fb", "Willbender":"Wb",
    "Warrior":"War", "Berserker":"Brs", "Spellbreaker":"Spb", "Bladesworn":"Bds",
    "Engineer":"Eng", "Scrapper":"Scr", "Holosmith":"Hol", "Mechanist":"Mec",
    "Ranger":"Rgr", "Druid":"Dru", "Soulbeast":"Slb", "Untamed":"Unt",
    "Thief":"Thf", "Daredevil":"Dar", "Deadeye":"Ded", "Specter":"Spe",
    "Elementalist":"Ele", "Tempest":"Tmp", "Weaver":"Wea", "Catalyst":"Cat",
    "Mesmer":"Mes", "Chronomancer":"Chr", "Mirage":"Mir", "Virtuoso":"Vir",
    "Necromancer":"Nec", "Reaper":"Rea", "Scourge":"Scg", "Harbinger":"Har",
    "Revenant":"Rev", "Herald":"Her", "Renegade":"Ren", "Vindicator":"Vin",    
}

team_colors = {
    0: "Unk",
    705: "Red",
    706: "Red",
    882: "Red",
    2520: "Red",
    2739: "Green",
    2741: "Green",
    2752: "Green",
    2763: "Green",
    432: "Blue",
    1277: "Blue",
}

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        """Handle creation of a new log file."""
        print(f"Processing newly created file: {event.src_path}")
        time.sleep(LOG_DELAY)
        start_time = datetime.datetime.now()
        log_file = event.src_path
        _, file_ext = os.path.splitext(log_file)

        if file_ext.lower() == '.zevtc':
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(log_file, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                        for extracted_file in os.listdir(temp_dir):
                            extracted_path = os.path.join(temp_dir, extracted_file)
                            header, agents, skills, events = parser.parse_evtc(extracted_path)
            except zipfile.BadZipFile:
                print(f"Failed to extract {log_file}, skipping.")
                return
            except Exception as e:
                print(f"Error processing {log_file}: {e}")
                return
        elif file_ext.lower() == '.evtc':
            try:
                header, agents, skills, events = parser.parse_evtc(log_file)
            except Exception as e:
                print(f"Error processing {log_file}: {e}")
                return
            
        team_changes = collect_team_changes(events)
        fight_count = collect_fight_count(agents, team_changes)
        print_fight_count(fight_count)

        end_time = datetime.datetime.now()
        print(f"File: {log_file} processed, {len(agents)} agents, {len(skills)} skills, {len(events)} events")
        print(f"Processing Time:  {end_time-start_time}")
        if WEBHOOK_URL:
            send_to_discord(WEBHOOK_URL, log_file, fight_count)

def collect_team_changes(events):

    team_changes = {}
    instance_id = {}

    for event in events:
        if event.is_statechange == 22:
            agent = event.src_agent
            team = event.value
            if team:
                team_changes[agent] = team

    return team_changes

def set_agent_instance_id(agents, events, instance_id) -> None:
    for agent in agents:
        for event in events:
            if not event.is_statechange and event.src_instid and event.src_agent == agent.address:
                agent.instid = event.src_instid
                break


def collect_fight_count(agents: List[parser.EvtcAgent], team_changes: Dict[int, int]) -> Dict[str, Dict[str, int]]:
    """
    Collect team changes from state change events.

    Args:
        agents (List[parser.EvtcAgent]): List of EvtcAgent objects.
        team_changes (Dict[int, int]): Mapping of agent addresses to team numbers.

    Returns:
        Dict[str, Dict[str, int]]: Mapping of team colors to a dictionary of
            agent names to their respective counts.
    """
    fight_count = {
        'squad': {}
    }

    for agent in agents:
        team = team_changes[agent.address] if agent.address in team_changes else None
        agent_team = team_colors[team] if team in team_colors else "Unk"
        if agent_team not in fight_count:
            fight_count[agent_team] = {}
            
        if agent.is_elite == 4294967295:
            continue
        if ":" in agent.name:
            name, account, sub = agent.name.split('\x00')
            if sub not in fight_count['squad']:
                fight_count['squad'][sub] = {}
            fight_count['squad'][sub][name] = account

        elif team:
            fight_count[agent_team][prof_abbrv[agent.name]] = fight_count[agent_team].get(prof_abbrv[agent.name], 0) +1

    return fight_count

def print_fight_count(fight_count: Dict[str, Dict[str, int]]) -> None:
    """
    Print a summary of the fight count to the console.

    Args:
        fight_count (Dict[str, Dict[str, int]]): Mapping of team colors to a dictionary of agent names to their respective counts.

    Returns:
        None
    """
    #Report non-squad players by team color, descending order of profession count
    for teamColor in fight_count:
        if teamColor in ['squad', 'Unk']:
            continue
        sorted_team = dict(sorted(fight_count[teamColor].items(), key=lambda item: item[1], reverse=True))
        team_count = sum(fight_count[teamColor].values())
        prof_counts = " | ".join(f"{key} : {value}" for key, value in sorted_team.items())
        print(teamColor, team_count)
        print(prof_counts)
        print(f"-----=====End of {teamColor}=====-----\n")

def send_to_discord(webhook_url: str, file_path: str, fight_count: Dict[str, Dict[str, int]]) -> None:
    """
    Send the analysis to a Discord webhook as an embed.

    Args:
        webhook_url (str): The URL of the Discord webhook.
        file_path (str): The path of the log file being analyzed.
        fight_count (Dict[str, Dict[str, int]]): Mapping of team colors to a dictionary of
            agent names to their respective counts.
    
    Returns:
        None
    """
    if not fight_count:
        message = f"No valid data to analyze in {os.path.basename(file_path)}"
        payload = {"content": message}
    else:
        # Create embed
        embed = {
            "title": f"EVTC Log Analysis: {os.path.basename(file_path)}",
            "color": 0x00FF00,  # Green color
            "fields": []
        }
        # Report non-squad players by team color, descending order of profession count
        for teamColor in fight_count:
            if teamColor in ['squad', 'Unk']:
                continue
            sorted_team = dict(sorted(fight_count[teamColor].items(), key=lambda item: item[1], reverse=True))
            team_count = sum(fight_count[teamColor].values())
            prof_counts = " | ".join(f"{key} : {value}" for key, value in sorted_team.items())
            # Create field for team player count
            embed["fields"].append({
                "name": f"Team {teamColor}",
                "value": f"{team_count} players",
                "inline": False
            })
            # Add profession breakdown
            embed["fields"].append({
                "name": "Professions",
                "value": f"{prof_counts}\n",
                "inline": True
            })

        payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code in (200, 204):
            print(f"Successfully sent analysis to Discord for {file_path}")
        else:
            print(f"Failed to send to Discord: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")



if __name__ == "__main__":
    path_to_watch = ARCDPS_LOG_DIR  # Replace with the path to the directory you want to monitor
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
