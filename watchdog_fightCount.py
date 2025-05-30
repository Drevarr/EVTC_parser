import parser
import datetime
import os
import requests
import tempfile
import time
import zipfile
from collections import defaultdict, Counter
from typing import Optional
from dataclasses import dataclass
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
            
        set_team_changes(agents, events)
        set_agent_instance_id(agents, events)
        squad_count, team_report = summarize_non_squad_players(agents)
        print(f"Squad players: {squad_count}")

        end_time = datetime.datetime.now()
        print(f"File: {log_file} processed, {len(agents)} agents, {len(skills)} skills, {len(events)} events")
        print(f"Processing Time:  {end_time-start_time}")
        if WEBHOOK_URL:
            send_to_discord(WEBHOOK_URL, log_file, team_report)

def set_team_changes(agents, events):
    # Preprocess events to map src_agent to the latest team assignment
    team_assignments = {}
    for event in events:
        if event.is_statechange == 22 and event.src_agent:
            assigned_team = event.dst_agent if event.dst_agent else event.value
            if assigned_team != 0:
                team_assignments[event.src_agent] = assigned_team

    # Assign teams to agents using the preprocessed map
    for agent in agents:
        if agent.is_elite != 4294967295 and not agent.team:
            assigned_team = team_assignments.get(agent.address)
            if assigned_team in team_colors:
                agent.team = team_colors[assigned_team]

def set_agent_instance_id(agents, events):
    # Preprocess events to map src_agent to the first src_instid
    instance_ids = {}
    for event in events:
        if event.is_statechange != 22 and event.src_instid and event.src_agent:
            # Only store the first instance ID for each src_agent
            if event.src_agent not in instance_ids:
                instance_ids[event.src_agent] = event.src_instid

    # Assign instance IDs to agents
    for agent in agents:
        if agent.is_elite != 4294967295 and not agent.instid:
            instid = instance_ids.get(agent.address)
            if instid:
                agent.instid = instid

def summarize_non_squad_players(agents):
    # Dictionary to store team -> profession -> count
    non_squad_summary = defaultdict(Counter)
    squad_count = 0

    # Single pass over agents
    for agent in agents:
        # Skip invalid agents
        if agent.is_elite == 4294967295 or agent.instid is None or agent.team is None:
            continue

        # Check if agent is in squad (based on ":" in name)
        if ":" in agent.name:
            squad_count += 1
            continue

        # Count non-squad agent by team and profession (name)
        non_squad_summary[agent.team][agent.name] += 1

    # Generate report
    if not non_squad_summary:
        print("No non-squad players found.")
        return squad_count, {}

    for team in sorted(non_squad_summary.keys()):
        team_count = sum(non_squad_summary[team].values())
        team_report = f"Team {team}: {team_count}\n"
        sorted_team = dict(sorted(non_squad_summary[team].items(), key=lambda item: item[1], reverse=True))
        for prof in sorted_team:
            team_report += f"  {prof}: {sorted_team[prof]} |"
        print(team_report)

    return squad_count, non_squad_summary

def send_to_discord(webhook_url: str, file_path: str, summary) -> None:
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
    if not summary:
        message = f"No valid data to analyze in {os.path.basename(file_path)}"
        payload = {"content": message}
    else:
        # Create embed
        embed = {
            "title": f"EVTC Log Analysis: {os.path.basename(file_path)}",
            "color": 0x00FF00,  # Green color
            "fields": []
        }
        # Create field for team report
        for team in sorted(summary.keys()):
            team_report = f"|"
            team_count = sum(summary[team].values())
            sorted_team = dict(sorted(summary[team].items(), key=lambda item: item[1], reverse=True))
            for prof in sorted_team:
                team_report += f" {prof}: {sorted_team[prof]} |"
            embed["fields"].append({
                "name": f"Team {team}: {team_count}",
                "value": f"{team_report}",
                "inline": False
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
