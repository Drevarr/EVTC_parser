import parser
import gw2_data
import configparser
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
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

#EXE Icon attribution: https://www.flaticon.com/authors/abdul-aziz

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        self.handle_file_event(event)

    def on_modified(self, event):
        self.handle_file_event(event)

    def handle_file_event(self, event):
        if not event.is_directory and event.src_path.endswith((".evtc", ".zevtc")):
            print(f"File event detected: {event.src_path} ({event.event_type})")
            time.sleep(LOG_DELAY)
            start_time = datetime.datetime.now()
            log_file = event.src_path
            _, file_ext = os.path.splitext(log_file)
            self.wait_for_file_completion(log_file, file_ext, start_time)

    def wait_for_file_completion(self, file_path, file_ext, start_time):
        last_size = -1
        max_wait = 30
        start_wait = time.time()

        while time.time() - start_wait < max_wait:
            try:
                with open(file_path, 'rb'):
                    current_size = os.path.getsize(file_path)
                    if current_size == last_size and current_size > 0:
                        print(f"File writing complete: {file_path}")
                        process_new_log(file_path, file_ext, start_time)
                        break
                    last_size = current_size
            except (IOError, PermissionError):
                print(f"File {file_path} not yet accessible, waiting...")
            time.sleep(1)
        else:
            print(f"Timeout waiting for {file_path} to complete.")

def load_config(config_file='config.ini'):
    config = configparser.ConfigParser()


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
            if assigned_team in gw2_data.team_ids:
                agent.team = gw2_data.team_ids[assigned_team]


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
    squad_comp = defaultdict(Counter)
    squad_count = 0
    squad_id = []
    other_id = []
    squad_color = None

    # Single pass over agents
    for agent in agents:
        # Skip invalid agents
        if agent.is_elite == 4294967295 or agent.instid is None or agent.team is None:
            continue

        # Check if agent is in squad (based on ":" in name)
        elif ":" in agent.name:
            if agent.instid not in squad_id:
                squad_id.append(agent.instid)
                squad_count += 1
                agent_prof = gw2_data.elites[agent.is_elite] if agent.is_elite in gw2_data.elites else gw2_data.profs[agent.profession]
                squad_comp["Squad"][agent_prof] += 1
            if not squad_color: 
                squad_color = agent.team

        else:
            # Count non-squad agent by team and profession (name)
            if agent.instid not in squad_id:
                other_id.append(agent.instid)
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
            team_report += f" {gw2_data.prof_abbrv[prof]}: {sorted_team[prof]} |"
        print(team_report)


    return squad_count, non_squad_summary, squad_comp, squad_color


def send_to_discord(webhook_url, file_path, summary, squad_count, squad_comp, squad_color) -> None:
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
    DISCORD_COLORS = {
        "Red": (15548997, "#ED4245"),
        "Green": (5763719, "#57F287"),
        "Blue": (3447003, "#3498DB"),
        "Black": (2303786, "#23272A"),
        "DarkButNotBlack": (2895667, "#2C2F33"),
        "NotQuiteBlack":	(2303786, "#23272A"),
        "Blurple": (5793266, "#5865F2"),
        "Greyple":	(10070709, "#99AAb5"),
        "Fuchsia":	(15418782, "#EB459E")
    }
    DISCORD_EMOJI = {
        "Red": ":red_square:",
        "Green": ":green_square:",
        "Blue": ":blue_square:",
    }
    if not summary:
        message = f"No valid data to analyze in {os.path.basename(file_path)}"
        payload = {"content": message}
    else:
        # Create embed
        embed = {
            "title": f"Player counts for fight: {os.path.basename(file_path)}",
            "color": 793266,  # Blurple color
            "fields": [],
            "author": {
                "icon_url": "https://wiki.guildwars2.com/images/c/cb/Commander_tag_%28purple%29.png", 
                "name": "LogMon"
            },
            "footer": {
                "text": "Drevarr's Fight Log Monitor"
            },
            "timestamp": datetime.datetime.now().isoformat(timespec='milliseconds')# + 'Z'
        }

        # Create field for team report
        for team in sorted(summary.keys()):
            team_report = f"|"
            team_count = sum(summary[team].values())
            sorted_team = dict(sorted(summary[team].items(), key=lambda item: item[1], reverse=True))
            team_emoji = DISCORD_EMOJI[team]
            for prof in sorted_team:
                team_report += f" {gw2_data.prof_abbrv[prof]}: {sorted_team[prof]} |"
            embed["fields"].append({
                "name": f"{team_emoji} Team {team if team != squad_color else "Allies"}: {team_count}",
                "value": f"{team_report}",
                "inline": False
            })
        embed["fields"].append({
            "name": f":pink_heart: Squad Count: ",
            "value": f"{squad_count} squad members",
            "inline": False
        })
        squad_report = f"|"
        for prof in squad_comp["Squad"]:
            squad_report += f" {gw2_data.prof_abbrv[prof]}: {squad_comp['Squad'][prof]} |"
        embed["fields"].append({
            "name": f"Squad Composition: ",
            "value": f"{squad_report}",
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


def process_new_log(log_file, file_ext, start_time):
    print(f"Starting processing of {log_file}")
    
    if file_ext.lower() == '.zevtc':
        print(f"Processing .zevtc file: {log_file}")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(log_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                    for extracted_file in os.listdir(temp_dir):
                        extracted_path = os.path.join(temp_dir, extracted_file)
                        print(f"Extracted file: {extracted_path}")
                        last_size = -1
                        max_wait = 30
                        start_wait = time.time()
                        while time.time() - start_wait < max_wait:
                            try:
                                current_size = os.path.getsize(extracted_path)
                                if current_size == last_size and current_size > 0:
                                    print(f"Parsing extracted file: {extracted_path}")
                                    header, agents, skills, events = parser.parse_evtc(extracted_path)
                                    break
                                last_size = current_size
                            except (IOError, PermissionError) as e:
                                print(f"File {extracted_path} not yet accessible: {e}")
                            time.sleep(1)
                        else:
                            print(f"Timeout waiting for {extracted_path} to complete.")
                            return
        except zipfile.BadZipFile as e:
            print(f"Failed to extract {log_file}: {e}")
            return
        except Exception as e:
            print(f"Error processing {log_file}: {e}")
            return
    elif file_ext.lower() == '.evtc':
        print(f"Processing .evtc file: {log_file}")
        if os.path.getsize(log_file) == 0:
            print(f"Error: {log_file} is empty")
            return
        try:
            with open(log_file, 'rb') as f:
                header_bytes = f.read(12)
                if not header_bytes.startswith(b'EVTC'):
                    print(f"Error: {log_file} is not a valid EVTC file")
                    return
            header, agents, skills, events = parser.parse_evtc(log_file)
            if not all([header, agents, skills, events]):
                print(f"Error: Incomplete data from parser for {log_file}")
                return
            print(f"Parsed {log_file}: {len(agents)} agents, {len(skills)} skills, {len(events)} events")
        except Exception as e:
            print(f"Error parsing {log_file}: {e}")
            return

    print(f"Setting team changes for {len(agents)} agents")
    set_team_changes(agents, events)
    
    print(f"Setting agent instance IDs")
    set_agent_instance_id(agents, events)
    
    print(f"Summarizing non-squad players")
    squad_count, team_report, squad_comp, squad_color = summarize_non_squad_players(agents)
    print(f"Squad players: {squad_count}")
    
    end_time = datetime.datetime.now()
    print(f"File: {log_file} processed, {len(agents)} agents, {len(skills)} skills, {len(events)} events")
    print(f"Processing Time: {end_time - start_time}")
    
    if WEBHOOK_URL:
        print(f"Sending to Discord webhook: {WEBHOOK_URL}")
        send_to_discord(WEBHOOK_URL, log_file, team_report, squad_count, squad_comp, squad_color)
    else:
        print("No WEBHOOK_URL configured, skipping Discord send")


if __name__ == "__main__":
    config_ini = configparser.ConfigParser()
    config_ini.read('config.ini')

    ARCDPS_LOG_DIR = config_ini['Settings']['ARCDPS_LOG_DIR']
    if not os.path.isdir(ARCDPS_LOG_DIR):
        raise ValueError(f"Directory {ARCDPS_LOG_DIR} does not exist or is not a directory")
    if not os.access(ARCDPS_LOG_DIR, os.R_OK):
        raise ValueError(f"No read permission for directory {ARCDPS_LOG_DIR}")

    LOG_DELAY = int(config_ini['Settings'].get('LOG_DELAY', 5))
    WEBHOOK_URL = config_ini['Settings']['WEBHOOK_URL']

    path_to_watch = ARCDPS_LOG_DIR
    event_handler = MyHandler()
    observer = PollingObserver()  # Use PollingObserver for reliability
    observer.schedule(event_handler, path_to_watch, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
