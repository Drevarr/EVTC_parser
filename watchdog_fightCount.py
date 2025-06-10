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
from watchdog.events import FileSystemEventHandler

#EXE Icon attribution: https://www.flaticon.com/authors/abdul-aziz

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith("evtc"):
            """Handle creation of a new log file."""
            print(f"New file created: {event.src_path}")
            time.sleep(LOG_DELAY)
            start_time = datetime.datetime.now()
            log_file = event.src_path
            _, file_ext = os.path.splitext(log_file)

            self.wait_for_file_completion(log_file, file_ext, start_time)

    def wait_for_file_completion(self, file_path, file_ext, start_time):
        last_size = -1
        while True:
            current_size = os.path.getsize(file_path)
            if current_size == last_size:
                print(f"File writing complete: {file_path}\n")
                process_new_log(file_path, file_ext, start_time)
                break
            last_size = current_size
            time.sleep(1)


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


    return squad_count, non_squad_summary, squad_comp

def send_to_discord(webhook_url: str, file_path: str, summary, squad_count, squad_comp) -> None:
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
                team_report += f" {gw2_data.prof_abbrv[prof]}: {sorted_team[prof]} |"
            embed["fields"].append({
                "name": f"Team {team}: {team_count}",
                "value": f"{team_report}",
                "inline": False
            })
        embed["fields"].append({
            "name": f"Squad Count: ",
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
    squad_count, team_report, squad_comp = summarize_non_squad_players(agents)
    print(f"Squad players: {squad_count}")

    end_time = datetime.datetime.now()
    print(f"File: {log_file} processed, {len(agents)} agents, {len(skills)} skills, {len(events)} events")
    print(f"Processing Time:  {end_time-start_time}")
    if WEBHOOK_URL:
        send_to_discord(WEBHOOK_URL, log_file, team_report, squad_count, squad_comp)


if __name__ == "__main__":
    # Read the config file
    config_ini = configparser.ConfigParser()
    config_ini.read('config.ini')

    ARCDPS_LOG_DIR = config_ini['Settings']['ARCDPS_LOG_DIR']
    LOG_DELAY = int(config_ini['Settings']['LOG_DELAY'])
    WEBHOOK_URL = config_ini['Settings']['WEBHOOK_URL']


    path_to_watch = ARCDPS_LOG_DIR  # Replace with the path to the directory you want to monitor
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
